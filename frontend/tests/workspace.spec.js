import { test, expect } from "@playwright/test";

const student = {
  user_id: "demo-1",
  label: "Student 1",
  rationale: "Course and assessment history",
};
const course = {
  id: 1,
  course_id: "course-1",
  title:
    "Data structures, algorithms, and problem solving with very long course names",
  subject: "Computer science",
  performance_percent: 80,
  progress_percent: 55,
  practice_topics: ["Trees"],
};
const dashboard = {
  courses: [course],
  subjects: [
    { subject: "Computer science", marks_out_of_100: 80, progress_percent: 55 },
  ],
  weak_topics: [],
  history: [],
  assessments: [],
  demo_notice: "Demo records",
};

async function mockApi(page, { signedIn = false, history = [] } = {}) {
  let session = signedIn;
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body = {};
    let status = 200;
    if (path === "/api/health") body = { status: "ok", model_configured: true };
    else if (path === "/api/students") body = [student];
    else if (path === "/api/login") {
      session = true;
      body = student;
    } else if (path === "/api/session") {
      if (route.request().method() === "DELETE") session = false;
      else if (session) body = { ...student, history };
      else {
        status = 401;
        body = { detail: "Choose a student." };
      }
    } else if (path === "/api/dashboard") body = dashboard;
    else if (path === "/api/courses") body = [course];
    else if (path === "/api/topics/course-1") body = ["Trees"];
    else if (path === "/api/conversations") body = [];
    else if (path === "/api/chat")
      body = {
        answer: "A helpful reply.",
        sources: [],
        tools_called: [],
        conversation_id: "conversation-1",
      };
    await route.fulfill({ status, json: body });
  });
}

test("deep link survives login, navigation, reload, and logout", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Student profile").selectOption(student.user_id);
  await page.getByRole("button", { name: "Enter workspace" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "Your learning overview" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Practice", exact: true }).click();
  await expect(page).toHaveURL(/\/practice$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.goForward();
  await page.reload();
  await expect(page).toHaveURL(/\/practice$/);
  await page.getByRole("button", { name: "Switch student" }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test("slow health request shows wake-up explanation and recovers", async ({
  page,
}) => {
  await mockApi(page);
  let release;
  const pending = new Promise((resolve) => {
    release = resolve;
  });
  await page.route("**/api/health", async (route) => {
    await pending;
    await route.fulfill({ json: { status: "ok" } });
  });
  await page.goto("/login");
  await expect(page.getByText("Waking up your server…")).toBeVisible({
    timeout: 6000,
  });
  await expect(
    page.getByRole("button", { name: "Enter workspace" }),
  ).toBeDisabled();
  release();
  await expect(page.getByText("Your workspace is ready")).toBeVisible();
});

test("failed startup has an actionable retry", async ({ page }) => {
  await mockApi(page);
  const fail = (route) =>
    route.fulfill({
      status: 404,
      json: { detail: "Connection endpoint unavailable." },
    });
  await page.route("**/api/health", fail);
  await page.goto("/login");
  await expect(page.getByRole("alert")).toContainText(
    "Connection endpoint unavailable.",
  );
  await page.unroute("**/api/health", fail);
  await page.getByRole("button", { name: "Try connecting again" }).click();
  await expect(page.getByText("Your workspace is ready")).toBeVisible();
});

test("expired session returns to profile selection", async ({ page }) => {
  await mockApi(page, { signedIn: true });
  await page.route("**/api/chat", (route) =>
    route.fulfill({ status: 401, json: { detail: "Session expired" } }),
  );
  await page.goto("/chat");
  await page.getByRole("textbox", { name: "Ask Orbit" }).fill("My progress?");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("alert")).toContainText("Your session has ended");
});

test("persistent health failure stops retrying after two minutes", async ({
  page,
}) => {
  await page.clock.install();
  await mockApi(page);
  let calls = 0;
  await page.route("**/api/health", (route) => {
    calls++;
    return route.fulfill({ status: 503, json: { detail: "Sleeping" } });
  });
  await page.goto("/login");
  await page.clock.runFor(121000);
  await expect(page.getByRole("alert")).toContainText(
    "taking longer than expected",
  );
  const stoppedAt = calls;
  await page.clock.runFor(10000);
  expect(calls).toBe(stoppedAt);
  await expect(
    page.getByRole("button", { name: "Try connecting again" }),
  ).toBeEnabled();
});

test("login rejection keeps the form usable", async ({ page }) => {
  await mockApi(page);
  await page.route("**/api/login", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Please try again shortly." },
    }),
  );
  await page.goto("/login");
  await page.getByLabel("Student profile").selectOption(student.user_id);
  await page.getByRole("button", { name: "Enter workspace" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Please try again shortly.",
  );
  await expect(
    page.getByRole("button", { name: "Enter workspace" }),
  ).toBeEnabled();
  await expect(page).toHaveURL(/\/login$/);
});

for (const width of [360, 768, 1440]) {
  test(`all pages fit at ${width}px and chat tables scroll locally`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await mockApi(page);
    await page.goto("/login");
    await expect(page.getByText("Your workspace is ready")).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: `test-results/login-${width}.png`,
      fullPage: true,
    });
    await page.getByLabel("Student profile").selectOption(student.user_id);
    await page.getByRole("button", { name: "Enter workspace" }).click();
    for (const path of ["/dashboard", "/practice", "/chat"]) {
      await page.goto(path);
      await expect(page.locator(".app")).toBeVisible();
      if (path === "/dashboard")
        await expect(
          page.locator(".course strong").filter({ hasText: course.title }),
        ).toBeVisible();
      if (path === "/practice")
        await expect(
          page.getByRole("heading", { name: "Create a quiz" }),
        ).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      await page.screenshot({
        path: `test-results/${path.slice(1)}-${width}.png`,
        fullPage: true,
      });
    }
    const markdown =
      "| Hackathon | Score | Submitted | Details |\n| --- | ---: | --- | --- |\n" +
      Array.from(
        { length: 20 },
        (_, i) =>
          `| Event ${i} | 80% | 2026-09-10 17:00 UTC | A lengthy assessment description |`,
      ).join("\n");
    await page.route("**/api/chat", (route) =>
      route.fulfill({
        json: { answer: markdown, sources: [], tools_called: [] },
      }),
    );
    await page
      .getByRole("textbox", { name: "Ask Orbit" })
      .fill("Show my scores");
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(page.getByRole("table")).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const box = await page.locator(".composer").boundingBox();
    expect(box.y + box.height).toBeLessThanOrEqual(900);
    await page.screenshot({
      path: `test-results/chat-${width}.png`,
      fullPage: true,
    });
    expect(errors).toEqual([]);
    if (width === 360) {
      await page.getByRole("button", { name: "Open navigation" }).click();
      await expect(
        page
          .getByRole("button", { name: "Close navigation", exact: true })
          .last(),
      ).toBeFocused();
      await page.keyboard.press("Escape");
      await expect(
        page.getByRole("button", { name: "Open navigation" }),
      ).toBeFocused();
    }
  });
}

for (const [width, height] of [
  [1440, 900],
  [1366, 768],
  [1280, 720],
  [1024, 768],
  [768, 1024],
  [390, 844],
  [375, 667],
  [360, 640],
]) {
  test(`login fits ${width}x${height}`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await mockApi(page);
    await page.goto("/login");
    await expect(page.getByText("Your workspace is ready")).toBeVisible();
    await page.getByLabel("Student profile").selectOption(student.user_id);
    const size = await page.evaluate(() => ({
      width: document.documentElement.scrollWidth,
      height: document.documentElement.scrollHeight,
    }));
    if (width === 1366 || width === 360) {
      await page.screenshot({ path: `test-results/login-${width}.png` });
    }
    expect(size.width).toBeLessThanOrEqual(width);
    expect(size.height).toBeLessThanOrEqual(height);
    await expect(
      page.getByRole("button", { name: "Enter workspace" }),
    ).toBeInViewport();
  });
}

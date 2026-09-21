import { test, expect } from "@playwright/test";

test("marks, atomic CSV imports, projects and record deletion", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Create an account" }).click();
  await page.getByLabel("Name", { exact: true }).fill("Dipesh");
  await page.getByLabel("Email").fill("phase1@example.com");
  await page
    .getByLabel("Password", { exact: true })
    .fill("phase one secure password");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Welcome, Dipesh" }),
  ).toBeVisible();
  await page.getByLabel("Subject name").fill("Database systems");
  await page.getByLabel("Subject code").fill("DB");
  await page.getByLabel("Semester", { exact: true }).fill("3");
  await page.getByRole("button", { name: "Add subject", exact: true }).click();
  await expect(page.getByRole("listitem")).toContainText("Database systems");
  await page
    .getByRole("button", { name: "Edit subject Database systems", exact: true })
    .click();
  await page.getByLabel("Subject name").fill("SQL and databases");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.getByRole("listitem")).toContainText("SQL and databases");
  await page.getByRole("button", { name: "Add mark", exact: true }).click();
  await page.getByLabel("Assessment title").fill("SQL quiz");
  await page.getByLabel("Score", { exact: true }).fill("12");
  await page.getByLabel("Maximum score").fill("20");
  await page.getByLabel("Assessment date").fill("2026-01-10");
  await page
    .getByLabel("Weak topics", { exact: false })
    .fill("joins; subqueries");
  await page.getByRole("button", { name: "Save mark", exact: true }).click();
  await expect(page.getByRole("cell", { name: "12 / 20 60%" })).toBeVisible();
  await page
    .getByRole("button", { name: "Edit mark SQL quiz", exact: true })
    .click();
  await page.getByLabel("Score", { exact: true }).fill("14");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.getByRole("cell", { name: "14 / 20 70%" })).toBeVisible();
  const header =
    "subject_code,semester,title,score,max_score,assessed_on,kind,weak_topics\n";
  const good = "DB,3,Second quiz,18,20,2026-01-12,quiz,joins\n";
  await page
    .getByLabel("Import marks CSV")
    .setInputFiles({
      name: "marks.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(
        header + good + "DB,3,Bad score,22,20,2026-01-13,quiz,\n",
      ),
    });
  await expect(page.getByRole("alert")).toContainText("Row 3");
  await expect(page.getByRole("cell", { name: /^Second quiz/ })).toHaveCount(0);
  await page
    .getByLabel("Import marks CSV")
    .setInputFiles({
      name: "marks.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(header + good),
    });
  await expect(page.getByRole("cell", { name: /^Second quiz/ })).toBeVisible();
  await page.reload();
  await expect(page.getByText("+20 pp · same type and scale")).toBeVisible();
  await page.screenshot({
    path: "test-results/phase1-academics.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "test-results/phase1-mobile.png",
    fullPage: true,
  });
  const overflow = await page.evaluate(() =>
    [...document.querySelectorAll("body *")]
      .filter(
        (e) =>
          e.getBoundingClientRect().right > innerWidth + 1 &&
          !e.closest(".record-table"),
      )
      .map((e) => ({
        tag: e.tagName,
        class: e.className,
        width: e.getBoundingClientRect().width,
        right: e.getBoundingClientRect().right,
      }))
      .slice(0, 15),
  );
  expect(overflow).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Projects", exact: true }).click();
  await page
    .getByRole("button", { name: "Add hackathon", exact: true })
    .click();
  await page.getByLabel("Hackathon name").fill("Campus Build Day");
  await page.getByLabel("Event date").fill("2026-01-15");
  await page.getByLabel("Your role").fill("Backend developer");
  await page.getByLabel("Project name").fill("My original title");
  await page
    .getByLabel("GitHub repository", { exact: false })
    .fill("https://github.com/example/orbit");
  await page.route("**/api/personal/github-preview", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "GitHub unavailable. Enter details manually." },
    }),
  );
  await page.getByRole("button", { name: "Preview GitHub details" }).click();
  await expect(page.getByRole("alert")).toContainText("GitHub unavailable");
  await expect(page.getByLabel("Project name")).toHaveValue(
    "My original title",
  );
  await page.unroute("**/api/personal/github-preview");
  await page.route("**/api/personal/github-preview", (route) =>
    route.fulfill({
      json: {
        project: "Orbit",
        summary: "A personal learning workspace",
        technologies: ["Python", "JavaScript"],
        source: "GitHub",
      },
    }),
  );
  await page.getByRole("button", { name: "Preview GitHub details" }).click();
  await expect(
    page.getByRole("button", { name: "Apply GitHub details" }),
  ).toBeVisible();
  await expect(page.getByLabel("Project name")).toHaveValue(
    "My original title",
  );
  await page.getByRole("button", { name: "Apply GitHub details" }).click();
  await page.getByLabel("Result", { exact: false }).fill("Finalist");
  await page
    .getByLabel("Reflection", { exact: true })
    .fill("Learned to scope the backend and work with a team.");
  await page
    .getByRole("button", { name: "Save hackathon", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Orbit", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/phase1-projects.png",
    fullPage: true,
  });
  await page
    .getByRole("button", {
      name: "Edit hackathon Campus Build Day",
      exact: true,
    })
    .click();
  await page.getByLabel("Result", { exact: false }).fill("Winner");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.getByText("Winner", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Assistant", exact: true }).click();
  await page
    .getByLabel("Message", { exact: true })
    .fill("What did I score in SQL?");
  await page.getByRole("button", { name: "Ask Orbit", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("enable AI responses");
  await page.getByRole("button", { name: "Coding", exact: false }).click();
  await expect(
    page.getByText("No coding source connected", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Academics", exact: true }).click();
  await page
    .getByRole("button", {
      name: "Delete subject SQL and databases",
      exact: true,
    })
    .click();
  await page
    .getByRole("button", { name: "Delete record", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Delete this subject's marks",
  );
  for (const title of ["SQL quiz", "Second quiz"]) {
    await page
      .getByRole("button", { name: `Delete mark ${title}`, exact: true })
      .click();
    await page
      .getByRole("button", { name: "Delete record", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: `Delete mark ${title}`, exact: true }),
    ).toHaveCount(0);
  }
  await page
    .getByRole("button", {
      name: "Delete subject SQL and databases",
      exact: true,
    })
    .click();
  await page
    .getByRole("button", { name: "Delete record", exact: true })
    .click();
  await expect(
    page.getByText("No subjects yet.", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Projects", exact: true }).click();
  await page
    .getByRole("button", {
      name: "Delete hackathon Campus Build Day",
      exact: true,
    })
    .click();
  await page
    .getByRole("button", { name: "Delete record", exact: true })
    .click();
  await expect(
    page.getByText("No hackathons yet.", { exact: false }),
  ).toBeVisible();
});

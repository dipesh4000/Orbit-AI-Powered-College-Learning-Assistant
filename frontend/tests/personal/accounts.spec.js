import { test, expect } from "@playwright/test";

for (const width of [360, 1440]) {
  test(`personal account flow and isolation at ${width}px`, async ({
    page,
    browser,
  }) => {
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.setViewportSize({ width, height: 900 });
    const email = `student-${width}@example.com`;
    await page.goto("/login");
    await expect(
      page.getByRole("button", { name: "Explore demo profiles" }),
    ).toHaveCount(0);
    await page.getByRole("button", { name: "Create an account" }).click();
    await page.getByLabel("Name", { exact: true }).fill("Alice");
    await page.getByLabel("Email").fill(email);
    await page
      .getByLabel("Password", { exact: true })
      .fill("a secure password here");
    await page
      .getByRole("button", { name: "Create account", exact: true })
      .click();
    await page.getByRole("button", { name: "Dashboard", exact: true }).click();
    await page.getByRole("button", { name: "Manage subjects & marks", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Dashboard", exact: true }),
    ).toBeVisible();
    await page.getByLabel("Subject name").fill("Database systems");
    await page.getByLabel("Subject code").fill("CS301");
    await page.getByLabel("Semester", { exact: true }).fill("3");
    await page.getByRole("button", { name: "Add subject", exact: true }).click();
    await expect(page.getByRole("listitem")).toContainText("Database systems");
    await page.reload();
    await page.getByRole("button", { name: "Dashboard", exact: true }).click();
    await page.getByRole("button", { name: "Manage subjects & marks", exact: true }).click();
    await expect(page.getByRole("listitem")).toContainText("Database systems");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: `test-results/personal-${width}.png`,
      fullPage: true,
    });

    const second = await browser.newContext();
    const bob = await second.newPage();
    await bob.goto("http://127.0.0.1:4176/login");
    await bob.getByRole("button", { name: "Create an account" }).click();
    await bob.getByLabel("Name", { exact: true }).fill("Bob");
    await bob.getByLabel("Email").fill(`bob-${width}@example.com`);
    await bob
      .getByLabel("Password", { exact: true })
      .fill("another secure password");
    await bob
      .getByRole("button", { name: "Create account", exact: true })
      .click();
    await bob.getByRole("button", { name: "Dashboard", exact: true }).click();
    await bob.getByRole("button", { name: "Manage subjects & marks", exact: true }).click();
    await expect(
      bob.getByText("No subjects yet.", { exact: false }),
    ).toBeVisible();
    await second.close();

    await page.getByRole("button", { name: "Sign out" }).click();
    await page.getByLabel("Email").fill(email);
    await page
      .getByLabel("Password", { exact: true })
      .fill("incorrect password");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText(
      "Email or password is incorrect",
    );
    await page
      .getByLabel("Password", { exact: true })
      .fill("a secure password here");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.getByRole("button", { name: "Dashboard", exact: true }).click();
    await page.getByRole("button", { name: "Manage subjects & marks", exact: true }).click();
    await expect(page.getByRole("listitem")).toContainText("Database systems");
    expect(errors).toEqual([]);
  });
}

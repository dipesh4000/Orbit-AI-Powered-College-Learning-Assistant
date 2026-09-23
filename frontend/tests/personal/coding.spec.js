import { test, expect } from "@playwright/test";

for (const width of [390, 1440]) {
  test(`coding snapshots, refresh recovery and manual fallback at ${width}px`, async ({
    page,
    browser,
  }) => {
    await page.setViewportSize({ width, height: 960 });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto("/login");
    await page.getByRole("button", { name: "Create an account" }).click();
    await page.getByLabel("Name", { exact: true }).fill("Taylor");
    await page.getByLabel("Email").fill(`coding-${width}@example.com`);
    await page
      .getByLabel("Password", { exact: true })
      .fill("coding secure password");
    await page
      .getByRole("button", { name: "Create account", exact: true })
      .click();
    await page.getByRole("button", { name: "Coding stats", exact: true }).click();
    await expect(page.getByText("No coding source connected")).toBeVisible();
    await page.getByPlaceholder("Your Codolio handle").fill(`test-${width}`);
    await page
      .getByRole("button", { name: "Connect Codolio", exact: true })
      .click();
    await expect(
      page.locator(".coding-metric").filter({ hasText: "Problems solved" }),
    ).toContainText("128");
    await page
      .getByRole("button", { name: "Development stats", exact: true })
      .click();
    await expect(
      page
        .getByRole("list", { name: "Daily contributions" })
        .getByRole("listitem"),
    ).toHaveCount(365);
    await expect(page.locator(".language-list")).toContainText("Python40%");
    await expect(
      page
        .locator(".coding-metric")
        .filter({ hasText: "GitHub contributions" }),
    ).toContainText("256");
    await page.screenshot({
      path: `test-results/phase2-coding-${width}.png`,
      fullPage: true,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page
      .getByRole("button", { name: "Refresh Codolio", exact: true })
      .click();
    await expect(
      page
        .getByRole("status")
        .filter({ hasText: "Codolio could not be refreshed" }),
    ).toBeVisible();
    await expect(
      page
        .locator(".coding-metric")
        .filter({ hasText: "GitHub contributions" }),
    ).toContainText("256");
    await page.reload();
    await page.getByRole("button", { name: "Coding stats", exact: true }).click();
    await expect(
      page.locator(".coding-metric").filter({ hasText: "Problems solved" }),
    ).toContainText("128");
    await page.getByRole("button", { name: "Enter totals manually" }).click();
    await page.getByLabel("Problems solved", { exact: true }).fill("0");
    await page.getByLabel("Snapshot note").fill("Checked my profile today");
    await page.getByRole("button", { name: "Save manual snapshot" }).click();
    await expect(
      page.locator(".coding-metric").filter({ hasText: "Problems solved" }),
    ).toContainText("0");
    await expect(
      page
        .locator(".coding-metric")
        .filter({ hasText: "Problem-solving active days" }),
    ).toContainText("Not reported");
    await page
      .getByRole("button", { name: "Disconnect Codolio", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Cancel" })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page
      .getByRole("button", { name: "Disconnect Codolio", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Remove history" })
      .click();
    await expect(page.getByText("No coding source connected")).toBeVisible();
    await expect(page.getByText("Checked my profile today")).toBeVisible();
    await page.reload();
    await page.getByRole("button", { name: "Coding stats", exact: true }).click();
    await expect(page.getByText("Checked my profile today")).toBeVisible();
    // A separate session cannot read any of these records.
    const other = await browser.newContext();
    const response = await other.request.get(
      "http://127.0.0.1:8011/api/coding",
    );
    expect(response.status()).toBe(401);
    await other.close();
    await page
      .getByRole("button", { name: "Remove manual history", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Remove history" })
      .click();
    await expect(page.getByText("Your own starting point")).toBeVisible();
    expect(errors).toEqual([]);
  });
}

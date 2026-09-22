import { test, expect } from "@playwright/test";

for (const width of [390, 1440]) {
  test(`chat first, recovery and saved practice at ${width}px`, async ({ page }) => {
    const errors = [];
    page.on("pageerror", e => errors.push(e.message));
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/login");
    await page.getByRole("button", { name: "Create an account" }).click();
    await page.getByLabel("Name", { exact: true }).fill("Learner");
    await page.getByLabel("Email").fill(`chat-practice-${width}@example.com`);
    await page.getByLabel("Password", { exact: true }).fill("safe practice password");
    await page.getByRole("button", { name: "Create account", exact: true }).click();
    await expect(page.getByRole("heading", { name: "What's on your mind, Learner?" })).toBeVisible();
    await expect(page.locator(".summary-grid")).toHaveCount(0);
    const message = page.getByLabel("Message", { exact: true });
    await message.fill("Draft");
    await message.press("Shift+Enter");
    await message.press("a");
    await expect(message).toHaveValue("Draft\na");
    await page.getByRole("button", { name: "Academics", exact: true }).click();
    await page.getByRole("button", { name: "Assistant", exact: true }).click();
    await expect(message).toHaveValue("Draft\na");
    await page.screenshot({ path: `test-results/chat-empty-${width}.png` });
    await message.fill("Hi");
    await message.press("Enter");
    await expect(page.locator(".chat-message.assistant")).toContainText("Hi!");
    await page.reload();
    await expect(page.locator(".chat-message.assistant")).toContainText("Hi!");
    const box = await message.boundingBox();
    expect(box.y + box.height).toBeLessThanOrEqual(900);
    await message.fill("Review my marks");
    await message.press("Enter");
    await expect(page.getByRole("alert")).toContainText("No model provider configured");
    await expect(message).toHaveValue("Review my marks");
    page.once("dialog", d => d.accept());
    await page.getByRole("button", { name: "Clear conversation" }).click();
    await expect(page.locator(".chat-message.assistant")).toHaveCount(0);

    const subject = await (await page.request.post("/api/subjects", { data: { name: "Databases", code: "DB", semester: "1" } })).json();
    const uploaded = await (await page.request.post("/api/papers", { multipart: {
      subject_id: String(subject.id), year: "2025", topics: "SQL",
      file: { name: "sql.txt", mimeType: "text/plain", buffer: Buffer.from("1. SQL SELECT reads rows. Which SQL keyword reads rows? [2 marks]") },
    } })).json();
    await expect.poll(async () => (await (await page.request.get(`/api/papers/${uploaded.id}`)).json()).questions.length).toBe(1);
    const detail = await (await page.request.get(`/api/papers/${uploaded.id}`)).json();
    const q = detail.questions[0];
    const reviewed = await page.request.put(`/api/paper-questions/${q.id}`, { data: { content: q.content, topic: "SQL", marks: 2, page: 1, confirmed: true, revision: q.revision } });
    expect(reviewed.ok()).toBe(true);
    await page.reload();
    await page.getByRole("button", { name: "Practice", exact: true }).click();
    await page.getByLabel("Practice subject").selectOption(String(subject.id));
    await page.getByLabel("Practice topic").fill("SQL");
    await page.getByLabel("Questions", { exact: true }).fill("1");
    await page.getByRole("button", { name: "Generate practice", exact: true }).click();
    await expect(page.getByText("Which keyword does the source use to read rows?", { exact: false })).toBeVisible();
    await expect(page.getByText("The supplied text explicitly says SELECT reads rows.")).toHaveCount(0);
    await page.getByLabel("DROP", { exact: true }).check();
    await page.getByRole("button", { name: "Check and save answers" }).click();
    await expect(page.getByRole("status")).toContainText("0/1");
    await page.reload();
    await page.getByRole("button", { name: "Practice", exact: true }).click();
    await page.getByRole("button", { name: "Review", exact: true }).click();
    await expect(page.getByLabel("DROP", { exact: true })).toBeChecked();
    await expect(page.getByText("The supplied text explicitly says SELECT reads rows.")).toBeVisible();
    await page.screenshot({ path: `test-results/practice-${width}.png`, fullPage: true });
    await page.getByRole("button", { name: "Actions", exact: true }).click();
    await page.getByRole("button", { name: "Refresh suggestions" }).click();
    await expect(page.getByRole("heading", { name: "Practise SQL again" })).toBeVisible();
    await page.getByRole("button", { name: "Practice", exact: true }).click();
    page.once("dialog", d => d.accept());
    await page.getByRole("button", { name: "Delete", exact: true }).click();
    await expect(page.getByText("No practice yet.", { exact: false })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });
}

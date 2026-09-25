import { test, expect } from "@playwright/test";

test("demo reveals words, changes chats safely, and persists an accessible theme", async ({ page }) => {
  const answer = "## Your study plan\n\n" + "Practise one topic and explain your reasoning. ".repeat(30);
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api", "");
    let body = {};
    if (path === "/health") body = { status: "ok", local_demo: true };
    if (path === "/session") body = { kind: "personal", owner_id: 1, name: "Demo", demo_account: true };
    if (path === "/personal/workspace") body = { subjects: [], hackathons: [] };
    if (path === "/personal/chats") body = [{ id: 1, title: "First chat" }, { id: 2, title: "Second chat" }];
    if (/\/messages$/.test(path)) body = route.request().method() === "POST" ? { answer, sources: [], tools_called: [] } : { history: [] };
    if (path === "/coding") body = { connection: null, latest: {} };
    if (path === "/github/profile") body = { profile: null };
    await route.fulfill({ json: body });
  });
  await page.goto("/chat");
  await page.getByLabel("Message", { exact: true }).fill("Help me plan");
  await page.getByRole("button", { name: "Ask Orbit" }).click();
  const reply = page.locator(".chat-message.assistant");
  await expect(reply).toContainText("Your study plan");
  const first = (await reply.innerText()).length;
  expect(first).toBeLessThan(answer.length / 2);
  await expect.poll(async () => (await reply.innerText()).length).toBeGreaterThan(first);
  await page.getByRole("button", { name: "Second chat", exact: true }).click();
  await expect(reply).toHaveCount(0);
  await expect(page.getByLabel("Message", { exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Open settings" }).click();
  await page.getByRole("switch", { name: "Dark mode" }).click();
  await expect(page.locator(".personal-shell")).toHaveAttribute("data-theme", "dark");
  expect(await page.locator(".settings-connection-block").first().evaluate(el => getComputedStyle(el).backgroundColor)).toBe("rgb(38, 38, 38)");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("switch", { name: "Dark mode" })).toBeInViewport();
  await expect(page.getByRole("button", { name: "Close settings" })).toBeInViewport();
  await page.reload();
  await expect(page.locator(".personal-shell")).toHaveAttribute("data-theme", "dark");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

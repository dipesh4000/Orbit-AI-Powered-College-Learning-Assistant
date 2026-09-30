import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

test("source geometry, live-account motion, sizing, and reduced motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  const source = readFileSync(new URL("../../../../orbit-ai-mark.html", import.meta.url), "utf8");
  await page.setContent(source);
  const reference = await page.locator(".petal").evaluateAll(nodes => nodes.map(node => {
    const m = node.getCTM();
    return [m.a, m.b, m.c, m.d, m.e, m.f];
  }));
  let releaseReply;
  const replyReady = new Promise(resolve => { releaseReply = resolve; });
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname.replace("/api", "");
    let body = {};
    if (path === "/health") body = { status: "ok" };
    if (path === "/session") body = { kind: "personal", owner_id: 1, name: "Dipesh", demo_account: false };
    if (path === "/personal/workspace") body = { subjects: [], hackathons: [] };
    if (path === "/personal/chats") body = [{ id: 1, title: "First chat" }];
    if (/\/messages$/.test(path)) {
      if (route.request().method() === "POST") {
        await replyReady;
        body = { answer: "Start with one topic. ".repeat(70), sources: [], tools_called: [] };
      } else body = { history: [] };
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/chat");
  await expect(page.locator(".orbit-startup-intro")).toBeVisible();
  await expect(page.locator(".orbit-startup-intro")).toHaveCount(0);
  await expect(page.locator(".chat-heading, .chat-demo-note")).toHaveCount(0);
  const headerMark = page.locator(".workspace-title .orbit-ai-mark");
  await expect(headerMark).toHaveAttribute("data-state", "idle");
  const idlePetal = headerMark.locator("path").first();
  const idleBefore = await idlePetal.evaluate(node => getComputedStyle(node).transform);
  await expect.poll(() => idlePetal.evaluate(node => getComputedStyle(node).transform)).not.toBe(idleBefore);
  const brand = page.locator(".personal-sidebar .brand .orbit-ai-mark");
  await expect(brand).toBeVisible();
  // Compare all 16 group transforms against the actual supplied HTML at its size.
  const actual = await brand.evaluate(node => {
    const oldStyle = node.getAttribute("style");
    node.style.width = "180px";
    node.style.height = "180px";
    const matrices = [...node.querySelectorAll(".orbit-mark-petal")].map(petal => {
      const m = petal.getCTM();
      return [m.a, m.b, m.c, m.d, m.e, m.f];
    });
    if (oldStyle === null) node.removeAttribute("style");
    else node.setAttribute("style", oldStyle);
    return matrices;
  });
  actual.forEach((matrix, i) => matrix.forEach((value, j) => expect(value).toBeCloseTo(reference[i][j], 4)));
  const ratio = await brand.evaluate(node => node.getBoundingClientRect().width / parseFloat(getComputedStyle(node.parentElement).fontSize));
  expect(ratio).toBeCloseTo(1.25, 2);
  await page.screenshot({ path: "test-results/orbit-welcome.png" });
  await page.getByLabel("Message", { exact: true }).fill("Help me plan");
  await page.getByRole("button", { name: "Ask Orbit" }).click();
  const thinking = page.locator(".chat-thinking .orbit-ai-mark");
  await expect(thinking).toBeVisible();
  await expect(headerMark).toHaveAttribute("data-state", "thinking");
  const petal = thinking.locator("path").first();
  const before = await petal.evaluate(node => getComputedStyle(node).transform);
  await expect.poll(() => petal.evaluate(node => getComputedStyle(node).transform)).not.toBe(before);
  await page.screenshot({ path: "test-results/orbit-thinking.png" });
  releaseReply();
  const responding = page.locator(".chat-message.assistant .orbit-ai-mark");
  await expect(responding).toHaveAttribute("data-state", "responding");
  await expect(headerMark).toHaveAttribute("data-state", "responding");
  await page.screenshot({ path: "test-results/orbit-responding.png" });
  await expect(responding).toHaveAttribute("data-state", "rest", { timeout: 10000 });
  await expect(headerMark).toHaveAttribute("data-state", "idle");
  await page.getByRole("button", { name: "Collapse sidebar", exact: true }).click();
  await expect(brand).toBeVisible();
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(await brand.locator("path").first().evaluate(node => getComputedStyle(node).animationName)).toBe("none");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("button", { name: "Open navigation", exact: true }).click();
  await page.getByRole("button", { name: "Open settings", exact: true }).click();
  await page.getByRole("switch", { name: "Dark mode" }).click();
  await page.getByRole("button", { name: "Close settings", exact: true }).click();
  expect(await brand.locator("path").first().evaluate(node => getComputedStyle(node).fill)).toBe("rgb(240, 240, 240)");
  await page.getByRole("button", { name: "Close navigation", exact: true }).filter({ visible: true }).last().click();
  await page.screenshot({ path: "test-results/orbit-mobile-dark.png" });
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/");
  await expect(page.locator(".orbit-startup-intro")).toBeVisible();
  await expect(page.locator(".orbit-startup-intro")).toHaveCount(0);
  await page.screenshot({ path: "test-results/orbit-landing.png" });
});

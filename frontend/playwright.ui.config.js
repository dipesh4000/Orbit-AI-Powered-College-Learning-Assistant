import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/ui", workers: 1,
  use: { baseURL: "http://127.0.0.1:4187", channel: "msedge" },
  webServer: { command: "npm run dev -- --host 127.0.0.1 --port 4187", url: "http://127.0.0.1:4187" },
});

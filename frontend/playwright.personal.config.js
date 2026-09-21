import { defineConfig } from "@playwright/test";
import path from "node:path";
const python = path.resolve(
  "../backend/.venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);

export default defineConfig({
  testDir: "./tests/personal",
  workers: 1,
  timeout: 60000,
  use: {
    baseURL: "http://127.0.0.1:4176",
    browserName: "chromium",
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    },
  },
  webServer: [
    {
      command: `"${python}" ../backend/tests/personal_server.py`,
      url: "http://127.0.0.1:8011/api/health",
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 4176",
      url: "http://127.0.0.1:4176",
      env: { ORBIT_API_PROXY: "http://127.0.0.1:8011" },
    },
  ],
});

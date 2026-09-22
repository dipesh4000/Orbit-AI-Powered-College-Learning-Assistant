import { defineConfig } from "@playwright/test";
import path from "node:path";
const python=path.resolve("../backend/.venv",process.platform==="win32" ? "Scripts/python.exe":"bin/python");
export default defineConfig({
  testDir:"./tests/demo", workers:1, timeout:60000, outputDir:"test-results/demo",
  use:{baseURL:"http://127.0.0.1:4176",browserName:"chromium",launchOptions:{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH}},
  webServer:[
    {command:`"${python}" -m orbit.demo_server`,cwd:"../backend",url:"http://127.0.0.1:8011/api/health"},
    {command:"npm run dev -- --host 127.0.0.1 --port 4176",url:"http://127.0.0.1:4176",env:{ORBIT_API_PROXY:"http://127.0.0.1:8011"}},
  ],
});

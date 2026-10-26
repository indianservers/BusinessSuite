import { defineConfig } from "playwright/test";
export default defineConfig({
  testDir: "../playwright", testMatch: "pms-notes-workspace.spec.ts", timeout: 60000,
  expect: { timeout: 12000 }, workers: 1,
  use: { baseURL: "http://127.0.0.1:5185", trace: "retain-on-failure" },
  webServer: [
    { command: process.platform === "win32" ? "..\\backend\\venv\\Scripts\\python.exe ..\\backend\\scripts\\serve_notes_qa.py" : "python ../backend/scripts/serve_notes_qa.py", url: "http://127.0.0.1:1559/docs", reuseExistingServer: true, timeout: 120000 },
    { command: "npm run dev -- --host 127.0.0.1 --port 5185 --strictPort", url: "http://127.0.0.1:5185", reuseExistingServer: true, env: { VITE_DEV_API_PROXY_TARGET: "http://127.0.0.1:1559" }, timeout: 120000 },
  ],
});

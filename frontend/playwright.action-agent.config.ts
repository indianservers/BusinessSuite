import { defineConfig } from 'playwright/test';

export default defineConfig({
  testDir: '../playwright',
  testMatch: 'action-agent-live-qa.spec.ts',
  outputDir: '../outputs/action-agent-browser-live',
  timeout: 120_000,
  expect: { timeout: 30_000 },
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:5192', trace: 'retain-on-failure' },
  webServer: [
    {
      command: '"../backend/venv/Scripts/python.exe" ../backend/scripts/run_action_agent_qa.py',
      url: 'http://127.0.0.1:1558/health',
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5192 --strictPort',
      url: 'http://127.0.0.1:5192',
      reuseExistingServer: false,
      timeout: 120_000,
      env: { VITE_DEV_API_PROXY_TARGET: 'http://127.0.0.1:1558', VITE_CACHE_DIR: '../.local/vite-action-agent-qa' },
    },
  ],
});

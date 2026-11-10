import { defineConfig } from 'playwright/test';

const port = Number(process.env.ASSISTANT_QA_PORT || 63934);

export default defineConfig({
  testDir: '../playwright',
  testMatch: ['ai-daily-briefing.spec.ts','nlp-training.spec.ts','action-bot.spec.ts','model-release.spec.ts'],
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: { baseURL: `http://127.0.0.1:${port}`, trace: 'retain-on-failure' },
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${port}`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: { VITE_SUPPRESS_PROXY_ERRORS: 'true' },
  },
});

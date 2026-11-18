import {defineConfig} from 'playwright/test';
const port=Number(process.env.QA_SHELL_PORT||5386);
export default defineConfig({
 testDir:'../playwright',testMatch:['action-bot.spec.ts','action-bot-drag.spec.ts','ai-daily-briefing.spec.ts','nlp-training.spec.ts','model-release.spec.ts'],
 outputDir:'test-results/qa-suite-shell',timeout:60000,expect:{timeout:15000},workers:2,
 use:{baseURL:`http://127.0.0.1:${port}`,trace:'retain-on-failure'},
 webServer:{command:`node node_modules/vite/bin/vite.js --config scripts/vite-module-regression.config.mjs --host 127.0.0.1 --port ${port} --strictPort`,url:`http://127.0.0.1:${port}`,reuseExistingServer:!!process.env.QA_SHELL_PORT,timeout:120000,env:{VITE_SUPPRESS_PROXY_ERRORS:'true',VITE_CACHE_DIR:'node_modules/.vite-qa-suite-shell'}},
});

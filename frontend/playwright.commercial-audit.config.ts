import { defineConfig } from "playwright/test";
export default defineConfig({testDir:"../playwright",testMatch:["connected-commercial-live.spec.ts","pms-assistant-live.spec.ts","pms-recovery-live.spec.ts","pms-workspace-reset-live.spec.ts"],workers:1,timeout:90000,use:{baseURL:"http://127.0.0.1:5191",trace:"off",screenshot:"only-on-failure"},outputDir:"../test-results/commercial-audit"});

import {defineConfig} from 'playwright/test';
export default defineConfig({testDir:'../playwright',testMatch:['workload-rebalance-review.spec.ts','action-bot.spec.ts'],timeout:45000,
 expect:{timeout:10000},use:{baseURL:'http://127.0.0.1:5186',trace:'retain-on-failure'}});

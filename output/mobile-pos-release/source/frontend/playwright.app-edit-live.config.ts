import {defineConfig} from 'playwright/test';
export default defineConfig({outputDir:"test-results/app-edit-live",testDir:'../playwright',testMatch:'app-edit-delete-live.spec.ts',workers:1,use:{baseURL:'http://127.0.0.1:5175',trace:'retain-on-failure'}});

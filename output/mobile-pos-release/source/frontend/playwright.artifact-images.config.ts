import {defineConfig} from 'playwright/test';

export default defineConfig({
 testDir:'../playwright',testMatch:'artifact-image.spec.ts',timeout:45_000,
 expect:{timeout:10_000},use:{baseURL:'http://127.0.0.1:5186',trace:'retain-on-failure'},
});

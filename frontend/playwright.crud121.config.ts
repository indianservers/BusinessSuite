import {defineConfig} from "playwright/test";
export default defineConfig({testDir:"../playwright",testMatch:"crud121-*.spec.ts",timeout:60000,expect:{timeout:15000},workers:1,use:{baseURL:"http://127.0.0.1:1582",viewport:{width:1600,height:1100},trace:"retain-on-failure"},outputDir:"../outputs/crud-permissions-121-final/test-artifacts"});

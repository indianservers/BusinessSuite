import {defineConfig} from "playwright/test";
export default defineConfig({
 testDir:"../playwright",testMatch:["catalog-offerings.spec.ts","catalog-views.spec.ts"],
 outputDir:"../output/catalog-offerings/test-results",timeout:60000,workers:1,
 use:{channel:"chrome",baseURL:"http://127.0.0.1:5197",trace:"retain-on-failure"},
 webServer:{command:"npm run dev -- --host 127.0.0.1 --port 5197",url:"http://127.0.0.1:5197",reuseExistingServer:true,timeout:120000,env:{VITE_SUPPRESS_PROXY_ERRORS:"true"}},
});

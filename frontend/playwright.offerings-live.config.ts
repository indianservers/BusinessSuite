import {defineConfig} from 'playwright/test';
export default defineConfig({
 testDir:'../playwright',testMatch:'catalog-offerings-live.spec.ts',workers:1,timeout:90000,
 expect:{timeout:12000},outputDir:'../output/offerings-live-audit/traces',
 reporter:[['line'],['json',{outputFile:'../output/offerings-live-audit/results.json'}]],
 use:{viewport:{width:1920,height:1080},actionTimeout:12000,navigationTimeout:30000,channel:'chrome',baseURL:'http://127.0.0.1:5198',trace:'retain-on-failure',screenshot:'only-on-failure'},
 webServer:{command:'npm run dev -- --host 127.0.0.1 --port 5198',url:'http://127.0.0.1:5198',reuseExistingServer:true,timeout:120000,
 env:{VITE_DEV_API_PROXY_TARGET:'http://127.0.0.1:8799',VITE_SUPPRESS_PROXY_ERRORS:'true'}},
});

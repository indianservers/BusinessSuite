import {defineConfig} from 'playwright/test';
export default defineConfig({testDir:'../playwright',testMatch:['crm-contacts-ui.spec.ts','crm-lead-workbench.spec.ts','crm-deals-ui.spec.ts','srm-sales-orders-ui.spec.ts','srm-invoices-ui.spec.ts','srm-receipts-ui.spec.ts','srm-contracts-ui.spec.ts','srm-engagements-ui.spec.ts','srm-ui-routes.spec.ts','srm-invoice-drafts-ui.spec.ts'],outputDir:'../test-results/qa-crm-srm-20261118',timeout:120000,expect:{timeout:12000},workers:1,use:{actionTimeout:15000,baseURL:'http://127.0.0.1:5383',trace:'retain-on-failure'},webServer:{command:'node --max-old-space-size=4096 node_modules/vite/bin/vite.js --config scripts/vite-qa-crm-srm.config.mjs --host 127.0.0.1 --port 5383 --strictPort',url:'http://127.0.0.1:5383',reuseExistingServer:true,timeout:120000,env:{VITE_CACHE_DIR:'node_modules/.vite-qa-crm-srm-20261118',VITE_SUPPRESS_PROXY_ERRORS:'true'}}});






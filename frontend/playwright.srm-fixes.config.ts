import {defineConfig} from 'playwright/test';
import base from './playwright.srm-audit.config';

export default defineConfig({
  ...base,
  testMatch:['srm-navigation.spec.ts','srm-route-audit.spec.ts','srm-ui-routes.spec.ts','srm-picker-recovery.spec.ts'],
  outputDir:'test-results/srm-fixes',
  use:{...base.use,baseURL:'http://127.0.0.1:5193'},
  webServer:{
    command:'npm run dev -- --host 127.0.0.1 --port 5193 --strictPort',
    url:'http://127.0.0.1:5193',reuseExistingServer:false,timeout:120_000,
    env:{VITE_SUPPRESS_PROXY_ERRORS:'true',VITE_CACHE_DIR:'../.local/vite-srm-fixes'},
  },
});

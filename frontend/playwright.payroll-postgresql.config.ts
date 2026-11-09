import { defineConfig } from 'playwright/test';
const backend=process.env.PAYROLL_QA_BACKEND_PORT||'1569';
const frontend=process.env.PAYROLL_QA_FRONTEND_PORT||'5209';
export default defineConfig({
  testDir:'../playwright',testMatch:['payroll-qa-live.spec.ts','payroll-postgresql-combinations.spec.ts','payroll-postgresql-policies.spec.ts'],workers:1,timeout:120000,
  outputDir:'../.tmp/payroll-postgresql-browser',expect:{timeout:15000},
  use:{baseURL:`http://127.0.0.1:${frontend}`,trace:'on',serviceWorkers:'block'},
  projects:[{name:'desktop',use:{viewport:{width:1440,height:1000}}},{name:'phone',use:{viewport:{width:390,height:844}}}],
  webServer:[
    {command:'"../backend/venv/Scripts/python.exe" "../backend/scripts/suite_navigation_qa_server.py"',url:`http://127.0.0.1:${backend}/health`,reuseExistingServer:false,timeout:180000,env:{SUITE_QA_PORT:backend}},
    {command:`node node_modules/vite/bin/vite.js --host 127.0.0.1 --port ${frontend} --strictPort`,url:`http://127.0.0.1:${frontend}`,reuseExistingServer:false,timeout:120000,env:{VITE_DEV_API_PROXY_TARGET:`http://127.0.0.1:${backend}`,VITE_SUPPRESS_PROXY_ERRORS:'true',VITE_CACHE_DIR:process.env.PAYROLL_QA_VITE_CACHE||'../.tmp/payroll-postgres-vite'}}
  ]
});

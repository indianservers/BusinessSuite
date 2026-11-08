// The CRM task page shares its composer and store with PMS.
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const result=spawnSync(process.execPath,[path.join(root,'frontend/node_modules/playwright/cli.js'),'test','--config='+path.join(root,'frontend/playwright.create-flows.config.ts'),'--grep','crm tasks:'],{cwd:root,stdio:'inherit'});
process.exitCode=result.status||0;

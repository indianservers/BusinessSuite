const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {chromium,expect}=require('playwright/test');
(async()=>{
 const root=path.resolve(__dirname,'..'),fixture=path.join(root,'.tmp-audit-pms-shell.tsx');
 fs.writeFileSync(fixture,`import React from'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import Frame from './src/shared/workspace/ModuleWorkspaceFrame';import{useAuthStore}from './src/store/authStore';import{hasPmsWorkspaceShell}from './src/lib/task-workspace';import './src/index.css';useAuthStore.setState({user:{id:1,email:'qa@example.test',role:'admin',is_superuser:true}});const path=new URLSearchParams(location.search).get('path')||'/pms',url=new URL(path,location.origin);window.owned=hasPmsWorkspaceShell(url.pathname,url.search);createRoot(document.getElementById('root')).render(<MemoryRouter initialEntries={[path]}><Frame module="pms"><header aria-label="Native workspace header">Native workspace</header></Frame></MemoryRouter>);`);
 const {createServer}=await import('vite');const server=await createServer({root,server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();
 try{
 const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/qa-pms-shell*',route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div><script type="module" src="/.tmp-audit-pms-shell.tsx"></script>'}));
 for(const [path,frame] of [['/pms',false],['/pms/',false],['/pms/workspaces?workspace=1',false],['/pms/workspaces?task=7',false],['/pms/workspaces?new=project',false],['/pms/workspaces',true],['/pms/workspaces?new=workspace',true],['/pms/projects',true]]){
  await page.goto('http://127.0.0.1:'+server.httpServer.address().port+'/qa-pms-shell?path='+encodeURIComponent(path));
  await expect(page.getByRole('banner',{name:'Native workspace header'})).toHaveCount(1);
  await expect(page.getByRole('navigation',{name:'PMS pages',exact:true})).toHaveCount(frame?1:0);
  assert.equal(await page.evaluate(()=>window.owned),!frame);
 }
 assert.deepEqual(errors,[]);console.log('PASS PMS shell: native root/legacy workspace header rendered once; directory, create-workspace and project navigation preserved');
 }finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});

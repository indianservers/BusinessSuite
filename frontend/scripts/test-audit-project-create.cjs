const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const {chromium,expect:baseExpect}=require('playwright/test');const expect=baseExpect.configure({timeout:30000});
(async()=>{
 const root=path.resolve(__dirname,'..');
 const source=`import React,{useState}from'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Page from './src/apps/project-management/pages/CreateProjectPage';import Team from './src/components/app/WorkspaceEnhancements';import{useAuthStore}from './src/store/authStore';useAuthStore.setState({isHydrated:true,isAuthenticated:true,user:{id:1,email:'qa@example.test',role:'admin',is_superuser:true}});const client=new QueryClient({defaultOptions:{queries:{retry:false}}});function App(){const[open,setOpen]=useState(true);return <><Team/><button onClick={()=>setOpen(!open)}>Toggle form</button>{open&&<Page onCreated={p=>{window.created=p;setOpen(false)}} onCancel={()=>setOpen(false)}/>}</>};createRoot(document.getElementById('root')).render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/pms/projects/new']}><App/></MemoryRouter></QueryClientProvider>);`;
 const fixture=path.join(root,'.tmp-audit-project-fixture.tsx');fs.writeFileSync(fixture,source);
 const {createServer}=await import('vite');
 const server=await createServer({root,server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();
 const browser=await chromium.launch({headless:true});
 try{
 const page=await browser.newPage(),errors=[];let reads=0,writes=0,fail=true;
 page.on('pageerror',e=>{errors.push(e.message);console.error(e.message);});
 await page.route('**/api/**',route=>{
  const req=route.request(),url=new URL(req.url());
  if(url.pathname.endsWith('/project-management/workspaces')){reads++;return route.fulfill({status:fail?503:200,json:fail?{detail:'Workspace service temporarily unavailable'}:[{id:12,name:'Audit workspace',role:'Owner'},{id:13,name:'Guest workspace',role:'Guest'}]});}
  if(url.pathname.endsWith('/project-management/projects')&&req.method()==='POST'){writes++;const body=req.postDataJSON();assert.equal(body.workspace_id,12);assert.equal(body.name,'Audit project');return route.fulfill({status:201,json:{...body,id:42}});}
  if(url.pathname.endsWith('/overview'))return route.fulfill({json:{tasks:[],projects:[],role:'Owner'}});
  if(url.pathname.endsWith('/entries'))return route.fulfill({json:[]});
  if(url.pathname.endsWith('/members'))return route.fulfill({json:[]});
  if(url.pathname.includes('/api/'))return route.fulfill({json:{fields:[]}});
  return route.fulfill({json:{}});
 });
 await page.route('**/qa-audit-project',route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div><script type="module" src="/.tmp-audit-project-fixture.tsx"></script>'}));
 await page.goto('http://127.0.0.1:'+server.httpServer.address().port+'/qa-audit-project');
 await expect(page.getByRole('button',{name:'Retry loading workspaces'})).toBeVisible();
 // A failed options request must leave the rest of the draft editable.
 await page.locator('#project-name').fill('Audit project');
 fail=false;await page.getByRole('button',{name:'Retry loading workspaces'}).click();
 await expect(page.getByLabel('Project workspace')).toHaveValue('12');
 await expect(page.getByLabel('Project workspace').locator('option')).toHaveText(['Choose workspace','Audit workspace']);
 assert.equal(reads,2);
 await page.getByRole('button',{name:'Toggle form'}).click();await page.getByRole('button',{name:'Toggle form'}).click();
 await expect(page.getByLabel('Project workspace')).toHaveValue('12');assert.equal(reads,2);
 await page.locator('#project-name').fill('Audit project');
 await page.getByRole('button',{name:'Create project',exact:true}).click();
 await expect.poll(()=>writes).toBe(1);await expect.poll(()=>page.evaluate(()=>window.created?.id)).toBe(42);
 await page.getByRole('button',{name:'Team workspace',exact:true}).click();await expect(page.getByRole('dialog',{name:'Team workspace',exact:true})).toBeVisible();await expect(page.getByRole('heading',{name:'Tasks',exact:true})).toBeVisible();assert.equal(reads,2,'team selector must reuse project form workspace options');
 await page.getByRole('button',{name:'Close team workspace',exact:true}).click();await page.evaluate(()=>sessionStorage.setItem('suite-branch','2'));await page.getByRole('button',{name:'Team workspace',exact:true}).click();await expect(page.getByRole('heading',{name:'Tasks',exact:true})).toBeVisible();assert.equal(reads,3,'branch switch must use a separate workspace cache');
 assert.deepEqual(errors,[]);console.log('PASS project create: failure/retry, editable draft, valid workspace roles, cached reopen, linked create');
 }finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});


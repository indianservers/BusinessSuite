const fs=require('node:fs'),path=require('node:path');
const {chromium,expect:baseExpect}=require('playwright/test');
const expect=baseExpect.configure({timeout:20000});
(async()=>{
 const apiOrigin=process.env.WORKFLOW_TEST_ORIGIN;
 if(!apiOrigin||new URL(apiOrigin).hostname!=='127.0.0.1')throw new Error('Run only through the disposable pytest fixture');
 const fixture=path.join(__dirname,'.audit-helpdesk-live.tsx');
 fs.writeFileSync(fixture,`import React from'react';import{createRoot}from'react-dom/client';import{BrowserRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Page from'@/apps/hrms/pages/helpdesk/HelpdeskPage';import Gate from'@/components/forms/FormDefaultsGate';import{useAuthStore}from'@/store/authStore';import{api}from'@/services/api';import'@/index.css';const config=(window as any).__HD_QA__;sessionStorage.setItem('suite-branch',config.branch);sessionStorage.setItem('suite-company',config.company);useAuthStore.setState({isHydrated:true,isAuthenticated:true,accessToken:config.token});const {data:user}=await api.get('/auth/me');useAuthStore.setState({user:{...user,role:typeof user.role==='object'?user.role.name:user.role}});createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><BrowserRouter><main className="p-4"><Gate required={false}><Page/></Gate></main></BrowserRouter></QueryClientProvider>);`);
 const {createServer}=await import('vite');
 const server=await createServer({root:process.cwd(),cacheDir:process.env.WORKFLOW_TEST_CACHE,server:{host:'127.0.0.1',port:0,hmr:false,watch:null,proxy:{'/api':{target:apiOrigin,changeOrigin:true},'/uploads':{target:apiOrigin,changeOrigin:true}}}});
 await server.listen();const browser=await chromium.launch({headless:true});const pages=[];
 try{for(const role of ['REQUESTER','MANAGER'])for(const width of [390,1280]){
  const token=process.env['HD_'+role+'_TOKEN'],headers={Authorization:'Bearer '+token,'X-Suite-Organization':process.env.HD_COMPANY,'X-Suite-Branch':process.env.HD_BRANCH};
  const page=await browser.newPage({viewport:{width,height:1000}});pages.push(page);const errors=[];page.on('pageerror',e=>errors.push(e.message));let managementReads=0,queue=Promise.resolve();const created=[];
  await page.route('**/api/v1/**',route=>{queue=queue.then(async()=>{
   const req=route.request(),url=new URL(req.url());
   if(url.pathname.endsWith('/access/settings/defaults/effective'))return route.fulfill({status:503,json:{detail:'Synthetic preferences outage'}});
   if(url.pathname.endsWith('/helpdesk/analytics')||url.pathname.endsWith('/helpdesk/sla/breaches'))managementReads++;
   const response=await route.fetch({url:apiOrigin+url.pathname+url.search,headers:{...req.headers(),...headers}});
   if(response.status()>=400)console.log('API',req.method(),url.pathname,response.status());
   if(req.method()==='POST'&&url.pathname.endsWith('/helpdesk/tickets')&&response.status()===201)created.push(await response.json());
   await route.fulfill({response});
  });return queue;});
  await page.route('**/hrms/helpdesk/live-qa',route=>route.fulfill({contentType:'text/html',body:`<html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script>window.__HD_QA__=${JSON.stringify({token,branch:process.env.HD_BRANCH,company:process.env.HD_COMPANY})}</script><script type="module">import R from'/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/.audit-helpdesk-live.tsx');</script></html>`}));
  await page.goto(server.resolvedUrls.local[0]+'hrms/helpdesk/live-qa',{waitUntil:'networkidle'});
  await expect(page.getByRole('button',{name:'Retry preferences',exact:true})).toBeVisible();
  if(role==='REQUESTER')expect(managementReads).toBe(0);else expect(managementReads).toBeGreaterThanOrEqual(2);
  await page.getByRole('button',{name:'New Ticket',exact:true}).click();const form=page.getByRole('dialog',{name:'Create support ticket',exact:true});
  const subject='Real Helpdesk '+role+' '+width;
  await form.getByLabel('Ticket subject').fill(subject);await form.getByRole('textbox',{name:'Description',exact:true}).fill('SQL-persisted ticket during preferences outage');
  await form.getByLabel('Ticket category').selectOption(process.env.HD_CATEGORY);
  await form.locator('.smart-create-footer').getByRole('button',{name:'Raise Ticket',exact:true}).click();
  await expect.poll(()=>created.length).toBe(1);await expect(form).toHaveCount(0);await expect(page.getByText(subject,{exact:true})).toBeVisible();
  const ticket=created[0];await page.getByText(subject,{exact:true}).click();
  if(role==='REQUESTER')await expect(page.getByLabel('Ticket status',{exact:true})).toHaveCount(0);
  else{await page.getByLabel('Ticket status',{exact:true}).selectOption('In Progress');await expect(page.getByLabel('Ticket status',{exact:true})).toHaveValue('In Progress');}
  const message='Persisted '+role+' reply '+width;
  const editor=page.getByRole('textbox',{name:'Ticket reply',exact:true});await editor.fill(message);
  const postedReply=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/helpdesk/tickets/'+ticket.id+'/reply')&&response.request().method()==='POST');
  await page.getByRole('button',{name:'Send ticket reply',exact:true}).click();const posted=await postedReply;expect(posted.status()).toBeGreaterThanOrEqual(200);expect(posted.status()).toBeLessThan(300);
  await expect.poll(()=>editor.evaluate(element=>element.matches('input,textarea')?element.value:element.textContent||'')).toBe('');
  await expect(page.getByText(message,{exact:true})).toBeVisible();
  const saved=await page.request.get(apiOrigin+'/api/v1/helpdesk/tickets/'+ticket.id,{headers});expect(saved.status()).toBe(200);const persisted=await saved.json();
  expect(persisted.subject).toBe(subject);expect(persisted.status).toBe(role==='MANAGER'?'In Progress':'Open');
  const replies=await page.request.get(apiOrigin+'/api/v1/helpdesk/tickets/'+ticket.id+'/replies',{headers});expect(replies.status()).toBe(200);expect((await replies.json()).some(r=>r.message.includes(message))).toBe(true);
  if(role==='REQUESTER')expect(managementReads).toBe(0);expect(errors).toEqual([]);console.log('PASS real Helpdesk '+role+' '+width+'px: preferences503, create, list, role policy, reply and fresh SQL-backed reads');await page.unrouteAll({behavior:'wait'});await queue;await page.close();
 }}finally{for(const page of pages)if(!page.isClosed())await page.unrouteAll({behavior:'wait'});await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(error=>{console.error(String(error?.stack||error).replace(/Bearer [A-Za-z0-9._-]+/g,'Bearer [fixture token]'));process.exitCode=1});

const fs=require('node:fs'),path=require('node:path'),{chromium,expect:base}=require('playwright/test');
const expect=base.configure({timeout:20000});
(async()=>{
 process.chdir(path.resolve(__dirname,'..'));const fixture=path.join(__dirname,'.audit-ai-permission-targets.tsx');
 fs.writeFileSync(fixture,`import React from'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Page from'@/pages/ai-agents/AiAgentPermissionsPage';import{useAuthStore}from'@/store/authStore';import'@/index.css';useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'qa',user:{id:1,email:'qa@example.com',role:'admin',is_superuser:true,access:{companyId:1,grants:{},modules:[]}}});window.switchCompany=()=>useAuthStore.setState({user:{...useAuthStore.getState().user,access:{...useAuthStore.getState().user.access,companyId:2}}});createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><Page/></MemoryRouter></QueryClientProvider>);`);
 const{createServer}=await import('vite');const server=await createServer({root:process.cwd(),server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();
 try{for(const width of[390,1280]){
  const page=await browser.newPage({viewport:{width,height:900}}),errors=[],writes=[];let failLookup=true,failSave=true,rules=[],release;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/v1/**',async r=>{const q=r.request(),u=new URL(q.url()),p=u.pathname;
   if(q.method()==='PUT'){writes.push(q.postDataJSON());if(failSave)return r.fulfill({status:503,json:{detail:'Synthetic save failure'}});await new Promise(resolve=>release=resolve);rules=q.postDataJSON().map((v,i)=>({...v,id:i+1}));return r.fulfill({headers:{'x-qa-save':'yes'},json:{status:'updated'}});}
   if(p.endsWith('/permission-targets')){if(failLookup)return r.fulfill({status:503,json:{detail:'Choices temporarily unavailable'}});const older=u.searchParams.get('page')==='2'||u.searchParams.get('search')==='Older';return r.fulfill({json:{roles:[{id:7,name:'Sales reviewer'}],users:[{id:older?22:11,name:older?'Older colleague':'Current colleague',email:older?'older@example.com':'current@example.com'}],selected_user:u.searchParams.get('selected_user')==='22'?{id:22,name:'Older colleague',email:'older@example.com'}:null,page:older?2:1,total:26,has_more:!older}});}
   if(p.endsWith('/permissions'))return r.fulfill({json:rules});
   return r.fulfill({json:[{id:5,name:'CRM assistant'}]});
  });
  await page.route('**/qa-permission-targets',r=>r.fulfill({contentType:'text/html',body:`<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from'/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/.audit-ai-permission-targets.tsx');</script>`}));
  await page.goto(server.resolvedUrls.local[0]+'qa-permission-targets');await page.getByRole('button',{name:'Add rule',exact:true}).click();
  await expect(page.getByRole('spinbutton')).toHaveCount(0);await expect(page.getByRole('alert')).toContainText('Could not load role and user choices');
  failLookup=false;await page.getByRole('button',{name:'Retry choices',exact:true}).click();await page.getByLabel('Role for rule 1',{exact:true}).selectOption('7');
  await page.getByRole('button',{name:'More users',exact:true}).click();await page.getByLabel('User for rule 1',{exact:true}).selectOption('22');
  await page.getByLabel('Find user for rule 1',{exact:true}).fill('Older');await expect(page.getByLabel('User for rule 1',{exact:true})).toHaveValue('22');
  await page.getByRole('button',{name:'Save',exact:true}).click();await expect.poll(()=>writes.length).toBe(1);await expect(page.getByRole('button',{name:'Save',exact:true})).toBeEnabled();
  await expect(page.getByLabel('User for rule 1',{exact:true})).toHaveValue('22');expect(writes[0][0].role_id).toBe(7);expect(writes[0][0].user_id).toBe(22);expect(writes[0][0].agent_id).toBe(5);
  failSave=false;await page.getByRole('button',{name:'Save',exact:true}).click();await expect.poll(()=>!!release).toBe(true);await page.evaluate(()=>window.switchCompany());await expect(page.getByLabel('User for rule 1',{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Add rule',exact:true}).click();await expect(page.getByLabel('User for rule 1',{exact:true})).toHaveValue('');const done=page.waitForResponse(r=>r.headers()['x-qa-save']==='yes');release();await(await done).finished();await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));await expect(page.getByLabel('User for rule 1',{exact:true})).toHaveValue('');expect(writes).toHaveLength(2);expect(errors).toEqual([]);await page.close();
 }console.log('PASS AI permission targets: named roles/users, lookup retry, pagination/search, retained failed save with exact IDs, company reset and late completion isolation at phone/desktop widths');}
 finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});

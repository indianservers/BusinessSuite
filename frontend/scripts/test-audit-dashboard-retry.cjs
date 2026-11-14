const fs=require('node:fs'),path=require('node:path'),{chromium,expect:base}=require('playwright/test');const expect=base.configure({timeout:20000});
(async()=>{
 process.chdir(path.resolve(__dirname,'..'));const fixture=path.join(__dirname,'.audit-dashboard-retry.tsx');
 fs.writeFileSync(fixture,`import React,{useState}from'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Studio from'@/features/access/DashboardStudio';import{useAuthStore}from'@/store/authStore';import'@/index.css';useAuthStore.setState({isHydrated:true,isAuthenticated:true,accessToken:'qa',user:{id:1,email:'qa@example.com',is_superuser:true,role:'admin'}});function Fixture(){const[error,setError]=useState('');const mutate=async(f,current=()=>true)=>{setError('');try{await f()}catch(e){if(current())setError(e.response?.data?.detail||'Lost response');}};return <>{error&&<p role="alert">{error}</p>}<Studio company={1} mutate={mutate}/></>;}createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><Fixture/></MemoryRouter></QueryClientProvider>);`);
 const{createServer}=await import('vite');const server=await createServer({root:process.cwd(),server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();
 try{for(const width of[390,1280]){
  const page=await browser.newPage({viewport:{width,height:900}}),errors=[],writes=[],layouts=new Map();let audits=0;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/v1/**',async route=>{const q=route.request(),url=new URL(q.url());
   if(q.method()==='PUT'){
    const data=q.postDataJSON();writes.push(data);let row=layouts.get(data.key);
    if(!(row&&row.version===data.version+1&&JSON.stringify(row.values_json)===JSON.stringify(data.values))){
      if(row&&row.version!==data.version)return route.fulfill({status:409,json:{detail:'Policy version changed'}});
      row={id:row?.id||layouts.size+1,version:(row?.version||0)+1,scope_key:`company:1:dashboard:${data.key}`,values_json:data.values};layouts.set(data.key,row);audits++;
    }
    if([1,3,5].includes(writes.length))return route.fulfill({status:503,json:{detail:'Response lost after commit'}});
    return route.fulfill({json:row});
   }
   return route.fulfill({json:url.pathname==='/api/v1/access/catalog'?{legacyRoles:[]}:[]});
  });
  await page.route('**/qa-dashboard-retry',route=>route.fulfill({contentType:'text/html',body:`<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from'/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/.audit-dashboard-retry.tsx');</script>`}));
  await page.goto(server.resolvedUrls.local[0]+'qa-dashboard-retry');const name=page.getByLabel('Dashboard name',{exact:true}),save=page.getByRole('button',{name:'Save layout',exact:true}),clone=page.getByRole('button',{name:'Clone',exact:true});
  await name.fill('Lost response layout');await save.click();await expect(page.getByRole('alert')).toHaveText('Response lost after commit');expect(layouts.size).toBe(1);
  await save.click();await expect(save).toBeEnabled();await expect(page.getByRole('alert')).toHaveCount(0);expect(writes[1].key).toBe(writes[0].key);expect(layouts.size).toBe(1);expect(audits).toBe(1);
  await name.fill('Edited layout');await save.click();await expect(page.getByRole('alert')).toHaveText('Response lost after commit');await save.click();await expect(save).toBeEnabled();await expect(page.getByRole('alert')).toHaveCount(0);expect(writes[3]).toEqual(writes[2]);expect(layouts.size).toBe(1);expect(audits).toBe(2);
  await clone.click();await expect(page.getByRole('alert')).toHaveText('Response lost after commit');await expect(name).toHaveValue('Edited layout');await clone.click();await expect(clone).toBeEnabled();await expect(name).toHaveValue('Edited layout copy');expect(writes[5]).toEqual(writes[4]);expect(writes[5].key).not.toBe(writes[0].key);expect(layouts.size).toBe(2);expect(audits).toBe(3);
  await clone.click();await expect.poll(()=>writes.length).toBe(7);await expect(clone).toBeEnabled();expect(writes[6].key).not.toBe(writes[5].key);expect(layouts.size).toBe(3);expect(audits).toBe(4);expect(errors).toEqual([]);await page.close();
 }console.log('PASS dashboard retry: committed create/edit/clone lost responses recover without duplicate layouts, versions or audit events; intentional subsequent clone gets a new identity at phone/desktop widths');}
 finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});

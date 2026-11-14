const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {chromium,expect}=require('playwright/test');
(async()=>{
 const root=path.resolve(__dirname,'..'),fixture=path.join(root,'.tmp-audit-catalog-fixture.tsx');
 fs.writeFileSync(fixture,`import React,{useState} from 'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{Toaster}from './src/components/ui/toaster';import './src/index.css';import CatalogEditor from './src/shared/catalog/CatalogEditor';import{useAuthStore}from './src/store/authStore';useAuthStore.setState({isHydrated:true,isAuthenticated:true,user:{id:1,email:'qa@example.test',role:'admin',is_superuser:true}});function Fixture(){const[open,setOpen]=useState(true);return <MemoryRouter>{open&&<CatalogEditor source="srm" close={()=>setOpen(false)} saved={item=>{window.saved=item;setOpen(false)}}/>}<Toaster/></MemoryRouter>;}createRoot(document.getElementById('root')).render(<Fixture/>);`);
 const {createServer}=await import('vite');const server=await createServer({root,server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();
 try{
 for(const width of[390,1280]){
 const page=await browser.newPage({viewport:{width,height:1000}}),errors=[],writes=[];let fail=true;page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',route=>{
  const req=route.request(),p=new URL(req.url()).pathname;
  if(p.endsWith('/branches/context'))return route.fulfill({json:{selected:1,default_branch_id:1,branches:[{id:1,name:'Audit branch',can_write:true,is_active:true}]}});
  if(p.endsWith('/follow-ups/options'))return route.fulfill({json:{employees:[],teams:[]}});
  if(p.endsWith('/catalog/items')&&req.method()==='POST'){const body=req.postDataJSON();writes.push(body);if(fail)return route.fulfill({status:503,json:{detail:'Catalog save unavailable'}});return route.fulfill({status:201,json:{...body,id:42,version:1}});}
  return route.fulfill({json:[]});
 });
 await page.route('**/qa-audit-catalog',route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div><script type="module" src="/.tmp-audit-catalog-fixture.tsx"></script>'}));
 await page.goto('http://127.0.0.1:'+server.httpServer.address().port+'/qa-audit-catalog');
 const dialog=page.getByRole('dialog'),price=dialog.getByLabel(/^Base price/);
 await dialog.getByLabel('Name',{exact:true}).fill('Audit item');await dialog.getByLabel('SKU / Code',{exact:true}).fill('QA-ITEM');await dialog.getByLabel('Unit',{exact:true}).fill('Nos');
 await price.fill('');await price.pressSequentially('-250');await expect(price).toHaveValue('-250');
 await dialog.getByRole('button',{name:'Save item',exact:true}).click();assert.equal(writes.length,0);await expect(price).toHaveValue('-250');
 await price.fill('250');await dialog.getByRole('button',{name:'Save item',exact:true}).click();await expect.poll(()=>writes.length).toBe(1);
 await expect(page.getByText('Item created',{exact:true})).toHaveCount(0);await expect(dialog.getByText('Catalog save unavailable',{exact:true})).toBeVisible();fail=false;await dialog.getByRole('button',{name:'Save item',exact:true}).click();await expect.poll(()=>writes.length).toBe(2);await expect(page.getByText('Item created',{exact:true})).toBeVisible();
 assert.equal(writes[1].price,250);await expect.poll(()=>page.evaluate(()=>window.saved?.id)).toBe(42);assert.deepEqual(errors,[]);
 await page.close();}
 console.log('PASS catalog creation toast only after successful retry, phone/desktop; price: negative typing retains sign, invalid price blocked, positive correction saved');
 }finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});

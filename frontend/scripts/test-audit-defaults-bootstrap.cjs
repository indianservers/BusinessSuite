const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {chromium,expect}=require('playwright/test');
(async()=>{
 const root=path.resolve(__dirname,'..'),fixture=path.join(root,'.tmp-audit-defaults-fixture.tsx');
 fs.writeFileSync(fixture,`import React,{useState}from'react';import{createRoot}from'react-dom/client';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Gate from './src/components/forms/FormDefaultsGate';import{useAuthStore}from './src/store/authStore';import{defaultText}from './src/lib/form-defaults';const user={id:1,email:'qa@example.test',role:'admin',is_superuser:true,access:{companyId:1}};useAuthStore.setState({user,isHydrated:true,isAuthenticated:true});window.switchCompany=()=>{sessionStorage.setItem('suite-organization','2');sessionStorage.removeItem('suite-branch');useAuthStore.setState({user:{...user,access:{companyId:2}}});};function Form(){const[currency]=useState(()=>defaultText('currency'));return <><h1>Defaults ready</h1><output data-testid="currency">{currency}</output></>};function App(){useAuthStore(s=>s.user);return <Gate><Form/></Gate>};createRoot(document.getElementById('root')).render(<React.StrictMode><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><App/></QueryClientProvider></React.StrictMode>);`);
 const {createServer}=await import('vite');const server=await createServer({root,server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();
 try{
 const page=await browser.newPage(),requests=[],errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',route=>{const company=Number(route.request().headers()['x-suite-organization']||1);requests.push({company,branch:route.request().headers()['x-suite-branch']});return route.fulfill({json:{companyId:company,branchId:company===1?11:22,values:{currency:company===1?'USD':'EUR'},modules:{}}});});
 await page.route('**/qa-defaults-bootstrap',route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div><script type="module" src="/.tmp-audit-defaults-fixture.tsx"></script>'}));
 await page.goto('http://127.0.0.1:'+server.httpServer.address().port+'/qa-defaults-bootstrap');
 await expect(page.getByRole('heading',{name:'Defaults ready',exact:true})).toBeVisible();await expect(page.getByTestId('currency')).toHaveText('USD');
 assert.equal(requests.filter(r=>r.company===1).length,1,'resolving the default branch must not fetch defaults twice');
 await page.evaluate(()=>window.switchCompany());await expect(page.getByTestId('currency')).toHaveText('EUR');assert.equal(requests.filter(r=>r.company===2).length,1);assert.deepEqual(errors,[]);
 const late=await browser.newPage();let release;
 late.on('pageerror',e=>errors.push(e.message));
 await late.route('**/api/**',async route=>{const company=Number(route.request().headers()['x-suite-organization']||1);if(company===1)await new Promise(resolve=>{release=resolve;});return route.fulfill({json:{companyId:company,branchId:company===1?11:22,values:{currency:company===1?'USD':'EUR'},modules:{}}});});
 await late.route('**/qa-defaults-bootstrap',route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div><script type="module" src="/.tmp-audit-defaults-fixture.tsx"></script>'}));
 await late.goto('http://127.0.0.1:'+server.httpServer.address().port+'/qa-defaults-bootstrap');await expect.poll(()=>typeof release).toBe('function');
 await late.evaluate(()=>window.switchCompany());await expect(late.getByTestId('currency')).toHaveText('EUR');release();await late.waitForLoadState('networkidle');
 await expect(late.getByTestId('currency')).toHaveText('EUR');assert.equal(await late.evaluate(()=>sessionStorage.getItem('suite-branch')),'22');assert.deepEqual(errors,[]);await late.close();
 console.log('PASS defaults bootstrap: one request per company despite default branch resolution and StrictMode; forms receive scoped defaults');
 }finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});

const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {chromium,expect}=require('playwright/test');
(async()=>{
 const root=path.resolve(__dirname,'..'),fixture=path.join(root,'.tmp-audit-lead-fixture.tsx');
 fs.writeFileSync(fixture,`import React,{useState}from'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import{LeadDrawer,CaptureDialog}from './src/apps/crm/leads/LeadManagementPage';import{useAuthStore}from './src/store/authStore';import './src/index.css';useAuthStore.setState({isHydrated:true,isAuthenticated:true,user:{id:1,email:'qa@example.test',role:'admin',is_superuser:true}});const bootstrap={settings:{stages:[{name:'New',required:[],allowedNext:[]}],slaHours:24,staleDays:7,preventDuplicates:false,assignment:{mode:'manual',ownerIds:[],rules:[]},sequences:[],workflows:[]},owners:[{id:1,name:'Audit owner'}],canManage:true,canAdmin:true,canAssign:true,userId:1};function App(){const[open,setOpen]=useState(true);if(new URLSearchParams(location.search).has("capture"))return <CaptureDialog bootstrap={bootstrap} close={()=>{}} saved={id=>{window.createdLead=id}}/>;return open?<LeadDrawer id={4} targetStage="" bootstrap={bootstrap} close={()=>{window.closedLead=true;setOpen(false)}} changed={()=>{}}/>:<p>Lead closed</p>};createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/crm/leads']}><App/></MemoryRouter></QueryClientProvider>);`);
 const {createServer}=await import('vite');const server=await createServer({root,server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();let page;
 try{
 page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[],writes=[],creates=[];
 let record={id:4,full_name:'Audit lead',company_name:'Audit company',job_title:'Manager',city:'Vijayawada',state:'Andhra Pradesh',country:'India',status:'New',email:'lead@example.com',estimated_value:100,owner_user_id:1,details:{priority:'High'},version:1,signals:{nextAction:'Schedule follow-up',followUpLabel:'Unscheduled'},customFields:[],timeline:[],activities:[]};
 let reject=true;
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',route=>{
  const req=route.request(),p=new URL(req.url()).pathname;
  if(p.endsWith('/crm/lead-management/leads')&&req.method()==='POST'){const body=req.postDataJSON();creates.push(body);return route.fulfill({status:201,json:{...record,...body.values,details:body.details,id:8}});}
  if(p.endsWith('/crm/lead-management/leads/4')&&req.method()==='PATCH'){
   const patch=req.postDataJSON();writes.push(patch);
   if(reject)return route.fulfill({status:422,json:{detail:[{loc:['body','values','city'],msg:'Choose a valid city'}]}});
   record={...record,...patch.values,details:{...record.details,...patch.details},version:record.version+1};return route.fulfill({json:record});
  }
  if(p.endsWith('/crm/lead-management/leads/4')||p.endsWith('/crm/leads/4'))return route.fulfill({json:record});
  if(p.includes('/record-360/'))return route.fulfill({status:503,json:{detail:'Record overview is excluded from this isolated edit test'}});
  return route.fulfill({json:{items:[],fields:[],customFields:[],lines:[],can_edit:false}});
 });
 await page.route('**/qa-audit-lead*',route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div><script type="module" src="/.tmp-audit-lead-fixture.tsx"></script>'}));
 await page.goto('http://127.0.0.1:'+server.httpServer.address().port+'/qa-audit-lead');
 const dialog=page.getByRole('dialog').first(),toolbar=dialog.locator('.lm-lead-save-toolbar');
 await toolbar.getByRole('button',{name:'Edit lead',exact:true}).click();
 await expect(dialog.getByLabel('Job Title',{exact:true})).toHaveValue('Manager');await expect(dialog.getByLabel('City',{exact:true})).toHaveValue('Vijayawada');await expect(dialog.getByLabel('Country',{exact:true})).toHaveValue('India');
 const amount=dialog.getByLabel('Estimated value',{exact:true});await amount.fill('-500');await toolbar.getByRole('button',{name:'Save changes',exact:true}).click();
 await expect(amount).toHaveAttribute('aria-invalid','true');await expect(dialog.getByText('Estimated value must be zero or greater.',{exact:true})).toBeVisible();assert.equal(writes.length,0);
 await amount.fill('250');await dialog.getByLabel('Job Title',{exact:true}).fill('Director');await dialog.getByLabel('City',{exact:true}).fill('Hyderabad');await dialog.getByLabel('Lead priority',{exact:true}).selectOption('Low');
 await toolbar.getByRole('button',{name:'Save changes',exact:true}).click();await expect(dialog.getByLabel('City',{exact:true})).toHaveAttribute('aria-invalid','true');await expect(dialog.getByText('Choose a valid city',{exact:true})).toBeVisible();
 reject=false;await dialog.getByLabel('City',{exact:true}).fill('Chennai');await toolbar.getByRole('button',{name:'Save changes',exact:true}).click();
 await expect(toolbar.getByRole('status')).toHaveText('All changes saved');await expect(toolbar.getByRole('button',{name:'Save changes',exact:true})).toBeDisabled();
 assert.equal(writes.at(-1).values.job_title,'Director');assert.equal(writes.at(-1).values.city,'Chennai');assert.equal(writes.at(-1).details.priority,'Low');
 const count=writes.length;await page.waitForTimeout(1700);assert.equal(writes.length,count,'manual save must not leave another autosave pending');
 await dialog.getByLabel('Job Title',{exact:true}).fill('Unsaved title');await page.keyboard.press('Escape');const confirm=page.getByRole('alertdialog');await expect(confirm).toBeVisible();await confirm.getByRole('button',{name:'Continue editing',exact:true}).click();await expect(dialog.getByLabel('Job Title',{exact:true})).toHaveValue('Unsaved title');
 await page.keyboard.press('Escape');await confirm.getByRole('button',{name:'Discard changes',exact:true}).click();await expect(page.getByText('Lead closed',{exact:true})).toBeVisible();
 await page.goto('http://127.0.0.1:'+server.httpServer.address().port+'/qa-audit-lead?capture');
 const capture=page.getByRole('dialog').first();
 await capture.getByRole('button',{name:'Next',exact:true}).click();await expect(capture.getByLabel('Lead Name *',{exact:true})).toHaveAttribute('aria-invalid','true');await expect(capture.getByRole('tab',{name:/Basic Details/})).toHaveAttribute('aria-selected','true');assert.equal(creates.length,0);
 await capture.getByLabel('Lead Name *',{exact:true}).fill('QA_TEST_CAPTURE_FIELDS');
 await capture.getByLabel('Priority',{exact:false}).selectOption('High');
 await capture.getByRole('button',{name:'Next',exact:true}).click();await capture.getByLabel('Job Title',{exact:true}).fill('Finance manager');
 await capture.getByLabel('Email',{exact:true}).fill('invalid-email');await capture.getByRole('button',{name:'Next',exact:true}).click();await expect(capture.getByLabel('Email',{exact:true})).toHaveAttribute('aria-invalid','true');await expect(capture.getByRole('tab',{name:/Contact Info/})).toHaveAttribute('aria-selected','true');assert.equal(creates.length,0);
 await capture.getByLabel('Email',{exact:true}).fill('capture@example.com');
 const capturePhone=capture.getByRole('textbox',{name:'Phone number',exact:true});await capturePhone.fill('1234');await capture.getByRole('button',{name:'Next',exact:true}).click();await expect(capturePhone).toHaveAttribute('aria-invalid','true');await expect(capture.getByRole('tab',{name:/Contact Info/})).toHaveAttribute('aria-selected','true');await capturePhone.fill('9876543210');
 await capture.getByRole('button',{name:'Next',exact:true}).click();await capture.getByRole('button',{name:'Next',exact:true}).click();
 await capture.getByLabel('City',{exact:true}).fill('Vijayawada');await capture.getByLabel('Country',{exact:true}).fill('India');
 await capture.getByRole('button',{name:'Create lead',exact:true}).click();await expect.poll(()=>page.evaluate(()=>window.createdLead)).toBe(8);
 assert.equal(creates[0].values.job_title,'Finance manager');assert.equal(creates[0].values.city,'Vijayawada');assert.equal(creates[0].values.country,'India');assert.equal(creates[0].details.priority,'High');assert(!String(creates[0].values.notes||'').includes('Priority:'));
 assert.deepEqual(errors,[]);console.log('PASS lead edit: job/location/priority fields, local and server validation, manual-save status, no duplicate autosave, Escape discard confirmation');
 }catch(e){if(page)console.error((await page.locator('body').innerText()).slice(-4500));throw e;}finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});


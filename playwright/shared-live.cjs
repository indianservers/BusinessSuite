const {chromium,expect}=require('../frontend/node_modules/playwright/test');
const path=require('path');
const bridge=process.env.CONTROL_BRIDGE;
if(!bridge||!bridge.startsWith('http://127.0.0.1:'))throw new Error('Isolated FastAPI test bridge required');
(async()=>{
 const browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1600,height:1100}});
 await context.addInitScript(()=>{window.__AI_HRMS_CONFIG__={apiBaseUrl:'/api/v1'};});
 await context.route('**/api/**',async route=>{try{const req=route.request(),url=new URL(req.url());const res=await context.request.fetch(bridge+url.pathname+url.search,{method:req.method(),headers:req.headers(),data:req.postDataBuffer()||undefined});await route.fulfill({response:res});}catch{await route.abort().catch(()=>{});}});
 const page=await context.newPage();
 const call=async(method,url,data)=>{const token=await page.evaluate(()=>JSON.parse(sessionStorage.getItem('hrms-auth')).state.accessToken);const response=await context.request.fetch(bridge+'/api/v1'+url,{method,data,headers:{Authorization:'Bearer '+token}});const body=await response.json();if(response.status()>=400)throw new Error(url+': '+response.status()+' '+JSON.stringify(body));return body;};
 const verify=async()=>{await page.getByLabel('Reason',{exact:true}).fill('Real browser shared-service verification');await page.getByLabel('Current administrator password',{exact:true}).fill('Admin@123456');await page.getByRole('button',{name:'Verify & Apply',exact:true}).click();await expect(page.getByRole('dialog')).toHaveCount(0);};
 try{
  await page.goto('http://127.0.0.1:5201/login');await page.getByPlaceholder('you@company.com').fill('testadmin@test.com');await page.getByPlaceholder('Enter your password').fill('Admin@123456');await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect.poll(()=>page.evaluate(()=>!!JSON.parse(sessionStorage.getItem('hrms-auth')||'{}').state?.accessToken)).toBe(true);
  const people=await call('GET','/access/users?companyId=1');const serviceUser=people.items.find(u=>u.email==='access.employee@example.com');expect(serviceUser.managed).toBe(true);
  for(const section of ['services','connections','webhooks','ai','delivery','documents','settings']){await page.goto('http://127.0.0.1:5201/admin/control/services/'+section);await expect(page.getByLabel('Loading shared services')).toHaveCount(0);if(await page.locator('.cc-error').count())throw new Error(section+': '+await page.locator('.cc-error').textContent());}
  await page.goto('http://127.0.0.1:5201/admin/control/services/workflows');await expect(page.getByRole('button',{name:'Save Draft',exact:true})).toBeVisible();
  await page.getByLabel('Name',{exact:true}).fill('Browser central lead alert');await page.getByLabel('Execution identity',{exact:true}).selectOption(String(serviceUser.id));
  await page.locator('.ss-palette').getByRole('button',{name:'notification',exact:true}).click();
  await page.getByLabel('Node configuration JSON').fill(JSON.stringify({recipientId:serviceUser.id,title:'Browser verified central notification',message:'Delivered by the shared workflow service'}));await page.getByRole('button',{name:'Apply Configuration',exact:true}).click();
  const port=page.getByRole('button',{name:/^Connect notification_/});const label=await port.getAttribute('aria-label');
  await page.getByRole('button',{name:'Connect start',exact:true}).click();await port.click();await port.click();await page.getByRole('button',{name:'Connect end',exact:true}).click();
  const grip=page.getByRole('button',{name:label.replace('Connect','Move'),exact:true});const box=await grip.boundingBox();await page.mouse.move(box.x+7,box.y+7);await page.mouse.down();await page.mouse.move(box.x-180,box.y+180,{steps:12});await page.mouse.up();await page.waitForTimeout(100);
  const validation=page.waitForResponse(r=>r.url().includes('/graph/validate'));await page.getByRole('button',{name:'Validate Preview',exact:true}).click();const validationResponse=await validation;if(!validationResponse.ok())throw new Error(JSON.stringify(await validationResponse.json())+' '+validationResponse.request().postData());await expect(page.getByText('Graph valid. No business action was executed.',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Save Draft',exact:true}).click();await verify();
  await page.getByRole('button',{name:'Publish',exact:true}).click();await verify();
  await page.reload();await expect(page.getByRole('option',{name:/Browser central lead alert/})).toHaveCount(1);
  const nativeLead=await call('POST','/crm/lead-management/leads',{values:{full_name:'Actual browser event lead'}});expect(nativeLead.id).toBeGreaterThan(0);
  await page.goto('http://127.0.0.1:5201/admin/control/services/executions');await page.getByRole('button',{name:'Process Queue',exact:true}).click();await verify();
  await expect(page.getByRole('cell',{name:'completed',exact:true})).toBeVisible();
  const delivery=await call('GET','/access/services/delivery?companyId=1');expect(delivery.some(d=>d.userId===serviceUser.id&&d.channel==='in_app'&&d.status==='delivered')).toBe(true);
  const workflows=await call('GET','/access/services/workflows?companyId=1');const created=workflows.find(w=>w.name==='Browser central lead alert');expect(created.published_version).toBe(1);expect(created.graph_json.nodes.find(n=>n.type==='notification').x).not.toBe(560);
  await page.goto('http://127.0.0.1:5201/admin/control/services/workflows');await page.getByLabel('Select workflow').selectOption(String(created.id));await page.locator('.ss-editor').screenshot({path:path.resolve('../docs/qa/suite-access/phase2-workflow-editor.png'),animations:'disabled'});
  await page.setViewportSize({width:390,height:844});await page.goto('http://127.0.0.1:5201/admin/control/services/services');await expect(page.getByLabel('Loading shared services')).toHaveCount(0);await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await page.screenshot({path:path.resolve('../docs/qa/suite-access/phase2-mobile.png'),animations:'disabled'});
  console.log('Real browser login, shared governance pages, node configuration, drag/connect, validation, database save/publish/reload, native CRM outbox event, durable execution and actual in-app delivery passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exit(1);});

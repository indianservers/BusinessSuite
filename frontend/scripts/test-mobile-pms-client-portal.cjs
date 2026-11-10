const fs=require('node:fs/promises'),path=require('node:path'),cp=require('node:child_process'),assert=require('node:assert/strict');const {chromium,expect:baseExpect}=require('playwright/test');const expect=baseExpect.configure({timeout:15000});
(async()=>{process.chdir(path.resolve(__dirname,'..'));const {createServer}=await import('vite');const out=path.resolve('../outputs/mobile-ux'),pin=(await fs.readFile(path.join(out,'pms-client-portal-capabilities.md'),'utf8')).match(/baseline pin (\w+)/)[1],scratch=['scripts/fixtures/pms-client-portal-before.tsx','scripts/fixtures/mobile-pms-client-portal-before.tsx'];let browser,server;
try{await fs.writeFile(scratch[0],cp.execFileSync('git',['show',pin+':frontend/src/apps/project-management/pages/ClientPortalPage.tsx'],{encoding:'utf8'}).replace('"../services/api"','"@/apps/project-management/services/api"').replace('"../types"','"@/apps/project-management/types"'));await fs.writeFile(scratch[1],(await fs.readFile('scripts/fixtures/mobile-pms-client-portal.tsx','utf8')).replace('"@/apps/project-management/pages/ClientPortalPage"','"./pms-client-portal-before"'));server=await createServer({server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:390,height:1000}}),errors=[],writes=[],reads=[];let fail=false,hold=false,release;let sourceFailure="",emptySource=false;let holdRead=false,releaseRead,readCaptured=false,omitMilestone=false;let actor=1;const states={42:'Pending',43:'Pending'},title='Delivery '+ 'Milestone'.repeat(13),filename='Client-deliverable-'+ 'filename'.repeat(15)+'.pdf';
const milestone=(id,owner=actor)=>({id,project_id:id===42?86:87,name:owner===1?(id===42?title:'Second client milestone'):('Actor '+owner+' '+(id===42?title:'Second client milestone')),client_approval_status:states[id],progress_percent:id===42?37:80,due_date:'2026-11-20'});
page.on('pageerror',e=>errors.push(e.message));await page.route('**/api/v1/**',async route=>{const req=route.request(),url=new URL(req.url()),p=url.pathname;if(req.method()!=='GET'){const requestActor=actor;writes.push({method:req.method(),path:p,body:req.postDataJSON()});const denied=fail;if(hold){hold=false;await new Promise(resolve=>release=resolve);}if(denied){await route.fulfill({status:403,json:{detail:'Client approval denied'}});return;}const id=Number(p.match(/milestones\/(\d+)/)[1]);states[id]=p.endsWith('/approve')?'Approved':'Rejected';await route.fulfill({json:milestone(id,requestActor)});return;}reads.push(url.pathname+url.search);
if(sourceFailure&&((sourceFailure==='projects'&&p.endsWith('/projects'))||(sourceFailure==='children'&&(p.includes('/86/milestones')||(p.endsWith('/files')&&url.searchParams.get('project_id')==='87'))))){await route.fulfill({status:503,json:{detail:'Portal source unavailable'}});return;}
let data=[];if(p.endsWith('/projects'))data=[{id:86,status:'Active',is_client_visible:false},{id:87,status:'Archived',is_client_visible:true},{id:88,status:'Archived',is_client_visible:false}];else if(p.includes('/milestones')){assert.ok(p.includes('/86/')||p.includes('/87/'));assert.equal(url.searchParams.get('skip'),'0');assert.equal(url.searchParams.get('limit'),'100');data=[milestone(p.includes('/86/')?42:43)];}else if(p.endsWith('/files')){assert.ok(['86','87'].includes(url.searchParams.get('project_id')));data=url.searchParams.get('project_id')==='86'?[{id:1,project_id:86,original_name:actor===1?filename:'Actor '+actor+' '+filename,visibility:'Client Visible',created_at:'2026-11-10'},{id:2,project_id:86,original_name:'Private asset',visibility:'Private',created_at:'2026-11-10'}]:[];}if(omitMilestone&&p.includes('/86/milestones'))data=[];
if(holdRead&&p.includes('/86/milestones')){holdRead=false;readCaptured=true;await new Promise(resolve=>releaseRead=resolve);}
await route.fulfill({json:emptySource?[]:data});});
await page.route('**/portal-qa*',r=>r.fulfill({contentType:'text/html',body:'<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/'+(r.request().url().includes('before')?'mobile-pms-client-portal-before':'mobile-pms-client-portal')+'.tsx");</script>'}));const origin='http://127.0.0.1:'+server.httpServer.address().port;const open=async(width,before=false)=>{await page.setViewportSize({width,height:1000});await page.goto(origin+'/portal-qa'+(before?'?before':''));await expect(page.getByText(filename,{exact:true})).toBeVisible();await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();};
if(process.env.CLIENT_PORTAL_BEFORE_QA){await open(390,true);hold=true;release=undefined;await page.getByRole('button',{name:'Approve',exact:true}).first().click();await expect.poll(()=>typeof release).toBe('function');await page.getByRole('button',{name:'Approve',exact:true}).first().click();await expect.poll(()=>writes.length).toBe(2);release();console.log('REPRO original390 repeated approval while first request held issued2POSTs. Mock only.');return;}
if(process.env.CLIENT_PORTAL_CONTEXT_QA){
for(const width of [320,360,375,390,414,430,480]){
 actor=1;states[42]=states[43]='Pending';await open(width);
 hold=true;release=undefined;await page.locator('[data-milestone-id="42"]').getByRole('button',{name:'Approve',exact:true}).click();await expect.poll(()=>typeof release).toBe('function');
 holdRead=true;readCaptured=false;actor=2;await page.evaluate(()=>window.portalActor(2));
 await expect.poll(()=>readCaptured).toBe(true);
 await expect(page.getByRole('heading',{name:title,exact:true})).toHaveCount(0);
 await expect(page.getByText(filename,{exact:true})).toHaveCount(0);
 await expect(page.getByRole('status').filter({hasText:'Loading milestone approvals'})).toBeVisible();releaseRead();
 await expect(page.getByRole('heading',{name:'Actor 2 '+title,exact:true})).toBeVisible();
 await expect(page.getByText('Actor 2 '+filename,{exact:true})).toBeVisible();
 const settled=await page.evaluate(()=>window.portalSettled());release();await expect.poll(()=>page.evaluate(()=>window.portalSettled())).toBe(settled+1);
 await expect(page.locator('[data-milestone-id="42"]')).toContainText('Pending');
 await expect(page.getByRole('heading',{name:title,exact:true})).toHaveCount(0);
 states[42]='Pending';fail=true;hold=true;release=undefined;
 await page.locator('[data-milestone-id="42"]').getByRole('button',{name:'Reject',exact:true}).click();await expect.poll(()=>typeof release).toBe('function');
 actor=3;await page.evaluate(()=>window.portalActor(3));await expect(page.getByRole('heading',{name:'Actor 3 '+title,exact:true})).toBeVisible();
 const settledError=await page.evaluate(()=>window.portalSettled());release();await expect.poll(()=>page.evaluate(()=>window.portalSettled())).toBe(settledError+1);fail=false;
 await expect(page.getByRole('alert')).toHaveCount(0);
 await page.locator('[data-milestone-id="42"]').getByRole('button',{name:'Reject',exact:true}).click();await expect(page.locator('[data-milestone-id="42"]')).toContainText('Rejected');
 holdRead=true;readCaptured=false;await page.evaluate(()=>{window.refreshPortalDone=false;void window.refreshPortal().then(()=>window.refreshPortalDone=true);});await expect.poll(()=>readCaptured).toBe(true);
 actor=4;await page.evaluate(()=>window.portalActor(4));await expect(page.getByRole('heading',{name:'Actor 4 '+title,exact:true})).toBeVisible();
 releaseRead();await expect.poll(()=>page.evaluate(()=>window.refreshPortalDone)).toBe(true);
 await expect(page.getByRole('heading',{name:'Actor 3 '+title,exact:true})).toHaveCount(0);
 await expect(page.getByRole('heading',{name:'Actor 4 '+title,exact:true})).toBeVisible();
 for(const kind of ['branch','organization','tenant']){
  actor++;const current=actor;await page.evaluate(({kind,value})=>window.portalContext(kind,String(value)),{kind,value:width*10+current});
  await expect(page.getByRole('heading',{name:'Actor '+current+' '+title,exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Actor '+(current-1)+' '+title,exact:true})).toHaveCount(0);
 }
 const beforeSilent=writes.length;
 await page.evaluate(value=>sessionStorage.setItem('suite-branch',value),String(width*100));
 await page.locator('[data-milestone-id="42"]').getByRole('button',{name:'Approve',exact:true}).dispatchEvent('click');assert.equal(writes.length,beforeSilent);
 actor=8;await page.evaluate(()=>window.dispatchEvent(new Event('suite:branch-changed')));
 await expect(page.getByRole('heading',{name:'Actor 8 '+title,exact:true})).toBeVisible();
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
}
assert.equal(writes.length,21);assert.deepEqual(errors,[]);console.log('PASS client portal context7phones actor changes/late successful+403 action results/late reads ignored/current action usable/branch+organization+tenant reset;21mockPOSTs.');return;
}
if(process.env.CLIENT_PORTAL_RACE_QA){
for(const width of [320,360,375,390,414,430,480]){
 for(const action of ['Approve','Reject']){
  states[42]=states[43]='Pending';await open(width);const row=page.locator('[data-milestone-id="42"]');
  hold=true;release=undefined;await row.getByRole('button',{name:action,exact:true}).click();await expect.poll(()=>typeof release).toBe('function');
  holdRead=true;releaseRead=undefined;readCaptured=false;
  await page.evaluate(()=>{window.refreshPortalDone=false;void window.refreshPortal().then(()=>window.refreshPortalDone=true);});
  await expect.poll(()=>readCaptured).toBe(true);
  release();await expect.poll(()=>states[42]).toBe(action==='Approve'?'Approved':'Rejected');
  // Ensure the mutation response has reached React before releasing the older snapshot.
  await page.waitForTimeout(100);releaseRead();await expect.poll(()=>page.evaluate(()=>window.refreshPortalDone)).toBe(true);
  await expect(row).toContainText(action==='Approve'?'Approved':'Rejected');
  await expect(page.locator('.pms-portal-metrics')).toContainText('Approval items1');
  await expect(page.locator('[data-milestone-id="43"]')).toContainText('Pending');
  // A later read must still be allowed to reflect a subsequent server change.
  states[42]='Pending';await page.evaluate(()=>window.refreshPortal());await expect(row).toContainText('Pending');
  await expect(page.locator('.pms-portal-metrics')).toContainText('Approval items2');
 }
 states[42]=states[43]='Pending';await open(width);
 hold=true;release=undefined;await page.locator('[data-milestone-id="42"]').getByRole('button',{name:'Approve',exact:true}).click();await expect.poll(()=>typeof release).toBe('function');
 holdRead=true;readCaptured=false;omitMilestone=true;
 await page.evaluate(()=>{window.refreshPortalDone=false;void window.refreshPortal().then(()=>window.refreshPortalDone=true);});
 await expect.poll(()=>readCaptured).toBe(true);omitMilestone=false;release();await expect.poll(()=>states[42]).toBe('Approved');
 await page.waitForTimeout(100);releaseRead();await expect.poll(()=>page.evaluate(()=>window.refreshPortalDone)).toBe(true);
 await expect(page.locator('[data-milestone-id="42"]')).toHaveCount(0);
 await expect(page.locator('.pms-portal-metrics')).toContainText('Approval items1');
 await page.evaluate(()=>window.refreshPortal());await expect(page.locator('[data-milestone-id="42"]')).toContainText('Approved');
}
assert.equal(writes.length,21);assert.deepEqual(errors,[]);console.log('PASS client portal race7phones both actions21mockPOST: pre-ack stale GET cannot overwrite completed action; later GET remains authoritative, sibling status/KPI retained, omitted record never resurrected.');return;
}
if(process.env.CLIENT_PORTAL_SOURCE_QA){
for(const width of [320,360,375,390,414,430,480]){
 await page.setViewportSize({width,height:1000});sourceFailure='projects';await page.goto(origin+'/portal-qa');
 await expect(page.getByRole('alert')).toContainText('Portal source unavailable');
 await expect(page.locator('.pms-portal-metrics')).toContainText('Visible projects—');
 await expect(page.getByText('No shared files available.',{exact:true})).toHaveCount(0);
 sourceFailure='children';await page.getByRole('button',{name:'Retry projects',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Second client milestone',exact:true})).toBeVisible();
 await expect(page.getByText(filename,{exact:true})).toBeVisible();
 await expect(page.getByRole('heading',{name:title,exact:true})).toHaveCount(0);
 await expect(page.locator('.pms-portal-metrics')).toContainText('Visible projects2');
 await expect(page.locator('.pms-portal-metrics')).toContainText('Approval items—');
 await expect(page.locator('.pms-portal-metrics')).toContainText('Shared files—');
 if(width===390)await page.screenshot({path:path.join(out,'pms-client-portal-partial-error-390.png'),fullPage:true});
 const before=reads.length;sourceFailure='';
 await page.getByRole('button',{name:'Retry milestone approvals',exact:true}).click();
 await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();
 assert.deepEqual(reads.slice(before),['/api/v1/project-management/projects/86/milestones?skip=0&limit=100']);
 await expect(page.locator('.pms-portal-metrics')).toContainText('Approval items2');
 const beforeFiles=reads.length;await page.getByRole('button',{name:'Retry shared files',exact:true}).click();
 await expect(page.locator('.pms-portal-metrics')).toContainText('Shared files1');
 assert.deepEqual(reads.slice(beforeFiles),['/api/v1/project-management/files?project_id=87']);
 await expect(page.getByRole('alert')).toHaveCount(0);
 assert.deepEqual(await page.locator('[data-milestone-id]').evaluateAll(rows=>rows.map(row=>row.getAttribute('data-milestone-id'))),['42','43']);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 if(width===390)await page.screenshot({path:path.join(out,'pms-client-portal-source-390.png'),fullPage:true});
 emptySource=true;await page.goto(origin+'/portal-qa');
 await expect(page.getByText('No projects available.',{exact:true})).toBeVisible();
 await expect(page.getByText('No milestone approvals available.',{exact:true})).toBeVisible();
 await expect(page.getByText('No shared files available.',{exact:true})).toBeVisible();emptySource=false;
}
assert.equal(writes.length,0);assert.deepEqual(errors,[]);console.log('PASS client portal source7phones project503/unknown counts/retry, partial child failures preserve successful sections, failed-only endpoint retries, verified empty/nooverflow/zero writes.');return;
}
for(const width of [320,360,375,390,414,430,480]){states[42]=states[43]='Pending';await open(width);await expect(page.getByText('Private asset',{exact:true})).toHaveCount(0);const metrics=page.locator('.pms-portal-metrics');await expect(metrics).toContainText('Visible projects2');await expect(metrics).toContainText('Approval items2');await expect(metrics).toContainText('Shared files1');assert.ok((await metrics.boundingBox()).height<=110);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));const first=page.locator('[data-milestone-id="42"]'),second=page.locator('[data-milestone-id="43"]');for(const label of ['Approve','Reject'])assert.ok((await first.getByRole('button',{name:label,exact:true}).boundingBox()).height>=44);const before=writes.length;fail=true;hold=true;release=undefined;await first.getByRole('button',{name:'Approve',exact:true}).click();await expect.poll(()=>typeof release).toBe('function');await expect(first).toHaveAttribute('aria-busy','true');for(const label of ['Approve','Reject'])await expect(first.getByRole('button',{name:label,exact:true})).toBeDisabled();await first.getByRole('button',{name:'Approve',exact:true}).dispatchEvent('click');await first.getByRole('button',{name:'Reject',exact:true}).dispatchEvent('click');assert.equal(writes.length,before+1);fail=false;await second.getByRole('button',{name:'Reject',exact:true}).click();await expect(second).toContainText('Rejected');assert.deepEqual(writes.at(-1),{method:'POST',path:'/api/v1/project-management/milestones/43/reject',body:{status:'Rejected',remarks:'Client requested changes from portal.'}});release();await expect(first.getByRole('alert')).toContainText('Client approval denied');await expect(first).toContainText('Pending');await expect(first).toContainText('Due 20/11/2026 - 37% complete');await expect(page.locator('.pms-portal-file').getByText('10/11/2026',{exact:true})).toBeVisible();await first.getByRole('button',{name:'Approve',exact:true}).click();await expect(first).toContainText('Approved');await expect(first.getByRole('alert')).toHaveCount(0);assert.equal(writes.at(-1).path,'/api/v1/project-management/milestones/42/approve');assert.equal(writes.at(-1).body,null);await expect(metrics).toContainText('Approval items0');assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));if(width===390)await page.screenshot({path:path.join(out,'pms-client-portal-390.png'),fullPage:true,animations:'disabled'});}
states[42]=states[43]='Pending';const geometry=()=>page.locator('body #root>div').evaluate(e=>Array.from(e.querySelectorAll('h1,h2,h3,p,button')).map(n=>{const r=n.getBoundingClientRect();return[n.tagName,n.textContent,Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)];}));for(const width of [481,768,1024,1440]){await open(width,true);const original=await geometry();await open(width);assert.deepEqual(await geometry(),original,'Desktop geometry '+width);}
assert.equal(writes.length,21);assert.deepEqual(errors,[]);console.log('PASS client portal7phones original project/file visibility/read params/all metrics+full metadata/compact metrics/44px/nooverflow/per-row held singleflight/opposite lock/independent row reject/403 retention+retry/exact approve+reject21mockPOST;4desktop pinned geometry.');
}finally{await browser?.close();await server?.close();await Promise.all(scratch.map(p=>fs.rm(p,{force:true})));}})().catch(e=>{console.error(e);process.exitCode=1;});

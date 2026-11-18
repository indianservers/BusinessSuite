const {chromium,expect}=require('playwright/test');
const path=require('node:path');
(async()=>{
 const {createServer}=await import('vite');
 const server=await createServer({root:path.resolve(__dirname,'..'),server:{host:'127.0.0.1',port:0}});await server.listen();
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  let links=[],readonly=false,deny=false,lastBody;
  await page.route('**/api/v1/project-management/task-workspace/tasks/1/**',async route=>{
   const request=route.request(),url=new URL(request.url());
   if(url.pathname.endsWith('/crm-link-options'))return route.fulfill({json:{items:[{id:11,name:url.searchParams.get('kind')==='lead'?'Existing prospect':'Existing contact'}],next:null}});
   if(request.method()==='POST'){
    if(deny)return route.fulfill({status:403,json:{detail:'Task edit access was removed'}});
    lastBody=request.postDataJSON();const row={id:links.length+1,kind:lastBody.kind,record_id:lastBody.record_id,name:lastBody.kind==='lead'?'Existing prospect':'Existing contact',url:`/crm/${lastBody.kind}s/11`};links.push(row);return route.fulfill({json:row});
   }
   if(request.method()==='DELETE'){links=links.filter(row=>row.id!==Number(url.pathname.split('/').pop()));return route.fulfill({json:{ok:true}});}
   return route.fulfill({json:{items:links,can_manage:!readonly}});
  });
  await page.addInitScript(()=>{window.recordMutations=0;window.addEventListener('suite:record-mutated',()=>window.recordMutations++);});
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/record-360-qa.html?links=1`);
  await page.getByRole('combobox',{name:'Search contact',exact:true}).fill('Existing');
  await page.getByRole('option',{name:'Existing contact',exact:true}).click();
  await expect(page.getByRole('link',{name:'Existing contact · contact'})).toHaveAttribute('href','/crm/contacts/11');
  await page.getByRole('button',{name:'Unlink Existing contact'}).click();
  await expect(page.getByRole('link',{name:'Existing contact · contact'})).toHaveCount(0);
  await page.getByLabel('CRM link type').selectOption('lead');
  await page.getByRole('combobox',{name:'Search lead',exact:true}).fill('Existing');
  await page.getByRole('option',{name:'Existing prospect',exact:true}).click();
  expect(lastBody).toEqual({kind:'lead',record_id:11});
  await expect(page.getByRole('link',{name:'Existing prospect · lead'})).toBeVisible();
  deny=true;
  await page.getByRole('combobox',{name:'Search lead',exact:true}).fill('Existing');
  await page.getByRole('option',{name:'Existing prospect',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Task edit access was removed');
  expect(links).toHaveLength(1);
  expect(await page.evaluate(()=>window.recordMutations)).toBe(3);
  readonly=true;await page.reload();
  await expect(page.getByRole('link',{name:'Existing prospect · lead'})).toBeVisible();
  await expect(page.getByLabel('CRM link type')).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Unlink Existing prospect'})).toHaveCount(0);
  expect(errors).toEqual([]);console.log('Task CRM links: existing picker, contact/lead links, unlink, permission failure and read-only rendering passed.');
 }finally{await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

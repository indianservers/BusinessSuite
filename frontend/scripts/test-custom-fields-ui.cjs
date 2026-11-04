const path=require('node:path');
const fs=require('node:fs/promises');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const {createServer}=await import('vite');const react=(await import('@vitejs/plugin-react')).default;
 const root=path.resolve(__dirname,'..');
 const server=await createServer({configFile:false,root,plugins:[react(),{name:'custom-fields-qa',configureServer(server){server.middlewares.use(async(req,res,next)=>{if(req.url.startsWith('/custom-fields-qa')){res.setHeader('Content-Type','text/html');res.end(await server.transformIndexHtml(req.url,'<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"/></head><body><div id="root"></div><script type="module" src="/scripts/fixtures/custom-fields-ui-qa.tsx"></script></body></html>'));}else next();});}}],resolve:{alias:{'@':path.join(root,'src')},dedupe:['react','react-dom']},server:{host:'127.0.0.1',port:0},optimizeDeps:{entries:['scripts/fixtures/custom-fields-ui-qa.tsx']}});
 await server.listen();const base=`http://127.0.0.1:${server.httpServer.address().port}`;
 const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let fields=[{id:1,entityType:'leads',fieldName:'Service line',fieldKey:'service_line',fieldType:'radio',isVisible:true,isRequired:false,options:['Audit','Tax'],position:1}];let writes=0;
 await page.route('**/api/v1/crm/custom-fields**',async route=>{const req=route.request();if(req.method()==='GET')return route.fulfill({json:{items:fields,total:fields.length}});writes++;const body=req.postDataJSON();if(req.method()==='POST')fields.push({...body,id:fields.length+1});else fields=fields.map(f=>String(f.id)===new URL(req.url()).pathname.split('/').pop()?{...f,...body}:f);await route.fulfill({json:fields.at(-1)});});
 const output=path.resolve(root,'../docs/qa/custom-fields-upgrade');await fs.mkdir(output,{recursive:true});
 try{
  await page.goto(`${base}/custom-fields-qa?controls`);
  await page.getByRole('radio',{name:'Tax',exact:true}).check();
  await page.getByRole('combobox',{name:'Region',exact:true}).click();await page.getByLabel('Search Region').fill('beng');await page.getByRole('option',{name:'Bengaluru',exact:true}).click();
  await page.getByRole('combobox',{name:'Interests',exact:true}).click();await page.getByRole('option',{name:'Audit',exact:true}).click();await page.getByRole('option',{name:'Tax',exact:true}).click();await page.keyboard.press('Escape');
  await page.getByRole('textbox',{name:'Reference',exact:true}).fill('CLIENT-1');
  const values=JSON.parse(await page.getByLabel('Saved values').innerText());assert.deepEqual(values.multi_select,['Audit','Tax']);assert.equal(values.combobox,'Bengaluru');assert.equal(values.number,0);assert.equal(values.checkbox,false);assert.equal(await page.getByTestId('placement').innerText(),'false');
  await page.screenshot({path:path.join(output,'controls-desktop.png'),fullPage:true});
  await page.goto(`${base}/custom-fields-qa`);await page.getByRole('heading',{name:'Service line',exact:true}).waitFor();await page.getByRole('button',{name:'Edit',exact:true}).click();await page.getByLabel('Field name').fill('Service category');assert.equal(writes,0);await page.getByRole('button',{name:'Cancel',exact:true}).click();assert.equal(writes,0);
  await page.getByRole('button',{name:'Add field',exact:true}).click();await page.getByLabel('Field name').fill('Region');await page.getByLabel('Field type').selectOption('combobox');await page.getByLabel('Options, one per line').fill('Hyderabad\nBengaluru');await page.getByLabel('Record detail view',{exact:true}).uncheck();await page.screenshot({path:path.join(output,'editor-desktop.png'),fullPage:true});await page.getByRole('button',{name:'Save field',exact:true}).click();await page.getByRole('heading',{name:'Region',exact:true}).waitFor();assert.equal(writes,1);assert.deepEqual(fields.at(-1).options.values,['Hyderabad','Bengaluru']);assert(!fields.at(-1).options.ui.places.includes('detail'));
  await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Add field',exact:true}).click();await page.screenshot({path:path.join(output,'editor-mobile.png'),fullPage:true});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);console.log('Custom field controls, search, multi-select, zero/false, placement and explicit save passed; desktop/mobile screenshots saved.');
 }finally{await browser.close();await server.close();}
})().catch(e=>{console.error(e);process.exit(1);});

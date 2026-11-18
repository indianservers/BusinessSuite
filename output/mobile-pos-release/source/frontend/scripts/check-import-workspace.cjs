// Run Vite on 127.0.0.1:5191. Every API request uses an isolated fixture.
const {chromium}=require('../node_modules/playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const specs=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../outputs/import-workspace/import-catalog.json'),'utf8'));
const output=path.resolve(__dirname,'../../docs/qa/import-workspace');fs.mkdirSync(output,{recursive:true});
(async()=>{const browser=await chromium.launch({headless:true});const results=[];
try{for(const width of [1440,390])for(const module of ['crm','srm','hrms','pms','fam']){
 const page=await browser.newPage({viewport:{width,height:1000}}),errors=[];page.on('pageerror',error=>errors.push(error.message));
 const catalog=specs.filter(spec=>spec.module===module);let batch;const history=[];
 const spec=catalog[0],headers=spec.fields.map(field=>field.key),values=spec.fields.map(field=>field.sample);
 const table={headers,rows:[values],rowNumbers:[2],sheets:['Data','Other'],sheet:'Data',total:1,headerRow:1};
 await page.route('**/api/**',async route=>{const url=new URL(route.request().url()).pathname;let data={};const body=route.request().postDataJSON?.bind(route.request());
  if(url.endsWith('/catalog'))data=catalog;
  else if(url.endsWith('/history'))data=history;
  else if(url.endsWith('/connections'))data={providers:[{key:'quickbooks',label:'QuickBooks Online',configured:false},{key:'zoho',label:'Zoho Books',configured:false}],connections:[]};
  else if(url.endsWith('/inspect'))data=table;
  else if(url.endsWith('/upload')){batch={id:'fixture',module,entity:spec.key,filename:'sample.csv',source:'spreadsheet',status:'uploaded',version:1,table,mapping:{},options:{},counts:{},created_at:'2026-11-04T10:00:00Z'};history.push(batch);data=batch;}
  else if(url.endsWith('/preview')){const payload=body();assert.ok(Object.keys(payload.mapping).length>0,'Mapping must be sent before preview');batch={...batch,mapping:payload.mapping,options:payload,version:batch.version+1,status:'previewed',counts:{create:1},preview:{total:1,can_import:true,counts:{create:1},rows:[{row:2,action:'create',values:Object.fromEntries(headers.map((key,index)=>[key,values[index]])),errors:[],suggestions:['Trim surrounding spaces']}]}};history[0]=batch;data=batch;}
  else if(url.endsWith('/commit')){assert.equal(body().version,batch.version);batch={...batch,status:'imported',version:batch.version+1};history[0]=batch;data=batch;}
  else if(url.endsWith('/revoke')){batch={...batch,status:'revoked',version:batch.version+1};history[0]=batch;data=batch;}
  else if(url.endsWith('/retry')){batch={...batch,id:'retry-fixture',status:'uploaded',version:1,preview:undefined};data=batch;}
  else if(url.includes('/batches/'))data=batch;
  await route.fulfill({json:data});
 });
 await page.goto(`http://127.0.0.1:5191/import-ui-qa.html?module=${module}`);
 await page.getByRole('heading',{name:'What would you like to import?'}).waitFor();
 assert.equal(await page.locator('.iw-types>button').count(),3);
 if(module==='fam'){assert.ok(await page.getByRole('button',{name:'Connect QuickBooks Online'}).isDisabled());}
 await page.locator('input[type=file]').setInputFiles({name:'sample.csv',mimeType:'text/csv',buffer:Buffer.from(headers.join(',')+'\n'+values.join(','))});
 await page.getByRole('button',{name:'Continue to mapping'}).click();
 await page.getByRole('heading',{name:/Match spreadsheet columns/}).waitFor();
 assert.equal(await page.getByLabel(`Map ${headers[0]}`,{exact:true}).inputValue(),headers[0]);
 await page.screenshot({path:path.join(output,`${module}-mapping-${width}.png`),fullPage:true});
 await page.getByRole('button',{name:'Preview import',exact:true}).click();
 const commit=page.getByRole('button',{name:'Import 1 new'});await commit.waitFor();assert.ok(await commit.isDisabled());
 await page.getByLabel('I reviewed the column mapping, cleaned values and duplicate decisions.').check();
 await page.screenshot({path:path.join(output,`${module}-preview-${width}.png`),fullPage:true});
 await commit.click();await page.getByRole('heading',{name:'Import complete',exact:true}).waitFor();
 await page.getByRole('button',{name:'View history',exact:true}).click();await page.getByRole('button',{name:'Revoke',exact:true}).click();
 await page.getByRole('radio',{name:'Revoke, remap columns and try again'}).check();await page.getByRole('button',{name:'Confirm revoke',exact:true}).click();
 await page.getByRole('heading',{name:/Match spreadsheet columns/}).waitFor();
 assert.equal(batch.status,'uploaded');
 assert.deepEqual(errors,[],`${module} runtime errors`);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,`${module} horizontal overflow at ${width}`);
 results.push({module,width,passed:true});console.log('Passed',module,width);await page.close();
}fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));}finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1;});

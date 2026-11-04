const fs=require('fs'),assert=require('node:assert/strict'),q=require('./custom_fields_live.cjs');
(async()=>{const a=await q.auth(),b=await q.browserContext(a),p=b.page,name='CLOUDUI-PMS-'+Date.now()+'.png';try{
await p.goto(q.origin+'/pms/files');
await p.locator('label').filter({hasText:/^Project\s/}).locator('select').selectOption(String(q.state.records.project.id));
await p.getByLabel('Upload project files',{exact:true}).setInputFiles({name,mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64')});
await p.getByRole('status').filter({hasText:'1 file uploaded'}).waitFor();
const reg=await a.api('/files-storage/files?search='+name);assert.equal(reg.items[0].status,'cloud');assert.equal(reg.items[0].module,'pms');
await p.screenshot({path:'docs/qa/files-storage/cloud-pms-upload-ui.png',fullPage:true});assert.deepEqual(b.errors,[]);
fs.writeFileSync('docs/qa/files-storage/cloud-pms-ui-result.json',JSON.stringify({name,status:'pass',file:reg.items[0]},null,2));console.log('PASS Actual PMS project browser form uploads PNG image to Google Drive');
}catch(e){console.log((await p.locator('body').innerText()).slice(-1500));throw e;}finally{await b.browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});

import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const output = path.join(root, 'Mockup images', 'CRM Screenshots');
const origin = process.env.CRM_SCREENSHOT_URL || 'http://127.0.0.1:5195';
const api = 'http://127.0.0.1:1534/api/v1';
await fs.mkdir(output, {recursive:true});
const routes = [...(await fs.readFile(path.join(root,'frontend/src/apps/crm/routes.tsx'),'utf8')).matchAll(/path: "(crm[^\"]*)"/g)].map(m=>'/'+m[1]);
const browser = await chromium.launch({headless:true});
const context = await browser.newContext({viewport:{width:1920,height:1200},deviceScaleFactor:1,reducedMotion:'reduce'});
await context.addInitScript(api=>{window.__AI_HRMS_CONFIG__={apiBaseUrl:api};},api);
const page = await context.newPage();
let errors=[];
page.on('response',r=>{if(r.url().includes('/api/v1/')&&r.status()>=400)errors.push({url:r.url().split('?')[0],status:r.status()});});
page.on('pageerror',e=>errors.push({runtime:e.message}));
const match = process.env.CRM_CAPTURE_MATCH ? new RegExp(process.env.CRM_CAPTURE_MATCH) : null;
let records=[];
if (match) {
  records = JSON.parse(await fs.readFile(path.join(output,'capture-manifest.json'),'utf8')).screenshots;
}
const escape=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
async function capture(route,file,pattern=route){
  await page.waitForLoadState('networkidle',{timeout:15000}).catch(()=>{});
  await page.evaluate(()=>document.fonts.ready);
  await page.waitForTimeout(700);
  const text=await page.locator('body').innerText();
  await page.screenshot({path:path.join(output,file),fullPage:true,animations:'disabled'});
  records = records.filter(r=>r.pattern!==pattern);
  records.push({route,pattern,file,actualUrl:page.url(),heading:await page.locator('h1').allTextContents(),errors:[...errors],visibleFailure:/Something went wrong|Unable to load|Failed to load|Access denied|Internal Server Error/i.test(text)});
  await fs.writeFile(path.join(output,'capture-manifest.json'),JSON.stringify({generatedAt:new Date().toISOString(),origin,registeredRoutes:routes.length,screenshots:records},null,2));
  console.log('Saved '+file);
}
try {
  await page.goto(origin+'/crm/login');
  await page.locator('#email').waitFor();
  await capture('/crm/login','00_crm-login.png');
  await page.locator('#email').fill('admin@vyaparacrm.com');
  await page.locator('#password').fill('Password@123');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.waitForURL(u=>!u.pathname.endsWith('/login'),{timeout:45000});
  console.log('CRM administrator signed in');
  const auth=await page.evaluate(()=>{for(const storage of [localStorage,sessionStorage]){const a=JSON.parse(storage.getItem('hrms-auth')||'null');if(a?.state?.accessToken)return a.state;}return null;});
  const ids={};
  for(const entity of new Set(routes.filter(r=>r.includes(':id')).map(r=>r.split('/')[2]))){
    const endpoint=entity==='companies'?'accounts':entity;
    const response=await context.request.get(`${api}/crm/${endpoint}?per_page=1`,{headers:{Authorization:`Bearer ${auth.accessToken}`}});
    const data=await response.json().catch(()=>({}));
    ids[entity]=(data.items||data.data||[])[0]?.id;
    console.log(`Record ${entity}: ${ids[entity]??'none available'}`);
  }
  for(let i=0;i<routes.length;i++){
    const pattern=routes[i],entity=pattern.split('/')[2];
    if (match && !match.test(pattern)) continue;
    if(pattern.includes(':id')&&!ids[entity]){records.push({pattern,skipped:'No existing record available'});continue;}
    const route=pattern.replace(':id',ids[entity]);errors=[];
    await page.goto(origin+route,{waitUntil:'domcontentloaded',timeout:45000});
    if(page.url().includes('/login'))throw new Error('Session redirected to login: '+route);
    await capture(route,`${String(i+1).padStart(2,'0')}_${pattern.slice(1).replaceAll('/','-').replace(':id','detail')}.png`,pattern);
  }
} finally {
  await fs.writeFile(path.join(output,'capture-manifest.json'),JSON.stringify({generatedAt:new Date().toISOString(),origin,registeredRoutes:routes.length,screenshots:records},null,2));
  const cards=records.filter(r=>r.file).map(r=>`<article><a href="${escape(r.file)}"><img loading="lazy" src="${escape(r.file)}"></a><p>${escape(r.route)}</p></article>`).join('');
  await fs.writeFile(path.join(output,'index.html'),`<!doctype html><meta charset="utf-8"><title>CRM Screenshots</title><style>body{font:16px system-ui;background:#edf1f7;padding:30px;color:#19283e}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(400px,1fr));gap:24px}article{background:white;border-radius:12px;overflow:hidden}img{width:100%;height:280px;object-fit:cover;object-position:top}p{padding:0 16px}</style><h1>CRM Screenshots</h1><p>${records.filter(r=>r.file).length} captures · 1920 × 1200 viewport · existing local application data</p><main>${cards}</main>`);
  const skipped = records.filter(r=>r.skipped);
  if (skipped.length) await fs.appendFile(path.join(output,'index.html'),`<h2>Unavailable detail routes</h2><ul>${skipped.map(r=>`<li>${escape(r.pattern)} — ${escape(r.skipped)}</li>`).join('')}</ul>`);
  await browser.close();
}

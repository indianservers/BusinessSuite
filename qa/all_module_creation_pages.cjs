const {chromium}=require('../frontend/node_modules/playwright/test');
const fs=require('node:fs');const {html,fixture}=require('./smart_creation_browser.cjs');
const origin=process.env.SMART_CREATE_QA_ORIGIN||'http://127.0.0.1:5192';
const directory=process.env.CREATION_AUDIT_DIR||'.local/creation-complete';const resultFile=directory+'/'+(process.env.CREATION_RUN_ID||'all-pages')+'.json';fs.mkdirSync(directory,{recursive:true});
const catalog=JSON.parse(fs.readFileSync('outputs/creation-inventory/all-module-routes.json','utf8')).routes;
const settingsFile=directory+'/settings-catalog.json';const settings=fs.existsSync(settingsFile)?JSON.parse(fs.readFileSync(settingsFile,'utf8')).options.map(option=>'/settings/'+option.id):[];
const extra=['/power-apps','/power-apps/approvals','/power-apps/automations',...settings,...['pms','crm','srm','hrms','fam'].flatMap(m=>[`/${m}/forms`,`/${m}/forms/new`])];
const paths=[...new Set([...catalog.map(r=>r.path),...extra])].filter(p=>p.startsWith('/')&&!p.includes('*'));
const subset=process.env.CREATION_PAGE_FILTER;
const retryFile=process.env.CREATION_RETRY_FILE;const retryPaths=retryFile?new Set(JSON.parse(fs.readFileSync(retryFile,'utf8')).filter(r=>r.status!=='rendered').map(r=>r.route)):null;
const previousFile=process.env.CREATION_SKIP_FILE;const previousPaths=previousFile?new Set(JSON.parse(fs.readFileSync(previousFile,'utf8')).map(r=>r.route)):null;
const targets=paths.filter(p=>(!subset||new RegExp(subset).test(p))&&(!retryPaths||retryPaths.has(p))&&(!previousPaths||!previousPaths.has(p)));
async function dismiss(page){
 await page.keyboard.press('Escape');await page.waitForTimeout(220);
 const discard=page.getByRole('button',{name:'Discard Changes',exact:true});if(await discard.isVisible())await discard.click();
 const pending=page.locator('.smart-create-pending button');if(await pending.isVisible())await pending.click();
 for(let i=0;i<3&&await page.locator('[role="dialog"]:visible').count();i++){
  const last=page.locator('[role="dialog"]:visible').last();const close=last.getByRole('button',{name:/^(Close|Cancel)/i}).first();
  if(await close.isVisible())await close.click({timeout:2000}).catch(()=>{});else await page.keyboard.press('Escape');await page.waitForTimeout(220);
 }
 await page.waitForTimeout(120);
}
async function checkCreationActions(page,item){
 item.actionChecks=[];
 if(/\/(new|create|edit)(\/|$)/.test(item.resolved))return;
 const labels=[...new Set(item.creationActions.filter(a=>!a.disabled&&!a.href&&!a.label.includes('→')&&!/views$/i.test(a.label)&&(/^(create|invite|new\b|add (employee|task|lead|customer|vendor|product|service|contact|company|asset|goal|follow-up))\b/i.test(a.label))).map(a=>a.label))];
 for(const label of labels){
  if(label==='New')continue;
  const buttons=page.getByRole('button',{name:label,exact:true});let button;
  for(let i=0;i<await buttons.count();i++)if(await buttons.nth(i).isVisible()){button=buttons.nth(i);break;}
  if(!button)continue;
  const check={label,status:'pending'};item.actionChecks.push(check);const before=page.url();
  try{
   // A submit already inside an open editor is verified by its entity save test, not an open test.
   if(await button.evaluate(b=>!!b.closest('[role="dialog"],form'))){check.status='existing-editor-action';continue;}
   await button.click({timeout:2000});
   await page.locator('[role="dialog"]:visible,[role="menu"]:visible').first().waitFor({state:'visible',timeout:15000}).catch(()=>{});
   await page.waitForTimeout(120);const dialog=page.locator('[role="dialog"]:visible').last();
   if(await dialog.count()){
    check.status=await dialog.getAttribute('data-smart-create')||await dialog.getAttribute('data-smart-create-enhanced')?'modal-pass':'dialog-style-review';
    check.title=await dialog.locator('h1,h2').allTextContents();
    check.originRetained=page.url()===before;
    await dismiss(page);
    const discard=page.getByRole('button',{name:'Discard Changes',exact:true});if(await discard.isVisible())await discard.click();
   }else if(await page.locator('[role="menu"]:visible').count()){check.status='chooser-opened';await dismiss(page);}
   else {check.status='no-modal-review';check.detail=(await page.locator('#root').innerText()).slice(-400);const cancel=page.locator('.smart-create-pending button');if(await cancel.isVisible())await cancel.click();}
  }catch(e){check.status='failed';check.error=e.message.slice(0,250);}
  if(page.url()!==before||await page.locator('[role="dialog"]:visible').count()){await page.evaluate(p=>window.qaNavigate(p),item.resolved);await page.waitForTimeout(100);}
  await dismiss(page);
 }
}
async function checkNewMenu(page,item){
 item.newMenuChecks=[];
 const trigger=page.getByRole('button',{name:'New',exact:true}).first();
 if(!await trigger.isVisible())return;
 await dismiss(page);await trigger.click();await page.getByRole('menuitem').first().waitFor({state:'visible',timeout:5000});
 const labels=(await page.getByRole('menuitem').allInnerTexts()).map(s=>s.split('\n')[0].trim());await dismiss(page);
 for(const label of labels){
  if(process.env.CREATION_MENU_FILTER&&!new RegExp(process.env.CREATION_MENU_FILTER).test(label))continue;
  const before=page.url();await trigger.click();
  const entry=page.getByRole('menuitem').filter({hasText:new RegExp('^'+label.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'))}).first();
  const check={label,status:'pending'};item.newMenuChecks.push(check);
  try{
  if(await entry.getAttribute('data-disabled')!==null){check.status='disabled';await page.keyboard.press('Escape');continue;}
  await entry.focus();await page.keyboard.press("Enter");await page.locator('[role="dialog"]:visible').first().waitFor({state:'visible',timeout:15000}).catch(()=>{});
  await page.waitForTimeout(120);const dialog=page.locator('[role="dialog"]:visible').last();
  if(await dialog.count()){check.status=await dialog.getAttribute('data-smart-create')||await dialog.getAttribute('data-smart-create-enhanced')?'modal-pass':'dialog-style-review';check.originRetained=page.url()===before;if(label==='Private note'){await page.waitForTimeout(500);await page.screenshot({path:directory+'/private-note-'+(process.env.CREATION_WIDTH||1440)+'.png'});}await dismiss(page);}
  else {check.status=label==='Correct Attendance'?'navigation-action':'no-modal-review';check.detail=(await page.locator('body').innerText()).slice(-1800);}
  if(page.url()!==before)await page.evaluate(p=>window.qaNavigate(p),item.resolved);
  const discard=page.getByRole('button',{name:'Discard Changes',exact:true});if(await discard.isVisible())await discard.click();
  }catch(e){check.status='failed';check.error=e.message.slice(0,250);}
  await dismiss(page);await page.waitForTimeout(150);
 }
}
async function run(){
 const livePort=process.env.CREATION_REAL_API;
 let liveAuth,liveAccess;const liveReads=new Map();
 const bootstrapFile=directory+"/bootstrap.json";const cachedBootstrap=fs.existsSync(bootstrapFile)?JSON.parse(fs.readFileSync(bootstrapFile,"utf8")):{};
 if(livePort){
  if(!/^15\d\d$/.test(livePort))throw Error('Local QA API port required');
  liveAuth=JSON.parse(fs.readFileSync(directory+'/auth.json','utf8'));
  const response=await fetch(`http://127.0.0.1:${livePort}/api/v1/access/me`,{headers:{Authorization:'Bearer '+liveAuth.access_token}});
  if(!response.ok)throw Error('QA access lookup failed: '+response.status);
  liveAccess=await response.json();
 }
 let source=await html();source=source.slice(0,source.indexOf('import {SmartCreationProvider'))+`
import App from '/src/App.tsx';import {useAuthStore} from '/src/store/authStore.ts';
import '/src/index.css';import '/src/design-system/premium.css';import '/src/components/forms/compact-forms.css';import '/src/shared/data-grid/suite-list-surface.css';
import {applyTheme,useThemeStore} from '/src/store/themeStore.ts';applyTheme(useThemeStore.getState().theme);
import {useNavigate,useLocation} from '${[...source.matchAll(/from '([^']+)'/g)].map(m=>m[1]).find(p=>p.includes('react-router-dom.js?'))}';
const user=${JSON.stringify(liveAuth?{id:liveAuth.user_id,email:liveAuth.email,role:liveAuth.role,is_superuser:liveAuth.is_superuser,employee_id:liveAuth.employee_id,access:liveAccess}:{id:98261,name:'Creation QA',email:'creation@example.test',role:'admin',is_superuser:true,employee_id:1,access:{companyId:98261,memberships:[98261],organizations:[{id:98261,name:'QA workspace'}],managed:false,grants:{},modules:[]}})};
useAuthStore.setState({user,accessToken:${JSON.stringify(liveAuth?.access_token||null)},isAuthenticated:true,isHydrated:true});
class Boundary extends React.Component{constructor(p){super(p);this.state={error:''}}static getDerivedStateFromError(e){return {error:e.stack||e.message}}render(){return this.state.error?React.createElement('p',{'data-qa-error':true},this.state.error):this.props.children}}
function Host(){const navigate=useNavigate(),location=useLocation();window.qaNavigate=p=>navigate(p);return React.createElement(Boundary,{key:location.pathname+location.search},React.createElement(App));}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(QueryClientProvider,{client:new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}})},React.createElement(BrowserRouter,null,React.createElement(Host))));
</script></body></html>`;
 const browser=await chromium.launch({headless:true});const results=[];
 try {let next=0;
 await Promise.all(Array.from({length:3},async()=>{
  const context=await browser.newContext({viewport:{width:Number(process.env.CREATION_WIDTH||1440),height:960}});await fixture(context);
  await context.route('**/api/v1/business-os/modules',r=>r.fulfill({json:{enabled_modules:['hrms','crm','project_management','srm','fam','ai','portals','communication','power_apps'],modules:[]}}));
  await context.route('**/api/v1/access/me',r=>r.fulfill({json:{companyId:98261,memberships:[98261],organizations:[{id:98261,name:"QA workspace"}],managed:false,grants:{},modules:[]}}));
  if(livePort)await context.route('**/api/v1/**',async route=>{
   const request=route.request(),url=new URL(request.url());
   const cached=cachedBootstrap[url.pathname.replace("/api/v1","")];if(cached&&request.method()==="GET")return route.fulfill({json:cached});
   if(!['GET','HEAD','OPTIONS'].includes(request.method())&&!/\/(query|preview|search|resolve|bootstrap|context)$/.test(url.pathname))return route.fulfill({status:409,json:{detail:'Read-only creation audit: writes are blocked.'}});
   try{
    const key=request.method()+url.pathname+url.search+String(request.headers()['x-suite-branch']||'');
    let read=liveReads.get(key);
    if(!read){read=(async()=>{const headers={...request.headers(),authorization:'Bearer '+liveAuth.access_token};delete headers.host;delete headers['content-length'];const response=await fetch(`http://127.0.0.1:${livePort}${url.pathname}${url.search}`,{method:request.method(),headers,body:request.method()==='GET'?undefined:request.postData(),signal:AbortSignal.timeout(20000)});const replyHeaders=Object.fromEntries(response.headers);delete replyHeaders['content-length'];delete replyHeaders['content-encoding'];return {status:response.status,headers:replyHeaders,body:Buffer.from(await response.arrayBuffer())};})();if(request.method()==='GET')liveReads.set(key,read);read.catch(()=>liveReads.delete(key));}
    await route.fulfill(await read).catch(()=>{});
   }catch{await route.fulfill({status:503,json:{detail:'QA backend request unavailable'}});}
  });
  await context.route(origin+'/**',r=>r.request().resourceType()==='document'?r.fulfill({contentType:'text/html',body:source}):r.fallback());
  const page=await context.newPage();await page.goto(origin+'/pms/product-launch?projectId=87');await page.waitForFunction(()=>typeof window.qaNavigate==='function');
  const errors=[];page.on('pageerror',e=>errors.push(e.stack||e.message));
  while(next<targets.length){const route=targets[next++];const resolved=route.replace(/:([\w]+)/g,(_,key)=>/project/i.test(key)?'1':/workspace/i.test(key)?'1':route.startsWith('/crm/leads/')?'23':route.startsWith('/crm/contacts/')?'71':route.startsWith('/crm/deals/')?'34':/^\/crm\/(quotes|quotations)\//.test(route)?'12':route.startsWith('/srm/invoices/')?'9':'1');const item={route,resolved,errors:[],status:'pending',creationActions:[]};errors.length=0;
   try{await page.evaluate(p=>window.qaNavigate(p),resolved);await page.waitForTimeout(300);await page.getByText(/Loading workspace preferences/).waitFor({state:'hidden',timeout:18000}).catch(()=>{});await page.locator('h1:visible,h2:visible,[data-qa-error]').first().waitFor({state:'visible',timeout:2500}).catch(()=>{});
    // Lazy imports finish independently of API latency; loading shells are not considered verified pages.
    for(let i=0;i<60;i++){if(await page.locator('[data-qa-error]').count())break;const text=await page.locator('#root').innerText();if(text.length>100&&!/Loading workspace preferences/.test(text))break;await page.waitForTimeout(250);}
    if(!await page.locator('h1:visible,h2:visible').count()){for(let attempt=0;attempt<36;attempt++){const text=await page.locator('#root').innerText();if(!/Loading|Preparing/.test(text))break;await page.waitForTimeout(250);}}
    if(!await page.locator('h1:visible,h2:visible').count()){await page.locator('.skeleton:visible,.animate-pulse:visible').first().waitFor({state:'hidden',timeout:35000}).catch(()=>{});}
    if(process.env.CREATION_DETAIL_WAIT==='1')await page.locator('#suite-main h1:visible,#suite-main h2:visible').first().waitFor({state:'visible',timeout:45000}).catch(()=>{});
    item.errors=[...new Set([...errors,...await page.locator('[data-qa-error]').allTextContents()])];
    if(process.env.CREATION_CHECK_MENUS==='1'){const expand=page.getByRole('button',{name:'Expand all menu categories',exact:true});if(await expand.isVisible())await expand.click();}
    if(process.env.CREATION_CHECK_MENU_CONSISTENCY==='1'){
     const navigation=page.locator('.module-menu').first();
     if(await navigation.isVisible()){
      const expand=navigation.getByRole('button',{name:'Expand all menu categories',exact:true});if(await expand.isVisible())await expand.click();
      item.menu={links:await navigation.locator('.module-menu-categories .module-menu-row > a,.module-menu-landing .module-menu-row > a').evaluateAll(nodes=>nodes.map(node=>({label:node.textContent.trim(),path:new URL(node.href).pathname})).sort((a,b)=>a.path.localeCompare(b.path))),plus:await navigation.locator('.module-menu-create').count(),more:await navigation.locator('.module-menu-more').count(),accent:await navigation.evaluate(node=>getComputedStyle(node).getPropertyValue('--menu-accent').trim())};
     }
    }
    item.headings=await page.locator('h1:visible,h2:visible').allTextContents();item.excerpt=(await page.locator('#root').innerText()).slice(0,700);item.finalUrl=page.url();item.skeletons=await page.locator('.skeleton:visible').count();if(process.env.CREATION_RUN_ID==='debug-one')item.dom=(await page.locator('#suite-main').innerHTML()).slice(-5000);item.excerptTail=(await page.locator('#root').innerText()).slice(-1200);if(process.env.CREATION_RUN_ID==='debug-one')await page.screenshot({path:directory+'/debug.png'});
    item.creationActions=await page.locator('button:visible,a:visible').evaluateAll(nodes=>nodes.map(n=>({label:(n.getAttribute('aria-label')||n.textContent||'').trim().replace(/\s+/g,' '),href:n.getAttribute('href'),disabled:n.disabled||n.getAttribute('aria-disabled')==='true'})).filter(x=>/^(create|new|add|invite|register|publish)\b/i.test(x.label)&&x.label.length<140));
    item.status=item.errors.length?'fixture-or-render-error':item.headings.length||await page.locator('#suite-main form:visible input,#suite-main [data-compact-form]:visible input').count()?'rendered':/\/login$/.test(route)?'authentication-redirect-reviewed':'no-heading-review';
    if(process.env.CREATION_CHECK_ACTIONS==='1'&&item.status==='rendered')await checkCreationActions(page,item);
    if(process.env.CREATION_CHECK_MENUS==='1'&&item.status==='rendered')await checkNewMenu(page,item);
   }catch(e){item.status='failed';item.errors.push(e.message.slice(0,500));}
   results.push(item);fs.writeFileSync(resultFile,JSON.stringify(results,null,2));if(results.length%30===0)console.log('Reviewed '+results.length+'/'+targets.length+' routes');
  }await context.close();
 }));
 }finally{await browser.close();}
 fs.writeFileSync(resultFile,JSON.stringify(results,null,2));console.log(JSON.stringify(results.reduce((m,r)=>(m[r.status]=(m[r.status]||0)+1,m),{})));
}
run().catch(e=>{console.error(e);process.exitCode=1});

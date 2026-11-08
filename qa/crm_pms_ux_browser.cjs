// Real React components against isolated API fixtures. No production data/providers.
const { chromium, expect } = require('../frontend/node_modules/playwright/test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const origin = process.env.UX_QA_ORIGIN || 'http://127.0.0.1:5186';
if (!['127.0.0.1', 'localhost'].includes(new URL(origin).hostname)) throw Error('Loopback QA only');

async function html() {
  const main = await (await fetch(origin + '/src/main.tsx')).text();
  const dependency = name => {
    const found = [...main.matchAll(/from "([^"\n]+)"/g)].map(m=>m[1]).find(p=>p.includes('/'+name+'.js?'));
    if (!found) throw Error('Missing Vite dependency: '+name);
    return found;
  };
  return `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module">
import React from '${dependency('react')}';import ReactDOM from '${dependency('react-dom_client')}';
import {BrowserRouter,useLocation} from '${dependency('react-router-dom')}';import {QueryClient,QueryClientProvider} from '${dependency('@tanstack_react-query')}';
import Deals from '/src/apps/crm/deals/EnterpriseDealsPage.tsx';import Frame from '/src/shared/workspace/ModuleWorkspaceFrame.tsx';import {useAuthStore} from '/src/store/authStore.ts';import '/src/index.css';
import Operations from '/src/components/layout/OperationsWorkspace.tsx';
const params=new URLSearchParams(location.search);const restricted=params.has('restricted');const operations=params.has('operations');
useAuthStore.setState({user:{id:98261,email:'ux@example.test',role:restricted?'crm_viewer':'admin',is_superuser:!restricted,access:{companyId:98261,managed:false,modules:[],grants:{}}}});
function Draft({title}){const [value,setValue]=React.useState('');return React.createElement('div',null,React.createElement('h1',null,title),React.createElement('input',{'aria-label':title+' draft',value,onChange:e=>setValue(e.target.value)}));}
const routes=['time-tracking','timesheets'].map((path,i)=>({path:'pms/'+path,element:React.createElement(Frame,{module:'pms'},React.createElement(Draft,{title:i?'Timesheets':'Time tracking'}))}));
function App(){const loc=useLocation();if(operations)return React.createElement(Operations,{route:routes[0],routes});const pms=loc.pathname.startsWith('/pms');return React.createElement(Frame,{module:pms?'pms':'crm'},pms?React.createElement('h1',null,'Project planning'):React.createElement(Deals));}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(QueryClientProvider,{client:new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}})},React.createElement(BrowserRouter,null,React.createElement(App))));
</script></body></html>`;
}
const deals = Array.from({length:8},(_,i)=>({id:i+1,name:'Opportunity '+(i+1),company_id:1,company_name:'Example company',pipeline_id:1,stage_id:1,stage_name:'Discovery',owner_user_id:i%2+1,owner_name:i%2?'Jamie':'Alex',amount:1000+i,currency:'INR',status:'Open',probability:20,priority:i%2?'High':'Medium',version:1,updated_at:'2026-11-08T10:00:00Z'}));
async function fixture(context) {
  const queries=[];let fail=false;
  await context.route('**/@vite/client',route=>route.fulfill({contentType:'application/javascript',body:'export function createHotContext(){return {accept(){},dispose(){},invalidate(){},prune(){},on(){},off(){},send(){},data:{}}} export function injectQuery(url){return url;} const styles=new Map(); export function updateStyle(id,css){let s=styles.get(id);if(!s){s=document.createElement("style");document.head.append(s);styles.set(id,s);}s.textContent=css;} export function removeStyle(id){styles.get(id)?.remove();styles.delete(id);}'}));
  await context.route('**/api/v1/**', async route=>{
    const url=new URL(route.request().url());const path=url.pathname;
    const json=body=>route.fulfill({json:path.includes('/deal-workspace/')&&!path.includes('/grid/')&&Array.isArray(body)?{items:body,total:body.length,pages:1,page:1}:body});
    if(path.endsWith('/deal-workspace/pipelines')) return json([{id:1,name:'Main pipeline',is_default:true},{id:2,name:'Renewals'}]);
    if(path.endsWith('/deal-workspace/pipeline-stages')) return json([{id:1,pipeline_id:1,name:'Discovery',probability:20},{id:2,pipeline_id:2,name:'Renewal review',probability:60}]);
    if(path.endsWith('/deal-workspace/assignees')) return json([{id:1,name:'Alex'},{id:2,name:'Jamie'}]);
    if(path.endsWith('/deal-workspace/teams')) return json([]);
    if(path.endsWith('/deal-workspace/grid/query')) {
      if(fail) return route.fulfill({status:503,json:{detail:'Fixture service unavailable'}});
      const base=JSON.parse(url.searchParams.get('base')||'{}'); const state=JSON.parse(url.searchParams.get('state')||'{}');queries.push({base,state});
      const rows=deals.filter(r=>(!base.owner_id||r.owner_user_id===+base.owner_id)&&(!base.priority||r.priority===base.priority)&&(!base.pipeline_id||r.pipeline_id===+base.pipeline_id)&&(!base.search||r.name.toLowerCase().includes(base.search.toLowerCase())));
      return json({rows,total:rows.length,pageTotal:rows.length,page:1,pageSize:25,groups:[],aggregates:[],permissions:{edit:false,export:true,archive:false,assign:false},context:{summary:{counts:{open:8,closing_month:3,won_month:2,lost_month:1,overdue:2,without_activity:4},currencies:[{currency:'INR',pipeline:8028,weighted:1605.6}],forecast:[],definitions:{}}}});
    }
    if(path.endsWith('/branches/context')) return json({selected:1,branches:[{id:1,name:'Main',can_write:true}]});
    if(path.includes('/notifications')) return json({items:[],unread:0,total:0});
    // Presentation preferences, identity lookups and unused auxiliary widgets.
    return json([]);
  });
  return {queries,setFailure(value){fail=value;}};
}
async function run() {
  fs.mkdirSync('.local/crm-pms-ux',{recursive:true});
  const body=await html();const browser=await chromium.launch({headless:true});const results=[];
  try {
    for(const width of [1440,390]) {
      const context=await browser.newContext({viewport:{width,height:900}});const api=await fixture(context);
      await context.route('**/__crm_pms_ux*',r=>r.fulfill({contentType:'text/html',body}));
      await context.route(origin+'/pms/**',r=>r.fulfill({contentType:'text/html',body}));
      const page=await context.newPage();const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error('Browser error:',e.message);});
      page.on('console',msg=>{if(msg.type()==='error')console.error('Console:',msg.text());});
      await page.goto(origin+'/__crm_pms_ux');
      await expect(page.getByRole('heading',{name:'Deals',exact:true})).toBeVisible();
      await expect(page.getByRole('link',{name:'Opportunity 1',exact:true}).first()).toBeVisible();
      assert.equal(await page.locator('h1:visible').count(),1,'One page heading');
      assert.equal(await page.locator('.ed-stats-primary>div').count(),3);
      assert.equal(await page.locator('.ed-stats-primary').evaluate(el=>el.scrollWidth<=el.clientWidth+1),true,'All three primary metrics fit without scrolling');
      await expect(page.getByText('Weighted pipeline',{exact:true})).not.toBeVisible();
      await page.getByText('More sales metrics',{exact:true}).click();
      await expect(page.getByText('Weighted pipeline',{exact:true})).toBeVisible();
      await page.getByText('More sales metrics',{exact:true}).click();
      const quick=page.getByRole('group',{name:'Quick deal filters'});
      await quick.getByLabel('Owner',{exact:true}).selectOption('2');
      await expect.poll(()=>api.queries.at(-1)?.base.owner_id).toBe('2');
      await expect(page.getByRole('link',{name:'Opportunity 1',exact:true})).toHaveCount(0);
      await page.getByText('Advanced filters',{exact:true}).click();
      await page.getByLabel('Priority',{exact:true}).selectOption('High');
      await expect.poll(()=>api.queries.at(-1)?.base.priority).toBe('High');
      await page.locator('.ed-filter-details>summary').click();
      await expect(page.locator('.ed-filter-details>summary')).toHaveText('Advanced filters (1 active)');
      await page.getByRole('button',{name:'Clear filters (2)',exact:true}).click();
      await expect(quick.getByLabel('Owner',{exact:true})).toHaveValue('');
      await expect(page.getByLabel('Priority',{exact:true})).toHaveValue('');
      await expect(page.getByRole('link',{name:'Opportunity 1',exact:true}).first()).toBeVisible();
      await quick.getByLabel('Pipeline',{exact:true}).selectOption('2');
      await quick.getByLabel('Stage',{exact:true}).selectOption('2');
      await quick.getByLabel('Pipeline',{exact:true}).selectOption('1');
      await expect(quick.getByLabel('Stage',{exact:true})).toHaveValue('');
      await page.getByRole('button',{name:/Clear filters/}).first().click();
      // Alternate views keep the same filters and returning to Table does too.
      await quick.getByLabel('Owner',{exact:true}).selectOption('2');
      await page.getByRole('button',{name:'Add deal views',exact:true}).click();
      const catalog=page.getByRole('dialog');
      await catalog.getByRole('button',{name:/List An expandable/}).click();
      await expect.poll(()=>api.queries.at(-1)?.base.owner_id).toBe('2');
      await expect(quick.getByLabel('Owner',{exact:true})).toHaveValue('2');
      await page.getByRole('button',{name:'Table',exact:true}).first().click();
      await expect(quick.getByLabel('Owner',{exact:true})).toHaveValue('2');
      await page.getByRole('button',{name:/Clear filters/}).first().click();
      api.setFailure(true);await page.getByRole('button',{name:'Refresh deals',exact:true}).click();
      await expect(page.getByText('Fixture service unavailable',{exact:false}).first()).toBeVisible();
      api.setFailure(false);await page.getByRole('button',{name:'Refresh deals',exact:true}).click();
      await expect(page.getByRole('link',{name:'Opportunity 1',exact:true}).first()).toBeVisible();
      await expect.poll(()=>page.getByText('Fixture service unavailable',{exact:false}).count()).toBe(0);
      await page.screenshot({path:'.local/crm-pms-ux/crm-'+width+'.png',fullPage:true});
      // Browser history updates the real Frame instance. All links remain real anchors.
      await page.evaluate(()=>{history.pushState({},'', '/pms/gantt?workspace=7&project=23');dispatchEvent(new PopStateEvent('popstate'));});
      await page.getByRole('button',{name:'Switch workspace',exact:true}).click();
      const workload=page.getByRole('link',{name:/Workload Availability/});
      await expect(workload).toHaveAttribute('href','/pms/workload?workspace=7&project=23');
      await workload.click();await expect(page).toHaveURL(/\/pms\/workload\?workspace=7&project=23$/);
      await page.getByRole('button',{name:'Switch workspace',exact:true}).click();
      await expect(page.getByRole('dialog',{name:'Choose a workspace'})).toBeVisible();
      await page.getByRole('link',{name:/Gantt Dependencies/}).focus();
      await page.keyboard.press('Escape');await expect(page.getByRole('button',{name:'Switch workspace',exact:true})).toBeFocused();
      await page.goBack();await expect(page).toHaveURL(/\/pms\/gantt\?workspace=7&project=23$/);
      await page.getByRole('button',{name:'Switch workspace',exact:true}).click();
      await page.getByRole('button',{name:'Pin Workload workspace',exact:true}).click();
      await expect(page.getByRole('button',{name:'Unpin Workload workspace',exact:true})).toHaveAttribute('aria-pressed','true');
      await page.reload();
      await page.getByRole('button',{name:'Switch workspace',exact:true}).click();
      await expect(page.getByRole('button',{name:'Unpin Workload workspace',exact:true})).toBeVisible();
      await page.evaluate(async()=>{const {useAuthStore}=await import('/src/store/authStore.ts');const user=useAuthStore.getState().user;useAuthStore.setState({user:{...user,id:98262}});});
      await expect(page.getByRole('button',{name:'Pin Workload workspace',exact:true})).toBeVisible();
      await page.keyboard.press('Escape');
      await page.screenshot({path:'.local/crm-pms-ux/pms-'+width+'.png',fullPage:true});
      const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);assert.equal(overflow,false,'No document overflow at '+width);
      await page.goto(origin+'/__crm_pms_ux?operations=1');
      await expect(page.getByRole('heading',{name:'Time tracking',exact:true})).toBeVisible();
      assert.equal(await page.locator('h1:visible').count(),1,'Operation wrapper must not add a heading');
      await page.getByRole('textbox',{name:'Time tracking draft',exact:true}).fill('Retain unsaved time entry');
      await page.getByRole('tab',{name:'Timesheets',exact:true}).click();
      await expect(page.getByRole('heading',{name:'Timesheets',exact:true})).toBeVisible();
      await page.getByRole('tab',{name:'Timesheets',exact:true}).press('ArrowLeft');
      await expect(page.getByRole('textbox',{name:'Time tracking draft',exact:true})).toHaveValue('Retain unsaved time entry');
      await expect(page.getByRole('tab',{name:'Time & timesheets',exact:true})).toBeFocused();
      assert.deepEqual(errors,[]);results.push({width,passed:true,flows:['metrics','quick/advanced filters','clear/reset','pipeline/stage reset','view preservation','load failure/retry','PMS context/navigation/back','keyboard dismissal','pin persistence and user isolation','operation tabs/keyboard/draft retention'],api:'isolated fixtures'});
      await context.close();
    }
    fs.writeFileSync('.local/crm-pms-ux/results.json',JSON.stringify({at:new Date().toISOString(),results},null,2));
    console.log(JSON.stringify(results,null,2));
  } finally {await browser.close();}
}
run().catch(e=>{console.error(e);process.exitCode=1;});

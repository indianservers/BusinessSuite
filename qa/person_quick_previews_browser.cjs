const { chromium, expect } = require('../frontend/node_modules/playwright/test');
const assert = require('node:assert/strict');
const origin = process.env.PREVIEW_QA_ORIGIN || 'http://localhost:5173';
(async () => {
  const module = await (await fetch(origin + '/src/components/RecordQuickPreview.tsx')).text();
  const react = module.match(/"([^"\n]*\/react\.js\?v=[^"\n]+)"/)[1];
  const router = module.match(/"([^"\n]*\/react-router-dom\.js\?v=[^"\n]+)"/)[1];
  const grid = await (await fetch(origin + '/src/shared/data-grid/SharedDataGrid.tsx')).text();
  const query = grid.match(/"([^"\n]*\/@tanstack_react-query\.js\?v=[^"\n]+)"/)[1];
  const main = await (await fetch(origin + '/src/main.tsx')).text();
  const dom = main.match(/"([^"\n]*\/react-dom_client\.js\?v=[^"\n]+)"/)[1];
  const html = `<!doctype html><html><head><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module">
import React from '${react}';import ReactDOM from '${dom}';import {BrowserRouter} from '${router}';import {QueryClient,QueryClientProvider} from '${query}';import Preview,{recordPreviewProps} from '/src/components/RecordQuickPreview.tsx';import {isPersonRecord} from '/src/components/PersonRecordPreview.tsx';import Directory from '/src/components/PeopleDirectoryPage.tsx';import Contacts from '/src/apps/crm/UniversalContactsPage.tsx';import CRMPanel from '/src/apps/crm/CRMRecordPanel.tsx';import PMSDirectory from '/src/apps/project-management/pages/PeopleManagementDirectory.tsx';import PersonHost from '/src/apps/project-management/components/people/PersonManagementHost.tsx';import {openPerson} from '/src/apps/project-management/components/people/peopleTypes.ts';import '/src/index.css';
window.classify=isPersonRecord;
const cases=[['user',{id:7,name:'Asha Shah',email:'asha@example.com',role:'Member',is_active:true,workspaces:[{name:'Main workspace'}],password:'PRIVATE-VALUE'},'/hrms/users'],['member',{original:{id:8,name:'Nora Patel',email:'nora@example.com',classification:'Intern',teams:[{name:'Design team'}],skills:['Figma']}},'/pms/people'],['contact',{id:9,name:'CRM Person',email:'person@example.com',status:'Active'},'/crm/contacts'],['lead',{id:10,full_name:'Lead Person',email:'lead@example.com',status:'New'},'/crm/leads'],['task',{id:11,title:'Actual task',task_key:'TASK-11'},'/pms/tasks']];
const surface=new URLSearchParams(location.search).get('surface');
const content=surface==='pms-directory'?React.createElement(PMSDirectory):surface==='manage-person'?React.createElement(React.Fragment,null,React.createElement('button',{onClick:()=>openPerson({userId:7})},'Manage Asha'),React.createElement(PersonHost)):surface==='directory'?React.createElement(Directory):surface==='contacts'?React.createElement(Contacts):surface==='crm-panel'?React.createElement(CRMPanel,{record:{id:9,entity:'contacts',name:'CRM Person',status:'Active'},close:()=>{},changed:()=>{},onInteraction:()=>{}}):React.createElement(React.Fragment,null,React.createElement('table',null,React.createElement('tbody',null,...cases.map(([key,record,path])=>React.createElement('tr',{...recordPreviewProps(record,path),'data-testid':key,key},React.createElement('td',null,key))))),React.createElement(Preview));
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(QueryClientProvider,{client:new QueryClient({defaultOptions:{queries:{retry:false}}})},React.createElement(BrowserRouter,null,content)));
</script></body></html>`;
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}}); const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    const contact={id:9,name:'CRM Person',email:'person@example.com',status:'Active',organization:'Acme',tags:['Customer'],notes:'Discuss next delivery',nextFollowUp:'2026-11-05',version:'1',leads:[{id:10,name:'Linked lead',status:'New',converted:false}],related:{related:{projects:[{name:'Customer project'}]},timeline:[{title:'Call recorded'}]}};
    await page.route('**/*', route => {
      const path = new URL(route.request().url()).pathname;
      if(path==='/__person_qa')return route.fulfill({contentType:'text/html',body:html});
      if(path.includes('/api/')) {
        let data={items:[],total:0};
        if(path.endsWith('/people-management/options'))data={workspaces:[],projects:[],organization_admin:false};
        else if(path.endsWith('/people-management/7'))data={id:7,name:'Asha Shah',email:'asha@example.com',role:'Member',status:'active',workspaces:[{id:1,workspace_id:1,name:'Main workspace',role:'Member'}],projects:[],access_sources:[],permissions:{},unavailable_reasons:{},history:[]};
        else if(path.endsWith('/people-workspace/reference'))data={stats:{total:1,active:1,inactive:0,teams:1,batches:0},roles:[],departments:[],workspaces:[],organizations:[],can_create_user:false,can_export:false,can_manage_batches:false,can_manage_people:false};
        else if(path.endsWith('/people-workspace/people'))data={items:[{id:8,name:'Nora Patel',email:'nora@example.com',role:'Member',classification:'Intern',status:'active',projects:[{id:1,name:'Website project'}],workspaces:[],teams:[{id:2,name:'Design team',workspace_id:1}],batches:[],skills:['Figma'],registered_at:'2026-11-01',can_manage:false}],total:1,page:1,page_size:24,pages:1};
        else if(path.endsWith('/people-workspace/views'))data=[];
        else if(path.endsWith('/people-workspace/groups')||path.endsWith('/people-workspace/actions/destinations'))data={items:[],total:0,page:1,pages:1};
        else if(path.endsWith('/users/directory'))data={items:[{id:7,name:'Asha Shah',email:'asha@example.com',role:'member',is_active:true,workspace_ids:[1]}],total:1,workspaces:[{id:1,name:'Main workspace'}],teams:[{id:2,name:'Design team',workspace_id:1,member_ids:[7]}]};
        else if(path.endsWith('/crm/contact-directory'))data={items:[contact],total:1,stats:{total:1},canManage:true,canConvert:true,classifications:[]};
        else if(path.endsWith('/crm/contact-directory/9'))data=contact;
        else if(path.endsWith('/crm/contacts/9'))data={...contact,timeline:[{title:'Call recorded'}],nested:{password:'PRIVATE-VALUE',city:'Hyderabad'}};
        else if(path.endsWith('/crm/contacts/9/related'))data={projects:[{name:'Customer project'}]};
        else if(path.endsWith('/crm/leads/10'))data={id:10,full_name:'Lead Person',email:'lead@example.com',next_follow_up_at:'2026-11-05',notes:'Lead notes'};
        else if(path.endsWith('/crm/leads/10/related'))data={};
        return route.fulfill({json:data});
      }
      return route.continue();
    });
    await page.goto(origin+'/__person_qa');
    await page.getByTestId('user').dblclick();
    await expect(page.locator('.wf-preview .wfp-title')).toHaveText('Asha Shah');
    await expect(page.getByRole('dialog')).not.toContainText('PRIVATE-VALUE');
    await page.getByRole('tab',{name:'Work & Relationships'}).click();
    await expect(page.getByRole('tabpanel')).toContainText('Main workspace');
    await page.keyboard.press('ArrowRight');await expect(page.getByRole('tab',{name:'Follow-up',exact:true})).toBeFocused();
    await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
    await page.getByTestId('member').dblclick();await expect(page.locator('.wfp-title')).toHaveText('Nora Patel');await expect(page.getByRole('dialog')).toContainText('Design team');await page.keyboard.press('Escape');
    await page.getByTestId('contact').dblclick();await expect(page.getByRole('dialog')).toContainText('Hyderabad');await expect(page.getByRole('dialog')).not.toContainText('PRIVATE-VALUE');
    await page.getByLabel('Search profile fields').fill('Hyderabad');await expect(page.getByRole('tabpanel')).toContainText('Hyderabad');await page.keyboard.press('Escape');
    await page.getByTestId('lead').dblclick();await page.getByRole('tab',{name:'Follow-up',exact:true}).click();await expect(page.getByRole('tabpanel')).toContainText('2026-11-05');await page.keyboard.press('Escape');
    await page.getByTestId('task').dblclick();await expect(page.getByRole('dialog')).toContainText('Quick preview');assert.equal(await page.locator('.wfp-avatar').count(),0);await page.keyboard.press('Escape');
    assert.equal(await page.evaluate(()=>window.classify({id:1,name:'Acme',email:'sales@acme.com'},'/crm/companies')),false);
    assert.equal(await page.evaluate(()=>window.classify({id:1,name:'Asha',email:'asha@example.com',role:'Member'},'/pms/projects/1')),true);
    await page.goto(origin+'/__person_qa?surface=directory');await page.getByRole('button',{name:'View profile of Asha Shah',exact:true}).click();await expect(page.locator('.wfp-title')).toHaveText('Asha Shah');await page.getByRole('tab',{name:'Work & Relationships'}).click();await expect(page.getByRole('button',{name:'Design team',exact:true})).toBeVisible();await page.getByRole('button',{name:'Design team',exact:true}).click();await expect(page.getByRole('dialog')).toHaveCount(0);
    await page.goto(origin+'/__person_qa?surface=contacts');await page.getByText('CRM Person',{exact:true}).first().click();await expect(page.locator('.wfp-title')).toHaveText('CRM Person');await page.getByRole('tab',{name:'Work & Relationships'}).click();await expect(page.getByRole('dialog')).toContainText('Linked lead');await expect(page.getByRole('button',{name:'Convert to customer',exact:true})).toBeVisible();await page.getByRole('tab',{name:'Notes & Activity'}).click();await expect(page.getByRole('tabpanel')).toContainText('Discuss next delivery');
    await page.setViewportSize({width:390,height:844});const box=await page.getByRole('dialog').boundingBox();assert.ok(box.x>=0&&box.x+box.width<=391&&box.height<=844);await page.screenshot({path:require('node:path').join(require('node:os').tmpdir(),'all-person-preview-mobile.png')});
    await page.setViewportSize({width:1440,height:1000});
    await page.goto(origin+'/__person_qa?surface=pms-directory');await page.getByRole('link',{name:'Nora Patel',exact:true}).first().click();await expect(page.locator('.wfp-title')).toHaveText('Nora Patel');await page.getByRole('tab',{name:'Work & Relationships'}).click();await expect(page.getByRole('dialog')).toContainText('Website project');await expect(page.getByRole('button',{name:'Assign to destination',exact:true})).toBeVisible();await expect(page.getByRole('link',{name:'Assignment history',exact:true})).toHaveAttribute('href',/tab=activity/);
    await page.goto(origin+'/__person_qa?surface=manage-person');await page.getByRole('button',{name:'Manage Asha'}).click();await expect(page.locator('.wfp-title')).toHaveText('Asha Shah');await expect(page.getByRole('dialog')).toContainText('Main workspace');await page.getByRole('tab',{name:'Access',exact:true}).click();await expect(page.getByRole('heading',{name:'Effective access and its source'})).toBeVisible();
    await page.goto(origin+'/__person_qa?surface=crm-panel');await expect(page.locator('.wfp-title')).toHaveText('CRM Person');await page.getByRole('tab',{name:'Notes & Activity'}).click();await expect(page.getByRole('tabpanel')).toContainText('Call recorded');
    assert.deepEqual(errors,[]);console.log('PASS: user/member/contact/lead routing; non-person records; secret filtering; directory actions; contact conversion controls; CRM timeline; PMS assignment controls; person management; keyboard and mobile layout.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exit(1);});

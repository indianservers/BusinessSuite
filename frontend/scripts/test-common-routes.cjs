const assert = require('node:assert/strict');
const path = require('node:path');
const { build } = require('esbuild');
const { chromium } = require('playwright');

(async () => {
  const root = path.resolve(__dirname, '..');
  const built = await build({
    stdin: { contents: `
      import React from 'react';
      import {createRoot} from 'react-dom/client';
      import {BrowserRouter,Routes,Route,useNavigate} from 'react-router-dom';
      import CommonEntityPage from '@/common/CommonEntityPage';
      import * as registry from '@/lib/common-routes';
      import {canAccessRoute,getActiveModule,getRoleNav} from '@/lib/roles';
      import {getProductKeyFromPath} from '@/lib/products';
      import {moduleForActionPath,moduleActionAllowed} from '@/hooks/use-module-action';
      import {workspacePageHref} from '@/lib/navigation-workspaces';
      import {useAuthStore} from '@/store/authStore';
      window.api={...registry,canAccessRoute,getActiveModule,getRoleNav,getProductKeyFromPath,moduleForActionPath,moduleActionAllowed,workspacePageHref};
      useAuthStore.setState({user:{id:1,role:'admin',is_superuser:true},isAuthenticated:true,isHydrated:true});
      const paths=[...new Set(Object.values(registry.commonEntities).flatMap(e=>[e.owner,...e.aliases]))];
      const routes=paths.map(p=>({path:p.slice(1),element:<h1>Native page {p}</h1>}));
      function Harness(){window.navigate=useNavigate();return <Routes><Route path="common/:entity" element={<CommonEntityPage routes={routes}/>}/><Route path="*" element={<h1>Home</h1>}/></Routes>}
      createRoot(document.getElementById('root')).render(<BrowserRouter><Harness/></BrowserRouter>);
    `, resolveDir: root, loader: 'tsx' },
    bundle: true, write: false, format: 'iife', platform: 'browser',
    alias: { '@': path.join(root, 'src') }, define: { 'import.meta.env': '{}' },
  });
  const browser = await chromium.launch();
  let checks = 0;
  try {
    const page = await browser.newPage();
    await page.route('http://common.test/**', route => route.fulfill({contentType:'text/html',body:'<div id="root"></div>'}));
    await page.goto('http://common.test/');
    await page.addScriptTag({content: built.outputFiles[0].text});
    await page.getByRole('heading', {name:'Home'}).waitFor();
    const definitions = await page.evaluate(() => window.api.commonEntities);
    for (const [entity, definition] of Object.entries(definitions)) {
      for (const module of ['crm','pms','hrms','srm','fam']) {
        const href = `/common/${entity}?module=${module}&workspace=27&project=9`;
        const result = await page.evaluate(({href,module}) => {
          const a=window.api,c=a.commonRouteContext(href);
          return {context:c,allowed:a.canAccessRoute(href,'admin',true),active:a.getActiveModule(href),product:a.getProductKeyFromPath(href),kept:a.workspacePageHref(href,'?workspace=42&project=77')};
        }, {href,module});
        assert.equal(result.context.module,module);
        assert.equal(result.allowed,true);
        assert.equal(result.active,module==='pms'?'project_management':module);
        assert.equal(result.product,module==='pms'?'project_management':module);
        assert(result.kept.includes('workspace=27') && result.kept.includes('project=9'));
        await page.evaluate(href=>window.navigate(href),href);
        await page.getByRole('heading',{name:`Native page ${result.context.nativePath}`,exact:true}).waitFor();
        await page.getByRole('navigation',{name:'Shared page breadcrumbs'}).getByText(definition.label,{exact:true}).waitFor();
        checks++;
      }
      for (const alias of definition.aliases) {
        const mapped=await page.evaluate(alias=>window.api.commonNavigationHref(alias,'crm'),alias);
        assert(mapped.startsWith(`/common/${entity}?`)); checks++;
      }
      const defaultContext=await page.evaluate(entity=>window.api.commonRouteContext(`/common/${entity}`),entity);
      assert.equal(defaultContext.nativePath,definition.owner); checks++;
    }
    for(const href of ['/common/nope','/common/__proto__','/common/constructor','/common/tasks/new','/common/tasks?module=admin','/common/tasks?module=https://evil.test','/common/tasks?module=CRM']) {
      const result=await page.evaluate(href=>({context:window.api.commonRouteContext(href),allowed:window.api.canAccessRoute(href,'admin',true)}),href);
      assert.equal(result.context,null);assert.equal(result.allowed,false);checks++;
    }
    for(const alias of ['/crm/tasks/legacy','/crm/leads/42','/pms/tasks/17','/hrms/employees/new','/srm/inventory/items/5','/fam/customers']) {
      assert.equal(await page.evaluate(alias=>window.api.commonNavigationHref(alias,'crm'),alias),alias);checks++;
    }
    for(const module of ['crm','pms','hrms','srm','fam']) {
      const navigation=await page.evaluate(module=>window.api.getRoleNav('admin',true,`/${module}`).map(item=>item.to),module);
      for(const entity of ['tasks','notes','calendar','contacts']) {
        assert(navigation.some(href=>href===`/common/${entity}?module=${module}`),`${module} must expose shared ${entity}`);checks++;
      }
    }
    const security=await page.evaluate(()=>{
      const a=window.api;
      return {employee:a.canAccessRoute('/common/employees?module=crm','crm_viewer',false),
        origin:a.canAccessRoute('/common/tasks?module=hrms','pms_team_member',false),
        action:a.moduleActionAllowed({access:{managed:true,grants:{crm:{enabled:true,actions:['edit']}}}},'/common/tasks?module=crm','edit'),
        denied:a.moduleActionAllowed({access:{managed:true,grants:{srm:{enabled:true,actions:['edit']}}}},'/common/contacts?module=srm','edit')};
    });
    assert.equal(security.employee,false);assert.equal(security.origin,false);assert.equal(security.action,true);assert.equal(security.denied,false);checks+=4;
    // A refreshed common URL must recover context from the address, without session history.
    await page.goto('http://common.test/common/customers?module=srm');
    await page.addScriptTag({content:built.outputFiles[0].text});
    await page.getByRole('heading',{name:'Native page /srm/customers',exact:true}).waitFor();checks++;
    await page.evaluate(()=>window.navigate('/common/tasks?module=invalid'));
    await page.getByRole('alert').waitFor();
    assert.equal(await page.getByRole('heading').count(),0);checks++;
    console.log(`PASS: ${checks} common route, adapter, alias, context, refresh and permission scenarios`);
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});

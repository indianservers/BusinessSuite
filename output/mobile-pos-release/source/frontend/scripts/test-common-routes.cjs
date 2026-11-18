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
      import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
      import {BrowserRouter,Routes,Route,Link,useNavigate,useParams} from 'react-router-dom';
      import CommonEntityPage from '@/common/CommonEntityPage';
      import CommonCommercialEntry from '@/common/CommonCommercialEntry';
      import SRMRouteWorkspace from '@/apps/srm/components/SRMRouteWorkspace';
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
      function Detail(){const {id}=useParams(),navigate=useNavigate();return <><h1>Invoice {id}</h1><Link to="/srm/invoices">Invoices list</Link><button onClick={()=>navigate('/srm/contracts/7')}>Related contract</button></>}
      routes.push({path:'srm/invoices/:id',element:<Detail/>},{path:'srm/contracts/:id',element:<h1>Contract detail</h1>});
      // Exercise the real native Sales wrapper as well as the common host.
      const wrappedRoutes=routes.map(route=>route.path.startsWith('srm/')&&registry.commercialEntities.some(entity=>registry.commonEntities[entity].owner==='/'+route.path)?{...route,element:<SRMRouteWorkspace route={route} routes={routes}/>} : route);
      function Harness(){window.navigate=useNavigate();return <Routes><Route path="common/:entity/*" element={<CommonEntityPage routes={wrappedRoutes}/>}/><Route path="srm/invoices/*" element={<CommonCommercialEntry><h1>Legacy page</h1></CommonCommercialEntry>}/><Route path="srm/quotes" element={<CommonCommercialEntry><h1>Legacy quotes</h1></CommonCommercialEntry>}/><Route path="*" element={<h1>Home</h1>}/></Routes>}
      createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><BrowserRouter><Harness/></BrowserRouter></QueryClientProvider>);
    `, resolveDir: root, loader: 'tsx' },
    bundle: true, write: false, format: 'iife', platform: 'browser',
    alias: { '@': path.join(root, 'src') }, define: { 'import.meta.env': '{}' }, loader: {'.css':'empty'},
  });
  const browser = await chromium.launch();
  let checks = 0;
  try {
    const page = await browser.newPage();
    await page.route('https://common.test/**', route => route.fulfill({contentType:'text/html',body:'<div id="root"></div>'}));
    await page.goto('https://common.test/');
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
        await page.getByRole('navigation',{name:'Shared page breadcrumbs'}).waitFor();
        if (['quotations','contracts','purchase-orders','sales-orders','invoices','invoice-drafts','billing-plans','collections','engagements','payment-requests'].includes(entity)) {
          await page.getByRole('navigation',{name:'Shared page breadcrumbs'}).getByText(definition.label,{exact:true}).waitFor();
          assert.equal(new URL(page.url()).pathname,`/common/${entity}`);
        }
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
    for (const module of ['crm','srm']) {
      const navigation=await page.evaluate(module=>window.api.getRoleNav('admin',true,`/${module}`),module);
      assert.deepEqual(navigation.filter(item=>item.group==='Commercial documents').map(item=>new URL(item.to,'https://suite.test').pathname),['quotations','contracts','purchase-orders','sales-orders','invoices','invoice-drafts','billing-plans','collections','engagements','payment-requests'].map(entity=>`/common/${entity}`));checks++;
      for (const entity of ['quotations','contracts','purchase-orders','sales-orders','invoices','invoice-drafts','billing-plans','collections','engagements','payment-requests']) {
        const links=navigation.filter(item=>item.to===`/common/${entity}?module=${module}`);
        assert.equal(links.length,1,`${module} must expose exactly one shared ${entity}`);
        assert.equal(links[0].group,'Commercial documents');checks++;
        const contexts=await page.evaluate(entity=>['crm','srm'].map(module=>window.api.commonRouteContext(`/common/${entity}?module=${module}`).nativePath),entity);
        assert.equal(contexts[0],contexts[1]);checks++;
      }
      for (const native of ['/crm/quotes/29/builder','/crm/quotations/29','/srm/sales-orders/42','/srm/contracts/42','/srm/invoices/42','/srm/inventory/purchase-orders/create']) {
        const result=await page.evaluate(({native,module})=>{const href=window.api.commonNavigationHref(native+'?new=1#details',module);return {href,context:window.api.commonRouteContext(href.split('#')[0])};},{native,module});
        assert.equal(result.context.module,module);
        assert.equal(result.context.nativePath,native);
        assert(result.href.endsWith('#details'));checks++;
      }
      await page.evaluate(module=>window.navigate(`/common/invoices/42?module=${module}`),module);
      await page.getByRole('heading',{name:'Invoice 42',exact:true}).waitFor();
      assert.equal(await page.getByRole('link',{name:'Invoices list'}).getAttribute('href'),`/common/invoices?module=${module}`);checks++;
      await page.getByRole('button',{name:'Related contract'}).click();
      await page.getByRole('heading',{name:'Contract detail'}).waitFor();
      assert.equal(new URL(page.url()).pathname,'/common/contracts/7');
      assert.equal(new URL(page.url()).search,`?module=${module}`);checks++;
    }
    const security=await page.evaluate(()=>{
      const a=window.api;
      return {employee:a.canAccessRoute('/common/employees?module=crm','crm_viewer',false),
        origin:a.canAccessRoute('/common/tasks?module=hrms','pms_team_member',false),
        action:a.moduleActionAllowed({access:{managed:true,grants:{crm:{enabled:true,actions:['edit']}}}},'/common/tasks?module=crm','edit'),
        denied:a.moduleActionAllowed({access:{managed:true,grants:{srm:{enabled:true,actions:['edit']}}}},'/common/contacts?module=srm','edit')};
    });
    assert.equal(security.employee,false);assert.equal(security.origin,false);assert.equal(security.action,true);assert.equal(security.denied,false);checks+=4;
    for(const module of ['crm','srm']) {
      await page.evaluate(module=>window.navigate(`/common/invoices?module=${module}&operation=/srm/invoice-drafts&customer_id=9`),module);
      await page.getByRole('heading',{name:'Native page /srm/invoice-drafts',exact:true}).waitFor();
      assert.equal(new URL(page.url()).pathname,'/common/invoice-drafts');
      assert.equal(new URL(page.url()).searchParams.get('operation'),null);
      assert.equal(new URL(page.url()).searchParams.get('customer_id'),'9');checks++;
    }
    await page.evaluate(()=>window.navigate('/srm/quotes?search=shared#top'));
    await page.getByRole('heading',{name:'Native page /crm/quotations',exact:true}).waitFor();
    assert.equal(new URL(page.url()).pathname,'/common/quotations');
    assert.equal(new URL(page.url()).search,'?search=shared&module=srm');checks++;
    await page.evaluate(()=>window.navigate('/srm/invoices/42'));
    await page.getByRole('heading',{name:'Invoice 42',exact:true}).waitFor();
    assert.equal(new URL(page.url()).pathname,'/common/invoices/42');checks++;
    // A refreshed common URL must recover context from the address, without session history.
    await page.goto('https://common.test/common/customers?module=srm');
    await page.addScriptTag({content:built.outputFiles[0].text});
    await page.getByRole('heading',{name:'Native page /srm/customers',exact:true}).waitFor();checks++;
    await page.evaluate(()=>window.navigate('/common/tasks?module=invalid'));
    await page.getByRole('alert').waitFor();
    assert.equal(await page.getByRole('heading').count(),0);checks++;
    console.log(`PASS: ${checks} common route, adapter, alias, context, refresh and permission scenarios`);
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});

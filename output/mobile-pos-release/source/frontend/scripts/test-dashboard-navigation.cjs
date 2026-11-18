const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { StaticRouter } = require('react-router-dom');

function load(file, imports = {}) {
  const exports = {};
  const source = fs.readFileSync(path.join(__dirname, '../src', file), 'utf8');
  const compiled = ts.transpileModule(source, {compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText;
  new Function('require', 'exports', compiled)(name => name in imports ? imports[name] : require(name), exports);
  return exports;
}
const workspaces = load('lib/navigation-workspaces.ts');
const menu = load('lib/navigation-menu.ts', {'./navigation-workspaces': workspaces});
const defaults = {groups:{},favorites:[],recent:[]};
const preferences = selector => selector({contexts:{},update:()=>{}});
preferences.getState = () => ({contexts:{}});
const Navigation = load('components/layout/ModuleNavigation.tsx', {
  '@/lib/roles': {canAccessRoute:()=>true},
  '@/lib/navigation-workspaces': workspaces,
  '@/lib/navigation-menu': menu,
  '@/store/authStore': {useAuthStore:selector=>selector({user:{id:1}})},
  '@/store/suitePreferences': {defaultSuitePreferences:defaults,suiteScope:()=>'',useSuitePreferences:preferences},
  './MenuItemMore': {default:({label})=>React.createElement('button',{'aria-label':`More options for ${label}`}),MenuItemIcon:({fallback:Icon})=>React.createElement(Icon)},
  './MenuQuickAdd': {default:()=>null},
  '@/components/app/ModuleNewMenu': {default:({children})=>children?children([]):null},
  './PMSPersonalNavigation': {default:()=>null},
  './HRPersonalNavigation': {default:()=>null},
  './CRMPersonalNavigation': {default:()=>null},
  './module-navigation.css': {},
}).default;
const icon = () => React.createElement('svg');
for (const module of ['crm','srm','fam','hrms','pms','ai-agents','power-apps']) {
  const root = `/${module}`;
  const links = [
    {to:root,label:'Dashboard',group:'Dashboard',icon},
    {to:root+'/dashboard',label:'Dashboard alias',group:'Dashboard',icon},
    {to:root+'/records',label:'Records',group:'Work',icon},
  ];
  const before = JSON.stringify(links);
  const split = menu.moduleLandingNavigation(links,module);
  assert.deepEqual(split.direct.map(item=>item.to),[root]);
  assert.deepEqual(split.grouped.map(item=>item.to),[root+'/records']);
  assert.equal(JSON.stringify(links),before);
  for (const collapsed of [false,true]) {
    const html = renderToStaticMarkup(React.createElement(StaticRouter,{location:root+'/dashboard'},
      React.createElement(Navigation,{modulePath:root,customItems:links,collapsed,onNavigate:()=>{}})));
    const landing = html.match(/<ul class="module-menu-landing"[\s\S]*?<\/ul>/)?.[0];
    assert.ok(landing, `${module} has a direct landing link`);
    assert.ok(landing.includes(`href="${root}"`));
    assert.ok(landing.includes('aria-current="page"'), 'Dashboard alias marks the direct link active');
    assert.ok(!landing.includes('module-menu-subtoggle') && !landing.includes('aria-expanded'), 'Landing has no submenu controls; record actions remain available');
    assert.ok(!html.includes('module-menu-category-name">Dashboard<'), 'No duplicate Dashboard category');
    assert.ok(!html.includes('Dashboard alias'), 'Aliases do not create another menu entry');
  }
  assert.deepEqual(menu.moduleLandingNavigation([links[2]],module).direct,[], 'Never invent an unauthorized dashboard link');
  assert.deepEqual(menu.moduleLandingNavigation([links[1]],module).direct.map(item=>item.to),[root+'/dashboard']);
  const scoped=links.map(item=>({...item,to:item.to+'?environment=testing#workspace'}));
  const scopedLanding=menu.moduleLandingNavigation(scoped,module);
  assert.deepEqual(scopedLanding.direct.map(item=>item.to),[root+'?environment=testing#workspace'],'Scoped landing links stay direct and retain their context');
  assert.deepEqual(scopedLanding.grouped.map(item=>item.to),[root+'/records?environment=testing#workspace'],'Scoped dashboard aliases do not become duplicate groups');
}
assert.deepEqual(menu.moduleLandingNavigation([{to:'/hrms/ess',label:'My dashboard'}],'hrms').direct.map(item=>item.to),['/hrms/ess']);
assert.deepEqual(menu.moduleLandingNavigation([{to:'/pms/dashboards',label:'Dashboards'}],'pms').direct.map(item=>item.to),['/pms/dashboards']);
console.log('Dashboard navigation: 7 modules, expanded/collapsed menus, aliases, access filtering, ESS and PMS library passed.');

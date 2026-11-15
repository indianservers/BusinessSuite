const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const {matchRoutes} = require('react-router-dom');
const root = path.resolve(__dirname, '../src');
let auth = {};
const cache = new Map();
const icons = new Proxy({}, {get: (_, name) => name});
function load(file) {
  file = file.replace(/\.(tsx?|jsx?)$/, '');
  if (cache.has(file)) return cache.get(file);
  const filename = ['.ts', '.tsx'].map(ext => path.join(root, file + ext)).find(fs.existsSync);
  const result = {exports: {}};
  cache.set(file, result.exports);
  const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true,
  }}).outputText;
  new Function('module', 'exports', 'require', code)(result, result.exports, name => {
    if (name === 'lucide-react') return icons;
    if (name === '@/store/authStore') return {useAuthStore:{getState:()=>auth}};
    if (name === '@/appRegistry') return {getInstalledAppKeys:()=>['srm','crm','hrms','fam','project_management'],isFrontendModuleEnabled:()=>true};
    if (name === '@/lib/lazy-route') return {lazyRoute:()=>()=>null};
    if (name === './components/SRMRouteWorkspace') return {__esModule:true,default:()=>null};
    if (name === '@/pages/settings/CentralSettingsRedirect') return {__esModule:true,default:()=>null};
    if (name.startsWith('@/')) return load(name.slice(2));
    if (name.startsWith('.')) return load(path.posix.join(path.posix.dirname(file), name));
    return require(name);
  });
  cache.set(file, result.exports);
  return result.exports;
}
const definitions = load('lib/navigation-workspaces');
const menus = load('lib/navigation-menu');
const common = load('lib/common-routes');
const roles = load('lib/roles');
const {srmRoutes} = load('apps/srm/routes');
const paths = srmRoutes.map(route => '/' + route.path);
assert.equal(new Set(paths).size, paths.length, 'Duplicate SRM route registration');
const registered = [...srmRoutes, ...['srm/forms', 'srm/connectors'].map(path=>({path}))];
const known = href => {
  const target = common.commonRouteContext(href)?.nativePath || href.split(/[?#]/)[0];
  return !target.startsWith('/srm') || Boolean(matchRoutes(registered, target));
};
let roleChecks = 0;
for (const role of ['admin','srm_admin','srm_sales_manager','srm_finance_manager','srm_revenue_manager','srm_sales_executive','srm_collection_executive','srm_business_owner','srm_viewer','employee']) {
  for (const managed of [false, true]) {
    auth = {user: {role, ...(managed ? {access:{managed:true,modules:[{key:'srm',route:'/srm'}],grants:{srm:{enabled:true,actions:['view'],permissions:['srm_view']}}}} : {})}};
    const links = roles.getRoleNav(role, false, '/srm').filter(item => roles.canAccessRoute(item.to, role, false));
    const presented = menus.moduleMenuNavigation(links, 'srm');
    const landing = menus.moduleLandingNavigation(presented, 'srm');
    const merged = [...landing.direct, ...menus.menuItems(landing.grouped)];
    const pages = merged.flatMap(menus.menuPages);
    const ids = pages.map(page => definitions.navigationOperationPath(page.to));
    assert.equal(new Set(ids).size, ids.length, `${role}/${managed}: duplicate menu destination`);
    const groups = merged.filter(item => definitions.getOperationWorkspace(item.to)).map(item=>definitions.getOperationWorkspace(item.to).label);
    assert.equal(new Set(groups).size, groups.length, `${role}/${managed}: workspace split between categories`);
    for (const link of links) {
      assert(known(link.to), `${role}: broken menu URL ${link.to}`);
      assert(ids.includes(definitions.navigationOperationPath(link.to)), `${role}: lost authorized menu ${link.to}`);
    }
    for (const href of paths) {
      const workspace = definitions.getOperationWorkspace(href);
      if (!workspace) continue;
      workspace.paths.forEach(target => assert(paths.includes(target), `Workspace points to unregistered route ${target}`));
    }
    roleChecks++;
  }
}
auth = {};
let linkChecks = 0;
const files = [];
function walk(dir) { for (const entry of fs.readdirSync(dir, {withFileTypes:true})) {
  const filename = path.join(dir, entry.name);
  if (entry.isDirectory()) walk(filename); else if (/\.tsx?$/.test(filename)) files.push(filename);
} }
walk(path.join(root, 'apps/srm'));
for (const file of ['apps/fam/FAMWorkspacePage.tsx','components/app/ModuleNewMenu.tsx','components/layout/MobileModuleDock.tsx','apps/inventory/sourceCatalog.ts']) files.push(path.join(root,file));
for (const filename of files) {
  const source = ts.createSourceFile(filename, fs.readFileSync(filename,'utf8'), ts.ScriptTarget.Latest, true);
  const visit = node => {
    let href;
    if (ts.isJsxAttribute(node) && ['to','href'].includes(node.name.getText(source)) && node.initializer && ts.isStringLiteral(node.initializer)) href=node.initializer.text;
    if (ts.isPropertyAssignment(node) && ['to','href','appPath'].includes(node.name.getText(source)) && ts.isStringLiteral(node.initializer)) href=node.initializer.text;
    if (href?.startsWith('/srm/')) {assert(known(href), `Broken SRM link ${href} in ${path.relative(root,filename)}`);linkChecks++;}
    ts.forEachChild(node, visit);
  };
  visit(source);
}
console.log(`SRM audit passed: ${paths.length} unique routes, ${roleChecks} role/access combinations, ${linkChecks} internal links; no duplicate menus or missing workspace pages.`);

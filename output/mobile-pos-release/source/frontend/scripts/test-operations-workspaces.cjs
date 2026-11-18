const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const React = require('react');
const {renderToString} = require('react-dom/server');
const router = require('react-router-dom');
function compile(file, imports) {
  const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, file), 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true}}).outputText;
  const m = {exports: {}};
  new Function('module', 'exports', 'require', code)(m, m.exports, name => imports[name] || require(name));
  return m.exports;
}
const common = compile('../src/lib/common-routes.ts', {});
const definitions = compile('../src/lib/navigation-workspaces.ts', {'./common-routes': common, './navigation-categories': compile('../src/lib/navigation-categories.ts', {})});
const menus = compile('../src/lib/navigation-menu.ts', {'./navigation-workspaces': definitions, './common-routes': common, './navigation-categories': compile('../src/lib/navigation-categories.ts', {})});
const tasks = compile('../src/lib/task-workspace.ts', {});
const denied = new Set();
const Workspace = compile('../src/components/layout/OperationsWorkspace.tsx', {
  '@/lib/navigation-workspaces': definitions,
  '@/lib/common-routes': common,
  '@/lib/navigation-menu': menus,
  '@/lib/task-workspace': tasks,
  '@/lib/operation-panel': compile('../src/lib/operation-panel.ts', {}),
  '@/components/ui/state': {LoadingState: () => null},
  '@/lib/roles': {canAccessRoute: p => !denied.has(p), getRoleNav: () => []},
  '@/store/authStore': {useAuthStore: fn => fn({user: {role: 'admin', is_superuser: true}})},
  '@/components/app/ErrorBoundary': {__esModule: true, default: ({children}) => children},
}).default;
const routes = ['pms/time-tracking', 'pms/timesheets', 'hrms/payroll', 'hrms/investment-declaration', 'crm/deals', 'crm/pipeline', 'srm/inventory', 'srm/inventory/stock-summary', 'srm/inventory/warehouses', 'srm/invoices', 'srm/collections'].map(p => ({path: p, element: React.createElement('form', {'data-operation': p}, React.createElement('button', null, 'Save ' + p))}));
function render(primary, operation) {
  return renderToString(React.createElement(router.MemoryRouter, {initialEntries: ['/' + primary + '?operation=' + encodeURIComponent(operation)]}, React.createElement(Workspace, {route: routes.find(r => r.path === primary), routes})));
}
for (const [primary, secondary] of [['pms/time-tracking', '/pms/timesheets'], ['hrms/payroll', '/hrms/investment-declaration'], ['crm/deals', '/crm/pipeline'], ['srm/inventory', '/srm/inventory/stock-summary'], ['srm/invoices', '/srm/collections']]) {
  const html = render(primary, secondary);
  assert(html.includes('data-operation="' + secondary.slice(1) + '"'), 'Actual operation form missing');
  if(primary === 'crm/deals') { assert(!html.includes('role="tab"'), 'Deals uses the single workspace navigation'); assert(html.includes('role="tabpanel"'), 'Deal operation panel missing'); }
  else assert(html.includes('role="tab"'), 'Operation tabs missing');
  assert(!html.includes('<a '), 'Operations must render in place');
}
denied.add('/hrms/investment-declaration');
const restricted = render('hrms/payroll', '/hrms/investment-declaration');
assert(!restricted.includes('data-operation="hrms/investment-declaration"'));
assert(restricted.includes('data-operation="hrms/payroll"'));
console.log('Operations workspace: embedded forms, tabs, and denied-operation fallback passed.');

denied.add('/srm/inventory/warehouses');
const stockRestricted = render('srm/inventory', '/srm/inventory/warehouses');
assert(!stockRestricted.includes('data-operation="srm/inventory/warehouses"'));
assert(stockRestricted.includes('data-operation="srm/inventory"'));
assert.equal(definitions.getOperationWorkspace('/srm/inventory/dashboard').label, 'Stock & warehouses');
assert.equal(definitions.getOperationWorkspace('/srm/inventory/products').label, 'Products & pricing');
console.log('SRM stock and billing: embedded operations, legacy aliases and permission fallback passed.');

const panels = compile('../src/lib/operation-panel.ts', {});
const SrmRouteWorkspace = compile('../src/apps/srm/components/SRMRouteWorkspace.tsx', {
  '@/lib/operation-panel': panels,
  '@/components/layout/OperationsWorkspace': {__esModule:true,default:({route})=>React.createElement('section', {'data-operation-shell':true}, route.element)},
}).default;
const original = {path:'srm/sales-orders',element:React.createElement('form', {'data-original-manager':true})};
const renderSrm = activeContent => renderToString(React.createElement(panels.OperationWorkspaceContext.Provider, {value:true},
  React.createElement(panels.OperationContentContext.Provider, {value:activeContent},
    React.createElement(SrmRouteWorkspace, {route:original,routes:[original]}))));
assert(renderSrm(false).includes('data-operation-shell'), 'A shared route host must retain the SRM workspace tabs');
assert(!renderSrm(true).includes('data-operation-shell'), 'A manager inside an existing panel must not add nested tabs');
assert(renderSrm(true).includes('data-original-manager'), 'Embedding must preserve the original working manager');
console.log('SRM route ownership: shared hosts retain tabs and embedded managers avoid nested workspaces.');

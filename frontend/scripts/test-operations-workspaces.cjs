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
const definitions = compile('../src/lib/navigation-workspaces.ts', {});
const common = compile('../src/lib/common-routes.ts', {});
const menus = compile('../src/lib/navigation-menu.ts', {'./navigation-workspaces': definitions, './common-routes': common});
const tasks = compile('../src/lib/task-workspace.ts', {});
const denied = new Set();
const Workspace = compile('../src/components/layout/OperationsWorkspace.tsx', {
  '@/lib/navigation-workspaces': definitions,
  '@/lib/navigation-menu': menus,
  '@/lib/task-workspace': tasks,
  '@/components/ui/state': {LoadingState: () => null},
  '@/lib/roles': {canAccessRoute: p => !denied.has(p), getRoleNav: () => []},
  '@/store/authStore': {useAuthStore: fn => fn({user: {role: 'admin', is_superuser: true}})},
  '@/components/app/ErrorBoundary': {__esModule: true, default: ({children}) => children},
}).default;
const routes = ['pms/time-tracking', 'pms/timesheets', 'hrms/payroll', 'hrms/investment-declaration', 'crm/deals', 'crm/pipeline'].map(p => ({path: p, element: React.createElement('form', {'data-operation': p}, React.createElement('button', null, 'Save ' + p))}));
function render(primary, operation) {
  return renderToString(React.createElement(router.MemoryRouter, {initialEntries: ['/' + primary + '?operation=' + encodeURIComponent(operation)]}, React.createElement(Workspace, {route: routes.find(r => r.path === primary), routes})));
}
for (const [primary, secondary] of [['pms/time-tracking', '/pms/timesheets'], ['hrms/payroll', '/hrms/investment-declaration'], ['crm/deals', '/crm/pipeline']]) {
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

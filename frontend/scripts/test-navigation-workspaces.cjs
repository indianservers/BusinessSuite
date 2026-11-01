const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
const source = fs.readFileSync(require('node:path').join(__dirname, '../src/lib/navigation-workspaces.ts'), 'utf8');
const mod = {exports:{}};
new Function('exports', ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText)(mod.exports);
const {consolidateNavigation, activeWorkspace} = mod.exports;
const paths = ['/pms/tasks','/pms/navigator','/pms/issue-navigator-pro','/pms/projects','/hrms/payroll','/hrms/my-payslips','/crm/communication-hub','/crm/emails'];
const links = paths.map(to => ({to, label:to, group:to.split('/')[1]}));
const before = JSON.stringify(links);
const merged = consolidateNavigation(links);
assert.equal(merged.length, 4);
assert.deepEqual(merged.flatMap(i => i.pages || [i]).map(i => i.to).sort(), paths.sort());
assert.equal(JSON.stringify(links), before);
assert.equal(activeWorkspace(merged, '/pms/tasks/123').label, 'Tasks');
assert.equal(activeWorkspace(merged, '/crm/emails').label, 'Communication & Campaigns');
assert.equal(activeWorkspace(merged, '/crm/emails-unknown'), undefined);
const restricted = consolidateNavigation(links.filter(i => i.to === '/hrms/my-payslips'));
assert.equal(restricted[0].to, '/hrms/my-payslips');
assert.deepEqual(restricted[0].pages.map(i => i.to), ['/hrms/my-payslips']);
assert.deepEqual(consolidateNavigation([]), []);
console.log('Workspace consolidation: all links retained, restricted fallback, active details, and fewer entries passed.');

const {workspacePageHref} = mod.exports;
assert.equal(workspacePageHref('/pms/tasks', '?workspace=2&layout=table'), '/pms/tasks?workspace=2');
assert.equal(workspacePageHref('/pms/tasks?layout=gallery', '?workspace=2'), '/pms/tasks?layout=gallery&workspace=2');
assert.equal(workspacePageHref('/pms/tasks?workspace=3', '?workspace=2'), '/pms/tasks?workspace=3');
assert.equal(workspacePageHref('/pms/tasks', '', 4), '/pms/tasks?workspace=4');
assert.equal(workspacePageHref('/hrms/payroll', '?workspace=2'), '/hrms/payroll');
console.log('Workspace context preservation passed.');
const menuSource = fs.readFileSync(require('node:path').join(__dirname, '../src/lib/navigation-menu.ts'), 'utf8');
const menuMod = {exports:{}};
new Function('exports', 'require', ts.transpileModule(menuSource, {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText)(menuMod.exports, () => mod.exports);
const {menuItems, menuLabel, menuMatches, menuPages} = menuMod.exports;
const grouped = [{to:'/crm/emails',label:'Emails',group:'Communication'}, {to:'/crm/campaigns',label:'Campaigns',group:'Marketing'}];
assert.equal(menuItems(grouped).length, 2, 'Cross-category consolidation must retain distinct categories');
assert.equal(menuLabel({to:'/pms/tasks',label:'Tasks'}), 'All tasks');
assert.ok(menuMatches({to:'/crm/quotations',label:'Quotations',group:'Sales'}, 'quotes'));
assert.ok(menuMatches({to:'/crm/quotations',label:'Quotations',group:'Sales'}, 'quotations'));
assert.equal(menuPages({to:'/pms/tasks',label:'Tasks',pages:[{to:'/pms/tasks',label:'Tasks'},{to:'/pms/navigator',label:'Navigator'}]}).length, 1);
assert.equal(menuItems([{to:'/pms/projects',label:'Projects',group:'Work'}, {to:'/pms/tasks',label:'Tasks',group:'Work'}])[0].to, '/pms/tasks');
console.log('Menu category boundaries, friendly/original search, alias deduplication and daily-work ordering passed.');

const internLinks = ['interns', 'interns/operations', 'interns/list', 'interns/batches'].map(path => ({to:'/hrms/'+path,label:path,group:'People'}));
const internMenu = menuItems(internLinks);
assert.equal(internMenu.length, 1);
assert.deepEqual(internMenu[0].pages, internLinks);
const singleGoal = menuItems([{to:'/pms/goals',label:'Goals',group:'Planning'}]);
assert.equal(menuLabel(singleGoal[0]), 'Goals', 'A single planning page must not inherit an administration label');
console.log('Intern pages retained under one hub and single-page labels preserved.');

for (const paths of [["/crm/deals", "/crm/pipeline", "/crm/templates"], ["/crm/forms", "/crm/webforms"], ["/pms/live", "/pms/teams-live"]]) {
  const result = menuItems(paths.map(to => ({to,label:to,group:"Same category"})));
  assert.equal(result.length, 1);
  assert.deepEqual(result[0].pages.map(page => page.to).sort(), [...paths].sort());
}
console.log("CRM deal/form and PMS live-work consolidation checks passed.");

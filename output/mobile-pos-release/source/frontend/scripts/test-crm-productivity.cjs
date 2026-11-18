const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const memory = new Map();
global.localStorage = {getItem: key => memory.get(key) ?? null, setItem: (key, value) => memory.set(key, value), removeItem: key => memory.delete(key)};
function load() {
  const source = fs.readFileSync(path.resolve(__dirname, '../src/apps/crm/productivityStore.ts'), 'utf8');
  const output = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020}}).outputText;
  const mod = {exports: {}};
  new Function('module', 'exports', 'require', output)(mod, mod.exports, require);
  return mod.exports;
}
const {useCRMProductivity: store, crmScope} = load();
const mine = crmScope(12, 4), colleague = crmScope(13, 4), otherOrg = crmScope(12, 5);
const first = {path: '/crm/deals/42', label: 'Renewal'}, second = {path: '/crm/companies/7', label: 'Customer'};
store.getState().pin(mine, first); store.getState().pin(mine, second);
store.getState().move(mine, second.path, -1);
for (let i = 0; i < 5; i++) store.getState().visit(mine, first);
assert.deepEqual(store.getState().scopes[mine].pins, [second, first], 'Visits must not reorder favorites');
assert.equal(store.getState().scopes[mine].visits[first.path].count, 5);
assert.equal(store.getState().scopes[colleague], undefined, 'Preferences must be personal');
assert.equal(store.getState().scopes[otherOrg], undefined, 'Preferences must be organization specific');
assert.deepEqual(load().useCRMProductivity.getState().scopes[mine].pins, [second, first], 'Chosen order survives reload');
store.getState().pin(mine, second);
assert.deepEqual(store.getState().scopes[mine].pins, [first], 'Unpin removes only the chosen favorite');
console.log('PASS CRM favorites: stable ordering, persistence, visit counts, account and organization isolation');

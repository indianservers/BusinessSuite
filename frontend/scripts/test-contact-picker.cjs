const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/shared/master-data/contact-picker.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const exported = {};
vm.runInNewContext(compiled, { exports: exported });
const parse = exported.contactPickerResponse;
assert.equal(parse({ items: [], total: 0 }).items.length, 0);
const contact = { id: 9, name: 'QA contact', email: null };
assert.equal(parse({ items: [contact], total: 1 }).items[0], contact);
for (const malformed of [undefined, '<html>Unexpected app shell</html>', {}, { items: null },
  { items: {} }, { items: [null] }, { items: [{ id: 0, name: 'Invalid' }] },
  { items: [{ id: 1, name: undefined }] }, { items: [{ id: 1, name: 'QA', email: {} }] }]) {
  assert.throws(() => parse(malformed), /Contact persons could not be loaded/);
}
console.log('11 contact-picker response regression scenarios passed');

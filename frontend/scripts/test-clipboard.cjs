const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/lib/clipboard.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
function load(clipboard) {
  const exports = {};
  vm.runInNewContext(compiled, { exports, navigator: { clipboard }, setTimeout, clearTimeout });
  return exports.writeClipboard;
}

(async () => {
  let copied;
  await load({ writeText: async text => { copied = text; } })('QA export');
  assert.equal(copied, 'QA export');
  await assert.rejects(load(undefined)('QA export'), /unavailable/);
  await assert.rejects(load({ writeText: async () => { throw new Error('Permission denied'); } })('QA export'), /Permission denied/);
  // Reproduce a browser permission prompt that never settles its promise.
  await assert.rejects(load({ writeText: () => new Promise(() => {}) })('QA export', 5), /not confirmed/);
  console.log('4 clipboard regression scenarios passed');
})().catch(error => { console.error(error); process.exitCode = 1; });

const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('../frontend/node_modules/typescript');
const source = fs.readFileSync('frontend/src/apps/communication/whatsapp/EmbeddedSignup.tsx', 'utf8');
const parsed = ts.createSourceFile('EmbeddedSignup.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const loader = parsed.statements.find(node => ts.isFunctionDeclaration(node) && node.name.text === 'loadSDK');
const code = ts.transpileModule(loader.getText(parsed) + '\nmodule.exports=loadSDK;', { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
(async () => {
  let stubCalls = 0, previousCalls = 0, element;
  const window = { FB: { __buffer: {}, init() { stubCalls++; }, login() { stubCalls++; } },
    setTimeout, clearTimeout, fbAsyncInit() { previousCalls++; } };
  const document = { getElementById() { return element || null; }, createElement() {
    return element = { isConnected: false, handlers: {}, addEventListener(event, callback) { this.handlers[event] = callback; } };
  }, body: { appendChild(script) { script.isConnected = true; } } };
  const context = { window, document, module: { exports: null } };
  vm.runInNewContext(code, context);
  let resolved = false;
  const promise = context.module.exports().then(value => { resolved = true; return value; });
  element.handlers.load(); await new Promise(setImmediate);
  assert.equal(resolved, false, 'The loader load event must not resolve the buffering placeholder');
  const sdk = { init() {}, login() {} };
  window.FB = sdk; window.fbAsyncInit();
  assert.equal(await promise, sdk);
  assert.equal(previousCalls, 1);
  assert.equal(stubCalls, 0);
  assert.equal(await context.module.exports(), sdk, 'Subsequent mounts reuse the real SDK');
  console.log('PASS: SDK loader waits for fbAsyncInit, ignores buffering placeholder, chains prior callback and reuses the real SDK.');
})().catch(error => { console.error(error); process.exitCode = 1; });

const assert = require('node:assert/strict');
const path = require('node:path');
const vm = require('node:vm');
const { buildSync } = require('esbuild');

const root = path.resolve(__dirname, '..');
const bundled = buildSync({
  absWorkingDir: root,
  stdin: { contents: "export { selectedConstruction } from './src/lib/selected-construction'; export { selectedPackContext, clearPackContext, setPackContext } from './src/lib/pack-context';", resolveDir: root, sourcefile: 'actual-native-selection-entry.ts', loader: 'ts' },
  tsconfig: path.join(root, 'tsconfig.json'),
  bundle: true, platform: 'node', format: 'cjs', write: false,
}).outputFiles[0].text;

function securityError(message) { const error = new Error(message); error.name = 'SecurityError'; return error; }
class StorageMap {
  constructor(values = {}, denied = {}) { this.values = new Map(Object.entries(values)); this.denied = denied; this.writes = []; }
  getItem(key) { if (this.denied.read === true || this.denied.read === key) throw securityError('Storage read denied'); return this.values.get(key) ?? null; }
  setItem(key, value) { if (this.denied.write === true || this.denied.write === key) throw securityError('Storage write denied'); this.writes.push(key); this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
}

function storage(overrides = {}, denied) {
  return new StorageMap({
    'suite-organization': '1', 'suite-branch': '7',
    'suite-pack-context': '41', 'suite-business-pack-context': '41',
    'suite-pack-context-owner': JSON.stringify([null, '1', '7']), ...overrides,
  }, denied);
}
const choice = { contextId: 41, branchId: 7, packKey: 'construction', packVersion: 1, contextRevision: 2, grantRevision: 3, activationRevision: 4, role: 'project_manager' };
function discovery(overrides = {}) {
  return { state: 'ready', hasMore: false, selectionState: 'verified', selectedContextId: 41, contexts: [{ ...choice }], ...overrides };
}
function user(value = discovery()) { return { id: 11, access: { companyId: 1, businessPacks: value } }; }
function load(nativeStorage, deniedGetter = false, browser = false) {
  const module = { exports: {} }, context = { module, exports: module.exports };
  const events = new Map();
  if (browser) { context.window = { addEventListener(name, callback) { events.set(name, callback); }, dispatchEvent() {} }; context.Event = Event; }
  let reads = 0;
  if (!deniedGetter) Object.defineProperty(context, 'sessionStorage', { get() { reads++; return nativeStorage; } });
  else context.recordStorageRead = () => { reads++; };
  vm.createContext(context);
  // A throwing host-global getter becomes ReferenceError in Node VM. Defining
  // the getter in its own realm preserves the browser's actual SecurityError.
  if (deniedGetter) vm.runInContext("Object.defineProperty(globalThis, 'sessionStorage', { get() { recordStorageRead(); const error = new Error('Storage getter denied'); error.name = 'SecurityError'; throw error; } });", context);
  vm.runInContext(bundled, context, { filename: 'actual-selected-construction.bundle.cjs' });
  // The real pack-context module skips its browser-only startup when window is undefined.
  if (!browser) assert.equal(reads, 0);
  return { select: module.exports.selectedConstruction, native: module.exports.selectedPackContext, clear: module.exports.clearPackContext, set: module.exports.setPackContext, reads: () => reads, events };
}

let count = 0;
function check(label, actor, nativeStorage, expected, deniedGetter = false) {
  const actual = load(nativeStorage, deniedGetter);
  assert.equal(actual.select(actor), expected, label);
  count++;
  return actual;
}

check('verified native Construction selection', user(), storage(), true);
const normalized = storage(); normalized.values.delete('suite-pack-context-owner');
check('real pack-context establishes its native ownership marker', user(), normalized, true);
assert.deepEqual(normalized.writes, ['suite-pack-context-owner']);

for (const [label, value] of [
  ['missing discovery', undefined],
  ['unavailable discovery', discovery({ state: 'unavailable' })],
  ['incomplete discovery', discovery({ hasMore: true })],
  ['invalid discovery selection', discovery({ selectionState: 'invalid' })],
]) {
  const actual = check(label, { id: 11, access: { companyId: 1, businessPacks: value } }, undefined, false, true);
  assert.equal(actual.reads(), 0, `${label} must fail before accessing storage`);
}
check('denied sessionStorage getter', user(), undefined, false, true);
check('denied branch storage read', user(), storage({}, { read: 'suite-branch' }), false);
check('denied selectedPackContext native read', user(), storage({}, { read: 'suite-pack-context' }), false);
const deniedOwner = storage({}, { write: 'suite-pack-context-owner' }); deniedOwner.values.delete('suite-pack-context-owner');
check('denied selectedPackContext ownership write', user(), deniedOwner, false);
const deniedCanonical = storage({}, { write: 'suite-pack-context' }); deniedCanonical.values.delete('suite-pack-context');
check('denied selectedPackContext canonical migration write', user(), deniedCanonical, false);

check('foreign branch', user(), storage({ 'suite-branch': '8', 'suite-pack-context-owner': JSON.stringify([null, '1', '8']) }), false);
check('selector does not match verified discovery', user(), storage({ 'suite-pack-context': '42', 'suite-business-pack-context': '42' }), false);
check('conflicting native selectors', user(), storage({ 'suite-business-pack-context': '42' }), false);
check('malformed native selector', user(), storage({ 'suite-pack-context': 'bad', 'suite-business-pack-context': 'bad' }), false);
check('missing eligible context', user(discovery({ contexts: [] })), storage(), false);
check('nonpositive revision', user(discovery({ contexts: [{ ...choice, grantRevision: 0 }] })), storage(), false);
for (const packKey of ['hospital', 'restaurant']) {
  check(`selected ${packKey} stays separate from another Construction assignment`, user(discovery({ contexts: [
    { ...choice, packKey }, { ...choice, contextId: 42 },
  ] })), storage(), false);
}
check('one implicitly selected native Construction context', user(discovery({ selectionState: 'none', selectedContextId: null })), new StorageMap({ 'suite-organization': '1', 'suite-branch': '7' }), true);
check('ambiguous implicit native contexts', user(discovery({ selectionState: 'none', selectedContextId: null, contexts: [{ ...choice }, { ...choice, contextId: 42 }] })), new StorageMap({ 'suite-organization': '1', 'suite-branch': '7' }), false);

for (const [label, nativeStorage, deniedGetter] of [
  ['getter', storage(), true],
  ['read', storage({}, { read: true }), false],
  ['ownership write', deniedOwner, false],
  ['canonical migration write', deniedCanonical, false],
]) {
  const before = [...nativeStorage.values];
  const actual = load(nativeStorage, deniedGetter, true);
  assert.equal(actual.select(user()), false, `browser startup ${label} must leave the hint unavailable`);
  assert.throws(() => actual.native(), error => error.name === 'SecurityError', `explicit native ${label} must still throw`);
  assert.equal(actual.events.size, 3);
  for (const callback of actual.events.values()) assert.doesNotThrow(() => callback(), `browser event ${label} must not crash navigation`);
  assert.deepEqual([...nativeStorage.values], before, `browser startup/events ${label} must not invent a legacy selection or alter storage`);
  count++;
}
const legacyStorage = new StorageMap({ 'suite-organization': '1', 'suite-branch': '7' });
const legacy = load(legacyStorage, false, true);
assert.equal(legacy.native(), null);
for (const callback of legacy.events.values()) callback();
assert.deepEqual([...legacyStorage.values], [['suite-organization', '1'], ['suite-branch', '7']]);
const conflict = load(storage({ 'suite-business-pack-context': '42' }), false, true);
assert.equal(conflict.native(), '!conflicting-pack-context');
assert.equal(conflict.select(user()), false);
const malformed = load(storage({ 'suite-pack-context': 'bad', 'suite-business-pack-context': 'bad' }), false, true);
assert.equal(malformed.native(), 'bad');
assert.equal(malformed.select(user()), false);
const deniedExplicit = load(storage({}, { read: true, write: true }), false, true);
assert.throws(() => deniedExplicit.clear(), error => error.name === 'SecurityError');
assert.throws(() => deniedExplicit.set('41'), error => error.name === 'SecurityError');
assert.throws(() => deniedExplicit.set('invalid'), /Select a positive Business Pack context identity/);
count += 4;

console.log(`PASS selected Construction UI hint: ${count} actual-helper cases; native storage denial fails closed without changing server authority.`);

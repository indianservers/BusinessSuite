const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname, '../src/features/access/refresh-current-access.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
let state, branch, company, writes;
const options = () => ({ queryKey: ['suite-access', state.user?.id, company, branch] });
const moduleStub = { exports: {} };
vm.runInNewContext(compiled, { exports: moduleStub.exports, require: id => id.includes('authStore') ? { useAuthStore: { getState: () => state } } : { accessQueryOptions: options } });
const refresh = moduleStub.exports.refreshCurrentAccess;
function reset() { branch = null; company = 1; writes = []; state = { isAuthenticated: true, user: { id: 1, role: 'custom' }, setUser: user => { writes.push(user); state.user = user; } }; }
(async () => {
 reset(); let calls = 0;
 await refresh({ fetchQuery: async () => { calls++; if (calls === 1) { branch = '7'; return { managed: true, marker: 'old-branch' }; } return { managed: true, marker: 'current-branch' }; } });
 assert.equal(calls, 2); assert.equal(writes.length, 1); assert.equal(state.user.access.marker, 'current-branch');
 reset(); calls = 0;
 await refresh({ fetchQuery: async () => { calls++; if (calls === 1) { company = 2; state.user = { id: 2, role: 'viewer' }; return { managed: true, marker: 'old-account' }; } return { managed: true, marker: 'new-account' }; } });
 assert.equal(writes.length, 1); assert.equal(state.user.id, 2); assert.equal(state.user.access.marker, 'new-account');
 reset(); await refresh({ fetchQuery: async () => { state.isAuthenticated = false; state.user = null; return { managed: true }; } });
 assert.equal(writes.length, 0); assert.equal(state.user, null);
 reset(); await refresh({ fetchQuery: async () => ({ unexpected: true }) }); assert.equal(writes.length, 0);
 reset(); calls = 0; await refresh({ fetchQuery: async () => { calls++; branch = String(calls); return { managed: true }; } }); assert.equal(calls, 3); assert.equal(writes.length, 0);
 reset(); await assert.rejects(refresh({ fetchQuery: async () => { throw Error('offline'); } }), /offline/); assert.equal(writes.length, 0);
 console.log('PASS permission refresh: default branch race, account/company change, logout, malformed response, bounded churn, offline');
})().catch(error => { console.error(error); process.exitCode = 1; });

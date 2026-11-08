// Company-bound QA identities exercise real approval rules without changing existing users.
const fs = require('node:fs'), crypto = require('node:crypto');
const { auth } = require('./custom_fields_live.cjs');
const file = '.tmp/workflow-board-live-records.json';
const state = JSON.parse(fs.readFileSync(file, 'utf8'));
const save = () => fs.writeFileSync(file, JSON.stringify(state, null, 2));
const root = 'http://127.0.0.1:1534/api/v1';
async function apiFor(token, step) {
  return async (url, method = 'GET', data) => {
    const r = await fetch(root + url, { method, headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json', 'X-Suite-Organization': '1', 'X-Suite-Branch': '6', ...(step ? { 'X-Access-Step-Up': step } : {}) }, body: data === undefined ? undefined : JSON.stringify(data) });
    const body = r.status === 204 ? null : await r.json();
    if (!r.ok) throw Error(`${method} ${url}: ${r.status} ${JSON.stringify(body)}`);
    return body;
  };
}
async function session(actor) {
  const response = await fetch(root + '/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: actor.email, password: actor.password }) });
  if (!response.ok) throw Error('QA identity login failed: ' + response.status);
  const login = await response.json(), api = await apiFor(login.access_token);
  return { login, api, actor: await api('/auth/me'), access: await api('/access/me') };
}
async function prepare() {
  const a = await auth();
  const password = fs.readFileSync('backend/app/db/init_db.py', 'utf8').match(/"email": "admin@aihrms.com",\s*"password": "([^"]+)"/)[1];
  const step = await a.api('/access/step-up', 'POST', { password });
  const admin = await apiFor(a.login.access_token, step.token);
  state.qaActors ||= {}; save();
  for (const name of ['requester', 'reviewer']) {
    if (state.qaActors[name]) continue;
    const credential = { email: `${state.run.toLowerCase()}-${name}@example.com`, password: 'Qa7!' + crypto.randomBytes(20).toString('hex') };
    const created = await admin('/access/users', 'POST', { companyId: 1, name: `${state.run} ${name}`, ...credential, invite: false, reason: 'Temporary dashboard live verification' });
    state.qaActors[name] = { id: created.user.id, ...credential }; save();
    await admin('/access/memberships', 'POST', { companyId: 1, userId: created.user.id, active: true, isAdmin: false, reason: 'Temporary dashboard verification company identity' });
    const actions = name === 'requester' ? ['view', 'create', 'edit', 'configure'] : ['view', 'approve'];
    const permissions = name === 'requester' ? ['view', 'create', 'edit', 'execute', 'publish', 'approval_submit', 'approval_manage', 'activity_view'] : ['view', 'approval_decide'];
    await admin('/access/changes/apply', 'POST', { companyId: 1, changes: [{ userId: created.user.id, version: created.user.version, grants: { power_apps: { enabled: true, role: 'Dashboard verification ' + name, scope: 'organization', actions, permissions: permissions.map(p => 'power_apps_' + p) } } }], reason: 'Temporary Power Apps-only dashboard verification' });
    const branch = await admin('/branches/access/' + created.user.id);
    await admin('/branches/access/' + created.user.id, 'PUT', { expected_version: branch.version, all_branches: false, manage_access: false, use_home_branch: false, grants: [{ branch_id: 6, can_write: true }], reason: 'Temporary dashboard verification in Main Branch' });
  }
  const requester = await session(state.qaActors.requester);
  if (!state.records.qaPolicy) {
    const policy = await requester.api('/power-apps/approvals/policies?environment=development', 'POST', { name: state.run + ' verified approval', definition: { stages: [{ id: 'review', name: 'Live verification review', selectors: [{ kind: 'user', ids: [state.qaActors.reviewer.id] }] }], fields: [], prohibit_self_approval: true, documents_required: false } });
    state.records.qaPolicy = { id: policy.id, version: policy.version, name: policy.name }; save();
    await requester.api(`/power-apps/approvals/policies/${policy.id}/activate?environment=development&expected_version=${policy.version}`, 'POST');
  }
  if (!state.records.approval) {
    const r = await requester.api('/power-apps/approvals/requests?environment=development', 'POST', { policy_id: state.records.qaPolicy.id, title: state.run + ' dashboard approval', description: 'Temporary live dashboard verification; no purchase or payment.', request_key: state.run, fields: {} });
    state.records.approval = { id: r.id, title: r.title, status: r.status }; save();
  }
  console.log(JSON.stringify({ createdCompanyBoundQaUsers: Object.values(state.qaActors).map(u => u.id), approval: state.records.approval }));
}
module.exports = { session, apiFor };
if (require.main === module) prepare().catch(error => { console.error(error.message); save(); process.exitCode = 1; });

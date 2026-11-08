const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { auth } = require('./custom_fields_live.cjs');
const { session } = require('./workflow_board_live_approval_records.cjs');
(async () => {
  const file = '.tmp/workflow-board-live-records.json', state = JSON.parse(fs.readFileSync(file, 'utf8'));
  const admin = await auth(), requester = await session(state.qaActors.requester);
  for (const [key, identity] of [['policy', admin], ['qaPolicy', requester]]) {
    const record = state.records[key];
    const detail = (await identity.api('/power-apps/approvals/policies?environment=development')).items.find(policy => policy.id === record.id);
    assert(detail.name.startsWith(state.run));
    if (detail.enabled) await identity.api(`/power-apps/approvals/policies/${record.id}/disable?environment=development&expected_version=${detail.version}`, 'POST');
  }
  require('node:child_process').execFileSync(path.resolve('backend/venv/Scripts/python.exe'), [path.resolve('qa/cleanup_workflow_board_live.py')], { cwd: path.resolve('backend'), windowsHide: true, stdio: 'inherit' });
  for (const actor of Object.values(state.qaActors)) delete actor.password;
  state.cleanedUp = new Date().toISOString();
  fs.writeFileSync(file, JSON.stringify(state, null, 2));
})().catch(error => { console.error(error.message); process.exitCode = 1; });

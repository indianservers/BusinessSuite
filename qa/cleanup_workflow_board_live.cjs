const fs = require('node:fs'), path = require('node:path');
(async () => {
  const file = '.tmp/workflow-board-live-records.json', state = JSON.parse(fs.readFileSync(file, 'utf8'));
  require('node:child_process').execFileSync(path.resolve('backend/venv/Scripts/python.exe'), [path.resolve('qa/cleanup_workflow_board_live.py')], { cwd: path.resolve('backend'), windowsHide: true, stdio: 'inherit' });
  for (const actor of Object.values(state.qaActors)) delete actor.password;
  state.cleanedUp = new Date().toISOString();
  fs.writeFileSync(file, JSON.stringify(state, null, 2));
})().catch(error => { console.error(error.message); process.exitCode = 1; });

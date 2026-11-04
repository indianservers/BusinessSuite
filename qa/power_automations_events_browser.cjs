// Run from the repository root after power_automations_events_e2e.py.
const fs = require('fs');
const { chromium } = require('../frontend/node_modules/playwright');
const { execFileSync } = require('child_process');

(async () => {
  const cases = JSON.parse(fs.readFileSync('.local/automation-events-verified.json', 'utf8'));
  const token = execFileSync('venv/Scripts/python.exe', ['-c', 'from app.core.security import create_access_token; print(create_access_token(26))'], { cwd: 'backend', encoding: 'utf8' }).trim();
  const raw = await fetch('http://127.0.0.1:1534/api/v1/auth/me', { headers: { Authorization: 'Bearer ' + token } }).then(response => response.json());
  const user = { ...raw, role: typeof raw.role === 'object' ? raw.role?.name : raw.role };
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.addInitScript(({ token, user }) => {
    sessionStorage.setItem('suite-branch', '1');
    sessionStorage.setItem('hrms-auth', JSON.stringify({ state: { accessToken: token, refreshToken: '', user, isAuthenticated: true }, version: 0 }));
  }, { token, user });
  let checks = 0;
  try {
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      for (const entry of cases) {
        await page.goto(`http://127.0.0.1:5173/power-apps/automations/executions/${entry.run_id}?environment=development`);
        await page.getByRole('heading', { name: 'Execution audit timeline', exact: true }).waitFor({ timeout: 30000 });
        const status = (await page.locator('.rt-run-meta .rt-status').innerText()).trim().toLowerCase();
        const expected = entry.case === 'cancel_delay' ? 'cancelled' : entry.case === 'api_failure' ? 'failed' : 'completed';
        if (status !== expected) throw Error(`${entry.case}: expected ${expected}, received ${status}`);
        if (entry.case === 'api_failure' && !(await page.locator('.rt-run-meta .rt-error').innerText()).includes('HTTP 404')) throw Error('Remote HTTP error missing');
        const timeline = (await page.locator('.rt-events').innerText()).toLowerCase();
        if (entry.case === 'delay' && !timeline.includes('resumed')) throw Error('Resume audit event missing');
        if (entry.case === 'webhook' && !timeline.includes('structured log')) throw Error('Webhook log missing');
        checks++;
      }
      await page.screenshot({ path: `.local/automation-events-ui-${width}.png`, fullPage: true });
      console.log(`All 8 execution pages and logs passed at ${width}px`);
    }
    console.log(`${checks} live UI checks passed`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exit(1); });

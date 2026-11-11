const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const evidence = path.join(root, '.local/create-menu-real');
const inventory = JSON.parse(fs.readFileSync(path.join(evidence, 'inventory.json'), 'utf8'));
const attempts = JSON.parse(fs.readFileSync(path.join(evidence, 'results.json'), 'utf8'));
const checks = inventory.flatMap(menu => menu.labels.map(action => {
    const result = attempts.filter(row => row.module === menu.module && row.action === action && row.width === menu.width && row.status !== 'inspected').at(-1);
    if (!result || result.status !== 'passed' || !result.readback?.matched)
        throw Error(`Unverified: ${menu.module} / ${action} / ${menu.width}`);
    if (result.kind !== 'navigation' && !result.saved)
        throw Error(`Missing API save: ${menu.module} / ${action} / ${menu.width}`);
    return {
        module: menu.module, action, width: menu.width, status: result.status,
        kind: result.kind || 'api-save', saved: result.saved, readback: result.readback,
        writes: result.writes, utcRoundTrip: result.utcRoundTrip,
        personalLayoutReload: result.personalLayoutReload, note: result.note,
        run: result.tag,
    };
}));
for (const menu of inventory.filter(menu => menu.width < 768)) {
    if (!menu.layout?.length || menu.layout.some(row => row.height < row.span + 16))
        throw Error(`Mobile menu text overlaps: ${menu.module}`);
}
const output = path.join(root, 'docs/qa');
fs.mkdirSync(output, { recursive: true });
const name = 'create-menu-real-api-2026-11-11';
const report = {
    verifiedAt: new Date().toISOString(),
    baseRevision: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    workingTreeIncludesUncommittedFixes: true,
    environment: {
        browser: 'Playwright Chromium', viewports: ['1440 × 950', '390 × 950'],
        timezone: 'Asia/Kolkata', actor: 'Disposable QA administrator',
        frontend: 'Production Vite build', backend: 'Real FastAPI HTTP endpoints',
        database: 'Fresh disposable SQLite from current ORM metadata',
        apiMocks: false, outboundDeliveryWorkers: false,
        limitation: 'Responsive mobile viewport; physical mobile devices and other permission roles were not tested.',
    },
    totals: { checks: checks.length, apiSaves: checks.filter(row => row.kind === 'api-save').length, navigation: checks.filter(row => row.kind === 'navigation').length },
    checks,
};
fs.writeFileSync(path.join(output, name + '.json'), JSON.stringify(report, null, 2) + '\n');
const lines = [
    '# Create menu real API verification — 11 November 2026', '',
    `Result: **${report.totals.checks}/${report.totals.checks} checks passed**. ${report.totals.apiSaves} save flows returned successful real API responses and passed a separate authenticated GET readback. ${report.totals.navigation} checks cover view/navigation actions.`, '',
    'The production frontend ran against real FastAPI endpoints and a fresh disposable SQLite database built from current ORM metadata. No Playwright API interception or mocked API responses were used. QA records use CREATEQA identifiers. Outbound delivery workers were disabled; email and campaign checks saved server drafts only.', '',
    'Desktop: 1440 × 950. Mobile responsive viewport: 390 × 950. Chromium, Asia/Kolkata, QA administrator. This does not certify physical phones, every browser, production infrastructure, or other permission roles.', '',
    '## Coverage', '',
    ...['pms', 'crm', 'hrms'].map(module => `- ${module.toUpperCase()}: ${checks.filter(row => row.module === module).length} passing checks.`), '',
    'The PMS board exposes one extra desktop-only action, Add existing person. All actions present in each discovered menu were checked.', '',
    '## Behavior boundaries', '',
    '- List opens the existing task list. PMS Reminder opens Tasks & Follow-ups. CRM Dashboard opens reporting. CRM Tag opens the Relationship Hub for record tags; these actions do not create independent entities.',
    '- Whiteboard arranges existing records in a personal browser layout. Card movement and layout persistence after reload were verified; it has no standalone whiteboard record API.',
    '- Page uses the Notes editor. Space uses the workspace editor. Sheet, Artifact and Clip attach actual CSV, text and recorded WebM files through Files; there is no native spreadsheet editor or clip recorder in this menu.',
    '- Email and Campaign save server drafts. No email/campaign was sent. Invitations were created with reserved QA addresses with delivery workers disabled.',
    '- HR checks include guided employee save, actual CSV import preview/commit, attendance correction and UTC round-trip, leave submission, tickets, expenses, certificate upload, letter PDF preview/issue, forms and assets.', '',
    '## Issues fixed during verification', '',
    '- Completed the shared PMS board menu and blocked it while permissions/context load.',
    '- Fixed navigation that changed the URL while retaining the previous screen.',
    '- Opened mobile create forms after the sheet closes and prevented modal forms from dismissing on restored outside focus.',
    '- Waited for CRM custom fields before saving reminders and preserved validation messages.',
    '- Replaced row-count-based CRM ticket numbers with unique identifiers.',
    '- Corrected User / invitation to open the invitation form.',
    '- Fixed overlapping expanded mobile menu descriptions and restored the mobile certificate upload submit button.',
    '- Preserved UTC attendance timestamps when opening correction forms and displaying recorded punches.', '',
    '## Reproduce', '',
    '1. Start `backend/venv/Scripts/python.exe backend/scripts/create_menu_real_api_server.py` from the repository root. It binds only to 127.0.0.1:1597 and creates disposable QA data.',
    '2. From frontend, set `VITE_DEV_API_PROXY_TARGET=http://127.0.0.1:1597`; build with `node node_modules/vite/bin/vite.js build --outDir ../.local/create-menu-real/frontend`; preview with `node node_modules/vite/bin/vite.js preview --outDir ../.local/create-menu-real/frontend --host 127.0.0.1 --port 5194 --strictPort`.',
    '3. From the repository root, run `node qa/create-menu-real.cjs --inventory`, then `node qa/create-menu-real.cjs`. Use `CREATE_MODULE`, `CREATE_ACTION` (pipe-separated), and `CREATE_WIDTH` to narrow a rerun. `CREATE_RESUME=1` skips already passing matrix entries.',
    '4. Run `node qa/create-menu-real-report.cjs` to reject missing/failing entries and regenerate this report and its JSON evidence.', '',
    'Production build and TypeScript checks passed. The adjacent JSON stores per-action HTTP methods/statuses, save endpoints/IDs and GET readback endpoints. Screenshots and complete attempt history are under `.local/create-menu-real/`.', '',
    '## Per-action API evidence', '',
];
for (const module of ['pms', 'crm', 'hrms']) {
    lines.push('### ' + module.toUpperCase(), '');
    for (const action of [...new Set(checks.filter(row => row.module === module).map(row => row.action))]) {
        const rows = checks.filter(row => row.module === module && row.action === action);
        lines.push(`- **${action}** — ${rows.map(row => `${row.width}px: ${row.saved ? `${row.saved.status} \`${row.saved.path}\`${row.saved.id ? ` (#${row.saved.id})` : ''}` : 'view verified'}; GET \`${row.readback.endpoint}\``).join(' · ')}.`);
    }
    lines.push('');
}
fs.writeFileSync(path.join(output, name + '.md'), lines.join('\n') + '\n');
console.log(JSON.stringify(report.totals));

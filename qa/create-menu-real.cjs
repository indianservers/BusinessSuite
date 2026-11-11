/* Real browser, real HTTP, fresh isolated backend. No API interception. */
const { chromium, expect } = require('../frontend/node_modules/playwright/test');
const fs = require('node:fs'), path = require('node:path');
const origin = process.env.CREATE_REAL_ORIGIN || 'http://127.0.0.1:5194';
if (new URL(origin).hostname !== '127.0.0.1')
    throw Error('Use the isolated loopback fixture');
const out = path.resolve('.local/create-menu-real');
fs.mkdirSync(out, { recursive: true });
const tag = 'CREATEQA-' + Date.now();
const resultFile = path.join(out, 'results.json');
const results = fs.existsSync(resultFile) ? JSON.parse(fs.readFileSync(resultFile, 'utf8')) : [];
const esc = value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
let browser, context, page, auth, headers, fixtures, failed = 0;
async function api(endpoint, method = 'GET', data) { const response = await fetch(origin + '/api/v1' + endpoint, { method, headers: { ...headers, ...(data ? { 'Content-Type': 'application/json' } : {}) }, body: data ? JSON.stringify(data) : undefined }); const text = await response.text(); let body; try {
    body = JSON.parse(text);
}
catch {
    body = text.slice(0, 500);
} if (!response.ok)
    throw Error(`${method} ${endpoint} ${response.status}: ${JSON.stringify(body).slice(0, 900)}`); return body; }
async function setup() {
    const session = await api('/auth/login', 'POST', { email: 'admin@suiteqa.example.com', password: 'SuiteQA@12345' });
    auth = session;
    headers = { Authorization: 'Bearer ' + session.access_token, 'X-Suite-Branch': '1', 'X-Suite-Organization': '1' };
    auth.access = await api('/access/me');
    auth.me = await api('/auth/me');
    await ensureReferenceData();
    const saved = path.join(out, 'fixtures.json');
    if (fs.existsSync(saved)) {
        fixtures = JSON.parse(fs.readFileSync(saved, 'utf8'));
        try {
            await api('/project-management/projects/' + fixtures.project.id);
            return;
        }
        catch { }
    }
    const workspace = await api('/project-management/workspaces', 'POST', { name: tag + ' workspace' });
    const project = await api('/project-management/projects', 'POST', { name: tag + ' project', project_key: 'CQ' + Date.now(), workspace_id: workspace.id });
    const parent = await api(`/project-management/projects/${project.id}/tasks`, 'POST', { title: tag + ' parent', task_key: 'CQP' + Date.now(), status: 'To Do' });
    fixtures = { workspace, project, parent };
    fs.writeFileSync(saved, JSON.stringify(fixtures, null, 2));
}
async function ensureReferenceData() {
    const list = data => Array.isArray(data) ? data : data.items || [];
    let department = list(await api('/company/departments/')).find(item => item.name === 'Create QA API department');
    if (!department)
        department = await api('/company/departments/', 'POST', { name: 'Create QA API department', branch_id: 1 });
    if (!list(await api('/company/designations/')).some(item => item.department_id === department.id))
        await api('/company/designations/', 'POST', { name: 'Create QA API specialist', department_id: department.id, level: 1 });
    let leave = list(await api('/leave/types')).find(item => item.name === 'Create QA API annual leave');
    if (!leave) {
        leave = await api('/leave/types', 'POST', { name: 'Create QA API annual leave', code: 'CQAPI', days_allowed: 30 });
        await api(`/leave/balance/allocate?employee_id=${auth.employee_id}&leave_type_id=${leave.id}&year=2026&days=30`, 'POST', {});
    }
    let pipeline = list(await api('/crm/pipelines')).find(item => item.name === 'Create QA API pipeline');
    if (!pipeline)
        pipeline = await api('/crm/pipelines', 'POST', { name: 'Create QA API pipeline', is_default: true });
    if (!list(await api('/crm/pipeline-stages')).some(stage => stage.pipeline_id === pipeline.id))
        await api(`/crm/pipelines/${pipeline.id}/stages`, 'POST', { name: 'Create QA qualification', probability: 25, position: 1 });
    const emp = await api('/employees/' + auth.employee_id);
    if (!emp.branch_id)
        await api('/employees/' + auth.employee_id, 'PUT', { branch_id: 1, department_id: department.id });
    await api('/attendance/bulk-entry', 'POST', { entries: [{ employee_id: auth.employee_id, date: '2026-11-10', status: 'Half-day', hours_worked: 2, remarks: 'Create QA correction fixture' }] });
    const templates = await api('/communication/email-templates');
    if (!templates.items.some(t => t.name === 'Create QA email template'))
        await api('/communication/email-templates', 'POST', { name: 'Create QA email template', subject: 'QA draft', body_text: 'QA draft body', active: true });
    const heads = await api('/documents/studio/letterheads');
    let head = heads.find(h => h.name === 'Create QA letterhead');
    if (!head)
        head = await api('/documents/studio/letterheads', 'POST', { name: 'Create QA letterhead', signatory_name: 'QA Administrator', show_company_header: false });
    if (!(await api('/documents/studio/templates')).some(t => t.name === 'Create QA verification letter'))
        await api('/documents/studio/templates', 'POST', { name: 'Create QA verification letter', document_type: 'QA verification', title: 'QA verification letter', body: 'Verification record for {{recipient.name}}.', recipient_scope: 'employee', letterhead_id: head.id });
}
async function visit(module, width) {
    context = await browser.newContext({ viewport: { width, height: 950 }, timezoneId: 'Asia/Kolkata', serviceWorkers: 'block' });
    await context.addInitScript(a => { sessionStorage.setItem('suite-organization', '1'); sessionStorage.setItem('suite-branch', '1'); sessionStorage.setItem('hrms-auth', JSON.stringify({ state: { accessToken: a.access_token, refreshToken: a.refresh_token, user: { ...a.me, id: a.user_id, role: a.role, is_superuser: a.is_superuser, employee_id: a.employee_id, access: a.access }, isAuthenticated: true }, version: 0 })); }, auth);
    page = await context.newPage();
    page.setDefaultTimeout(45000);
    page.setDefaultNavigationTimeout(90000);
    const route = module === 'pms' ? `/pms/workspaces?workspace=${fixtures.workspace.id}` : module === 'crm' ? '/crm/leads' : '/hrms/employees';
    await page.goto(origin + route, { waitUntil: 'domcontentloaded' });
    await page.locator('.suite-new-trigger:visible,.mobile-module-add:visible').first().waitFor({ timeout: 90000 });
}
async function openMenu() {
    await page.locator('.suite-new-trigger:visible,.mobile-module-add:visible').first().click();
    await page.locator('.suite-new-menu:visible,.mobile-create-list:visible').first().waitFor();
    const all = page.getByRole('button', { name: /^View all \d+ actions$/ });
    if (await all.count())
        await all.click();
}
async function select(label) { await openMenu(); const item = page.getByRole('menuitem').filter({ has: page.locator('.suite-new-item-copy').filter({ hasText: new RegExp('^' + esc(label) + '(?=[A-Z]|$)') }) }); if (await item.count())
    await item.click();
else
    await page.locator('.mobile-create-list button').filter({ has: page.locator('strong', { hasText: new RegExp('^' + esc(label) + '$') }) }).click(); }
async function fields() { return page.locator('input,select,textarea,[contenteditable=true]').evaluateAll(nodes => nodes.filter(n => n.getClientRects().length).map(n => ({ tag: n.tagName, type: n.type, name: n.name, label: n.getAttribute('aria-label') || n.labels?.[0]?.textContent?.trim(), placeholder: n.placeholder, value: n.value, options: n.tagName === 'SELECT' ? Array.from(n.options).map(o => ({ value: o.value, text: o.text })) : undefined }))); }
async function diagnostic(row) { row.url = page.url(); row.headings = await page.locator('h1,h2,h3').allTextContents(); row.fields = await fields(); row.buttons = await page.locator('button').evaluateAll(nodes => nodes.filter(n => n.getClientRects().length).map(n => ({ text: n.textContent.trim(), label: n.getAttribute('aria-label'), disabled: n.disabled }))); row.alerts = await page.locator('[role=alert],.md-error,.lm-error').allTextContents(); row.resources = await page.evaluate(() => performance.getEntriesByType('resource').filter(item => item.name.includes('/assets/')).slice(-18).map(item => ({ name: item.name.split('/').pop(), duration: Math.round(item.duration) }))); }
async function record(module, action, width, run) {
    const row = { module, action, width, tag, origin, status: 'running', writes: [], errors: [] };
    try {
        await visit(module, width);
        page.on('pageerror', error => row.errors.push(error.message));
        page.on('response', async (response) => { const request = response.request(), p = new URL(response.url()).pathname; if (p.startsWith('/api/v1/') && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method()))
            row.writes.push({ path: p, method: request.method(), status: response.status() }); });
        await select(action);
        await run(row);
        if (row.errors.length)
            throw Error('Runtime errors: ' + row.errors.join('; '));
        if (row.status === 'running')
            row.status = 'passed';
    }
    catch (error) {
        failed++;
        row.status = 'failed';
        row.error = error.message;
        await diagnostic(row).catch(() => { });
        await page?.screenshot({ path: path.join(out, `${module}-${action.replace(/[^a-z0-9]/gi, '-')}-${width}.png`) }).catch(() => { });
    }
    finally {
        const latest = fs.existsSync(resultFile) ? JSON.parse(fs.readFileSync(resultFile, 'utf8')) : [];
        latest.push(row);
        fs.writeFileSync(resultFile, JSON.stringify(latest, null, 2));
        console.log(JSON.stringify({ module, action, width, status: row.status, error: row.error?.split('\n')[0] }));
        await context?.close();
    }
}
async function inventory() {
    const inventory = [];
    for (const module of ['pms', 'crm', 'hrms'])
        for (const width of [1440, 390]) {
            await visit(module, width);
            await openMenu();
            let labels = await page.locator('.suite-new-menu .suite-new-item-copy').evaluateAll(nodes => nodes.map(n => n.childNodes[0].textContent));
            if (!labels.length)
                labels = await page.locator('.mobile-create-list strong').allTextContents();
            const layout = await page.locator('.mobile-create-list>button').evaluateAll(nodes => nodes.slice(0, 4).map(n => ({ height: n.getBoundingClientRect().height, minHeight: getComputedStyle(n).minHeight, lineHeight: getComputedStyle(n).lineHeight, display: getComputedStyle(n).display, span: n.children[1]?.getBoundingClientRect().height })));
            if (layout.some(item => item.height < item.span + 16))
                throw Error(module + ' mobile menu descriptions overlap');
            inventory.push({ module, width, labels, layout });
            await page.screenshot({ path: path.join(out, `menu-${module}-${width}.png`) });
            console.log(JSON.stringify(inventory.at(-1)));
            await context.close();
        }
    fs.writeFileSync(path.join(out, 'inventory.json'), JSON.stringify(inventory, null, 2));
}
async function inspect() { const module = process.env.CREATE_MODULE || 'pms', action = process.env.CREATE_ACTION || 'Quick task', width = Number(process.env.CREATE_WIDTH || 1440); await record(module, action, width, async (row) => { await page.waitForTimeout(5000); await diagnostic(row); row.reactLocations = await page.evaluate(() => { const root = document.querySelector('#root'); const key = Object.keys(root).find(k => k.startsWith('__reactContainer')); const found = []; function walk(f) { if (!f)
    return; const v = f.memoizedProps?.value; if (v?.location)
    found.push({ path: v.location.pathname, search: v.location.search }); walk(f.child); walk(f.sibling); } walk(root[key]?.stateNode?.current); return found; }); row.status = 'inspected'; }); }
async function main() { await setup(); browser = await chromium.launch(); try {
    if (process.argv.includes('--inventory'))
        await inventory();
    else if (process.argv.includes('--inspect-all')) {
        for (const module of (process.env.CREATE_MODULE || 'crm').split(','))
            for (const action of (process.env.CREATE_ACTION || 'Deal').split('|'))
                await record(module, action, Number(process.env.CREATE_WIDTH || 1440), async (row) => { await page.waitForTimeout(1500); await diagnostic(row); row.status = 'inspected'; });
    }
    else if (process.argv.includes('--inspect'))
        await inspect();
    else
        await runCases();
}
catch (error) {
    if (page) {
        await page.screenshot({ path: path.join(out, 'last-failure.png') }).catch(() => { });
        fs.writeFileSync(path.join(out, 'last-failure.txt'), (await page.locator('body').innerText()).slice(0, 16000));
    }
    throw error;
}
finally {
    await browser?.close();
    if (failed)
        process.exitCode = 1;
} }
function dialog() { return page.locator('[role="dialog"]:visible').last(); }
function certificatePdf(text) {
    const escaped = text.replace(/[()\\]/g, '\\$&');
    const stream = `BT /F1 12 Tf 40 740 Td (${escaped}) Tj ET`;
    const objects = [
        '<< /Type /Catalog /Pages 2 0 R >>',
        '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
        `<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}\nendstream`,
        '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ];
    let pdf = '%PDF-1.4\n';
    const offsets = [0];
    objects.forEach((object, index) => {
        offsets.push(Buffer.byteLength(pdf));
        pdf += `${index + 1} 0 obj\n${object}\nendobj\n`;
    });
    const xref = Buffer.byteLength(pdf);
    pdf += `xref\n0 6\n0000000000 65535 f \n${offsets.slice(1).map(offset => String(offset).padStart(10, '0') + ' 00000 n ').join('\n')}\ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
    return Buffer.from(pdf);
}
async function reveal(field, scope = dialog()) {
    await field.waitFor({ state: 'attached', timeout: 90000 });
    if (await field.isVisible())
        return;
    for (const tab of await scope.locator('.suite-form-tabs button').all()) {
        await tab.click();
        if (await field.isVisible())
            return;
    }
    await expect(field).toBeVisible();
}
async function fill(label, value, scope = dialog()) { const input = scope.getByLabel(label, { exact: true }); await reveal(input, scope); await input.fill(value); }
async function click(name, scope = page) { const buttons = scope.getByRole('button', { name, exact: typeof name === 'string' }); for (let i = 0; i < await buttons.count(); i++)
    if (await buttons.nth(i).isVisible()) {
        await buttons.nth(i).click();
        return;
    } await buttons.first().click(); }
async function save(row, matcher, clicker) {
    const waiting = page.waitForResponse(response => ['POST', 'PUT', 'PATCH'].includes(response.request().method()) && matcher(new URL(response.url()).pathname), { timeout: 30000 });
    waiting.catch(() => { });
    await clicker();
    const response = await waiting;
    const body = await response.json();
    if (!response.ok())
        throw Error(`Save ${response.status()} ${new URL(response.url()).pathname}: ${JSON.stringify(body).slice(0, 1000)}`);
    row.saved = { path: new URL(response.url()).pathname, status: response.status(), id: body.id || body.task?.id };
    return body;
}
async function read(row, endpoint, needle) { const stored = await api(endpoint); if (needle && !JSON.stringify(stored).includes(needle))
    throw Error('Persisted readback did not contain ' + needle); row.readback = { endpoint, matched: true }; return stored; }
const cases = [];
function test(module, action, handler) { cases.push({ module, action, handler }); }
for (const action of ['Task', 'Story', 'Bug'])
    test('pms', action, async (row) => {
        const name = tag + ' ' + action;
        await fill('Task Title', name);
        const project = dialog().getByLabel('Project', { exact: true });
        await reveal(project);
        await project.selectOption(String(fixtures.project.id));
        const data = await save(row, p => /\/task-studio\/projects\/\d+\/tasks$/.test(p), () => click('Create Task', dialog().locator('[data-smart-create-footer]')));
        const task = data.task || data;
        const stored = await read(row, '/project-management/tasks/' + task.id, name);
        if (stored.work_type !== action)
            throw Error('Work type was not retained');
    });
for (const action of ['Quick task', 'Subtask'])
    for (const module of action === 'Subtask' ? ['pms', 'crm'] : ['pms'])
        test(module, action, async (row) => {
            const name = tag + ' ' + module + ' ' + action;
            const d = dialog();
            await d.getByLabel('Quick task project', { exact: true }).selectOption(String(fixtures.project.id));
            if (action === 'Subtask')
                await d.getByLabel('Parent task', { exact: true }).selectOption(String(fixtures.parent.id));
            await fill('Title', name, d);
            const data = await save(row, p => p === `/api/v1/project-management/projects/${fixtures.project.id}/tasks`, () => click(action === 'Subtask' ? 'Create subtask' : 'Create task', d));
            const stored = await read(row, '/project-management/tasks/' + data.id, name);
            if (action === 'Subtask' && stored.parent_task_id !== fixtures.parent.id)
                throw Error('Parent task not saved');
        });
test('pms', 'Project', async (row) => { const name = tag + ' project'; await fill('Project name', name); const workspace = dialog().getByLabel('Project workspace', { exact: true }); await reveal(workspace); await workspace.selectOption(String(fixtures.workspace.id)); const data = await save(row, p => p === '/api/v1/project-management/projects', () => click('Create project', dialog().locator('[data-smart-create-footer]'))); await read(row, '/project-management/projects/' + data.id, name); });
for (const module of ['pms', 'crm'])
    for (const action of module === 'pms' ? ['Private note', 'Page'] : ['Note', 'Page'])
        test(module, action, async (row) => {
            const name = tag + ' ' + module + ' ' + action;
            const title = page.getByLabel('Note title', { exact: true });
            await title.waitFor();
            await title.fill(name);
            const editor = page.locator('[contenteditable=true]:visible').last();
            await editor.fill('Real API Create menu acceptance.');
            const data = await save(row, p => /\/project-management\/notes(?:\/\d+)?$/.test(p), () => page.keyboard.press('Control+s'));
            await read(row, '/project-management/notes/' + data.id, name);
        });
for (const module of ['pms', 'crm'])
    test(module, 'Document', async (row) => { const name = tag + ' ' + module + ' document'; await click('New document'); await fill('Document title', name, page); await page.getByLabel('Document project', { exact: true }).selectOption(String(fixtures.project.id)); await page.locator('[contenteditable=true]:visible').last().fill('Create menu real API document.'); const data = await save(row, p => /\/projects\/\d+\/docs$/.test(p), () => click('Save document')); await read(row, '/project-management/docs/' + data.id, name); });
test('crm', 'Add Lead', async (row) => { const name = tag + ' lead'; await fill('Lead Name *', name); await fill('Email', 'createqa-' + Date.now() + '@example.com'); const data = await save(row, p => p === '/api/v1/crm/lead-management/leads', () => click('Create lead', dialog())); await read(row, '/crm/lead-management/leads/' + data.id, name); });
for (const action of ['Company', 'Add Customer'])
    test('crm', action, async (row) => { const name = tag + ' ' + action; await fill(action === 'Company' ? 'Company name *' : 'Full name *', name); const data = await save(row, p => p === '/api/v1/master-data/companies', () => click('Save ' + (action === 'Company' ? 'company' : 'customer'), dialog())); await read(row, '/master-data/companies/' + data.id + '?source=crm', name); });
test('crm', 'Contact', async (row) => { const name = tag + ' contact'; const input = dialog().getByPlaceholder('Enter contact name', { exact: true }); await reveal(input); await input.fill(name); const data = await save(row, p => p === '/api/v1/crm/contacts', () => click('Create contact', dialog())); await read(row, '/crm/contacts/' + data.id, name); });
test('crm', 'Reminder', async (row) => { const name = tag + ' reminder'; await fill('Title', name); await click('Tomorrow, 9 AM', dialog()); const data = await save(row, p => p === '/api/v1/crm/tasks', () => click('Create reminder', dialog())); await read(row, '/crm/tasks/' + data.id, name); });
for (const action of ['Product', 'Service'])
    test('crm', action, async (row) => { const name = tag + ' ' + action; await fill('Name', name); await fill('SKU / Code', 'C' + Date.now()); const data = await save(row, p => p === '/api/v1/catalog/items', () => click('Save item', dialog())); await read(row, '/catalog/items/' + action.toLowerCase() + '/' + data.id, name); });
test('crm', 'Task', async (row) => { const name = tag + ' CRM linked task'; await fill('Task Title', name); const project = dialog().getByLabel('Project', { exact: true }); await reveal(project); await project.selectOption(String(fixtures.project.id)); const data = await save(row, p => /\/task-studio\/projects\/\d+\/tasks$/.test(p), () => click('Create Task', dialog().locator('[data-smart-create-footer]'))); await read(row, '/project-management/tasks/' + (data.task || data).id, name); });
for (const module of ['pms', 'crm', 'hrms'])
    test(module, 'Form', async (row) => { const name = tag + ' ' + module + ' form'; await fill('Form name', name); const data = await save(row, p => p === '/api/v1/forms', () => click('Save draft', dialog().locator('.forms-actions'))); await read(row, '/forms/' + data.id, name); });
test('hrms', 'Add employee', async (row) => { const name = 'CreateQA' + Date.now(); await fill('First Name *', name); const body = dialog().locator('.smart-create-body'); await click('Next', body); await body.locator('input[name=date_of_joining]').fill('2026-11-11'); for (let i = 0; i < 3; i++)
    await click('Next', body); const data = await save(row, p => p.replace(/\/$/, '') === '/api/v1/employees', () => click('Create Employee', body)); await read(row, '/employees/' + data.id, name); });
test('hrms', 'Submit expense', async (row) => { const name = tag + ' expense'; await fill('Claim amount', '12.50'); await fill('Business purpose', name); const data = await save(row, p => p === '/api/v1/expenses/claims', () => click('Submit expense claim', dialog().locator('[data-smart-create-footer]'))); await read(row, '/expenses/claims', name); });
test('hrms', 'Apply for leave', async (row) => { const name = tag + ' leave'; const d = dialog(); await d.locator('select[name=leave_type_id]').selectOption({ label: 'Create QA API annual leave' }); const offset = row.width === 1440 ? 10 : 11; const date = new Date(); date.setDate(date.getDate() + offset); const day = date.toISOString().slice(0, 10); await d.locator('input[name=from_date]').fill(day); await d.locator('input[name=to_date]').fill(day); await fill('Reason', name); const data = await save(row, p => p === '/api/v1/leave/apply', () => click('Submit Application', d)); await read(row, '/leave/my-requests', name); });
for (const module of ['pms', 'crm'])
    test(module, 'Folder', async (row) => {
        const name = tag + ' ' + module + ' folder';
        if (module === 'pms') {
            await page.getByLabel('File project', { exact: true }).selectOption(String(fixtures.project.id));
            await click('Create folder');
            await fill('Folder name', name);
            const data = await save(row, p => p === '/api/v1/project-management/file-folders', () => click('Create folder', dialog()));
            await read(row, '/project-management/file-folders?project_id=' + fixtures.project.id, name);
        }
        else {
            await click('Create folder');
            await fill('CRM folder name', name);
            await save(row, p => p === '/api/v1/crm/file-workspace/folders', () => click('Create folder', dialog()));
            await read(row, '/crm/file-workspace', name);
        }
    });
for (const module of ['pms', 'crm'])
    for (const action of ['Sheet', 'Artifact', 'Clip'])
        test(module, action, async (row) => {
            await click('Open Files', dialog());
            if (module === 'pms')
                await page.getByLabel('File project', { exact: true }).selectOption(String(fixtures.project.id));
            const file = { name: tag + '-' + module + '-' + action + (action === 'Sheet' ? '.csv' : action === 'Clip' ? '.webm' : '.txt'), mimeType: action === 'Sheet' ? 'text/csv' : action === 'Clip' ? 'video/webm' : 'text/plain', buffer: Buffer.from(action === 'Sheet' ? 'name,value\nQA,1\n' : 'Real API attachment verification') };
            if (action === 'Clip') {
                file.buffer = Buffer.from(await page.evaluate(async () => { const canvas = document.createElement('canvas'); canvas.width = 64; canvas.height = 64; canvas.getContext('2d').fillRect(0, 0, 64, 64); const stream = canvas.captureStream(5), recorder = new MediaRecorder(stream, { mimeType: 'video/webm' }), chunks = []; return await new Promise(resolve => { recorder.ondataavailable = e => chunks.push(e.data); recorder.onstop = async () => { resolve(Array.from(new Uint8Array(await new Blob(chunks).arrayBuffer()))); stream.getTracks().forEach(t => t.stop()); }; recorder.start(); setTimeout(() => recorder.stop(), 300); }); }));
            }
            await save(row, p => p.endsWith(module === 'pms' ? `/projects/${fixtures.project.id}/files/upload` : '/crm/file-workspace/upload'), async () => { const input = page.locator('input[type=file]').first(); await expect(input).toBeEnabled({ timeout: 30000 }); await input.setInputFiles(file); });
            await read(row, module === 'pms' ? '/project-management/files?project_id=' + fixtures.project.id : '/crm/file-workspace', file.name);
        });
test('pms', 'Tag', async (row) => { const name = tag + ' tag'; await click('Create tag'); await fill('Name', name); await save(row, p => p === '/api/v1/project-management/tags', () => click('Save tag', dialog())); await read(row, '/project-management/tag-manager', name); });
for (const module of ['pms', 'crm'])
    test(module, 'Custom Field', async (row) => { const name = tag + ' ' + module + ' field'; await click(module === 'pms' ? /^(New custom field|Create custom field)$/ : 'Add field'); await fill(module === 'pms' ? 'Field name' : 'Field name *', name); await save(row, p => p === `/api/v1/${module === 'pms' ? 'project-management' : 'crm'}/custom-fields`, () => click(module === 'pms' ? 'Create field' : 'Save field', dialog())); await read(row, module === 'pms' ? '/project-management/custom-fields?include_archived=true' : '/crm/custom-fields?entityType=leads&per_page=100', name); });
for (const module of ['pms', 'crm'])
    test(module, 'Time Tracked', async (row) => { const name = tag + ' ' + module + ' time'; const scope = page.locator('form').filter({ has: page.getByLabel('Duration (minutes or 3h 20m)', { exact: true }) }).last(); await scope.getByLabel('Project', { exact: true }).selectOption(String(fixtures.project.id)); await fill('Duration (minutes or 3h 20m)', '15', scope); await fill('Description', name, scope); await save(row, p => p === '/api/v1/project-management/time-logs', () => click('Log time', scope)); await read(row, '/project-management/time-logs?project_id=' + fixtures.project.id, name); });
test('pms', 'Dashboard', async (row) => { const name = tag + ' dashboard'; await click('New dashboard'); await fill('Dashboard name *', name); for (let i = 0; i < 3; i++)
    await click('Continue', dialog()); const data = await save(row, p => p === '/api/v1/project-management/dashboards', () => click('Create dashboard', dialog())); await read(row, '/project-management/dashboards/' + data.id, name); });
for (const action of ['Workspace', 'Space'])
    test('pms', action, async (row) => { const name = tag + ' ' + action; await fill('Workspace name', name); const data = await save(row, p => p === '/api/v1/project-management/workspace-directory', () => click('Create Workspace', dialog().locator('form'))); await read(row, '/project-management/workspace-directory/' + data.id, name); });
test('crm', 'Space', async (row) => { const name = tag + ' CRM space'; await click('Create Workspace'); await fill('Workspace name', name); const data = await save(row, p => p === '/api/v1/crm/workspace-directory', () => click('Create Workspace', dialog().locator('form'))); await read(row, '/crm/workspace-directory/' + data.id, name); });
test('hrms', 'Asset', async (row) => { const name = tag + ' asset'; await fill('Asset name', name); await fill('Unique company asset tag', 'CQ' + Date.now()); await click('Review asset', dialog()); await save(row, p => p.replace(/\/$/, '') === '/api/v1/assets', () => click('Save asset', dialog())); await read(row, '/assets/?search=' + encodeURIComponent(name), name); });
test('hrms', 'Support ticket', async (row) => { const name = tag + ' HR ticket'; await fill('Ticket subject', name); await dialog().locator('[contenteditable=true]').fill('Real API support verification.'); const data = await save(row, p => p === '/api/v1/helpdesk/tickets', () => click('Raise Ticket', dialog())); await read(row, '/helpdesk/tickets', name); });
test('hrms', 'Note', async (row) => { const name = tag + ' HR note'; await page.getByLabel('Note title', { exact: true }).fill(name); await page.locator('[contenteditable=true]:visible').last().fill('HR Create real API acceptance.'); const data = await save(row, p => /\/project-management\/notes(?:\/\d+)?$/.test(p), () => page.keyboard.press('Control+s')); await read(row, '/project-management/notes/' + data.id, name); });
for (const module of ['pms', 'crm'])
    test(module, 'Conversation', async (row) => { const name = tag + ' ' + module + ' channel'; await click('+ New conversation'); await dialog().getByLabel(/^Type/).selectOption('channel'); await fill('Name', name); const data = await save(row, p => /\/chat\/conversations$/.test(p), () => click('Create conversation', dialog())); await read(row, row.saved.path.replace('/api/v1', ''), name); row.note = 'Private conversation created; no message sent.'; });
test('crm', 'Deal', async (row) => { const name = tag + ' deal'; await dialog().getByPlaceholder('Enter deal name...', { exact: true }).fill(name); await dialog().getByLabel('Pipeline', { exact: true }).selectOption({ label: 'Create QA API pipeline' }); await dialog().getByLabel(/^Stage/).selectOption({ label: 'Create QA qualification' }); const data = await save(row, p => p === '/api/v1/crm/deals', () => click('Create Deal', dialog())); await read(row, '/crm/deals/' + data.id, name); });
test('crm', 'Activity', async (row) => { const name = tag + ' activity'; await dialog().getByPlaceholder('Follow-up call', { exact: true }).fill(name); await save(row, p => p === '/api/v1/crm/activities', () => click('Create', dialog())); await read(row, '/crm/activities?per_page=100', name); });
test('crm', 'Support ticket', async (row) => { const name = tag + ' CRM ticket'; await dialog().getByPlaceholder('Customer issue', { exact: true }).fill(name); await save(row, p => p === '/api/v1/crm/tickets', () => click('Create', dialog())); await read(row, '/crm/tickets?per_page=100', name); });
test('crm', 'Campaign', async (row) => { const name = tag + ' campaign'; const templates = await api('/communication/email-templates'); let template = templates.items.find(t => t.name === 'Create QA email template'); if (!template)
    template = await api('/communication/email-templates', 'POST', { name: 'Create QA email template', subject: 'QA draft', body_text: 'QA campaign draft', body_html: '<p>QA campaign draft</p>', active: true }); await fill('Campaign name', name); await dialog().locator('select').first().selectOption(String(template.id)); await click('Review & save draft', dialog()); const data = await save(row, p => p === '/api/v1/communication/campaigns', () => click('Create reviewed draft', dialog())); await read(row, '/communication/campaigns', name); row.note = 'Draft only; campaign not launched.'; });
test('hrms', 'Upload document', async (row) => { const name = tag + ' HR certificate'; const employee = page.getByLabel('Document employee', { exact: true }); if (await employee.count())
    await employee.selectOption(String(auth.employee_id)); await page.getByLabel('Certificate type', { exact: true }).fill('QA certificate'); await page.getByLabel('Document title', { exact: true }).fill(name); await expect(page.getByLabel('Certificate file', { exact: true })).toBeEnabled(); await page.getByLabel('Certificate file', { exact: true }).setInputFiles({ name: tag + '.pdf', mimeType: 'application/pdf', buffer: certificatePdf(tag + '-' + row.width) }); const upload = page.locator('button').filter({ hasText: /^Upload document$/ }); await reveal(upload, page); await save(row, p => p === '/api/v1/documents/certificates', () => upload.click()); await read(row, '/documents/certificates?employee_id=' + auth.employee_id, name); });
test('crm', 'Email', async (row) => { const name = tag + ' email'; await fill('Find email recipient', 'CREATEQA'); await dialog().locator('.cc-picker-results button').first().click(); await fill('Recipient email', 'create-qa@example.com'); await fill('Subject', name); await dialog().getByLabel(/^Message/).fill('QA draft only; no email is sent.'); const data = await save(row, p => p === '/api/v1/communication/emails/draft', () => click('Save server draft', dialog())); await read(row, '/communication/timeline/' + data.related_record_type + '/' + data.related_record_id, name); row.note = 'Server draft only; no email sent.'; });
test('hrms', 'Bulk add employees', async (row) => { const name = 'CreateImport' + Date.now(); await page.getByLabel('Import spreadsheet', { exact: true }).setInputFiles({ name: tag + '.csv', mimeType: 'text/csv', buffer: Buffer.from('employee_id,first_name,last_name,date_of_joining\nCQI' + Date.now() + ',' + name + ',QA,2026-11-11\n') }); await click('Continue to mapping'); await click('Preview import'); await expect(page.getByRole('heading', { name: 'Import Preview Ready', exact: true })).toBeVisible(); await click('Dismiss'); await page.getByLabel('I reviewed the column mapping, cleaned values and duplicate decisions.', { exact: true }).check(); const data = await save(row, p => /\/imports\/hrms\/batches\/[^/]+\/commit$/.test(p), () => click(/^Import 1 new/)); await read(row, '/employees/?search=' + name, name); });
test('hrms', 'Generate letter', async (row) => { const name = tag + ' letter'; const template = (await api('/documents/studio/templates')).find(t => t.name === 'Create QA verification letter'); await dialog().getByLabel('Template', { exact: true }).selectOption(String(template.id)); await dialog().getByLabel('Recipient', { exact: true }).selectOption(String(auth.employee_id)); await fill('Internal remarks', name); const waiting = page.waitForResponse(r => r.request().method() === 'POST' && r.url().includes('/documents/studio/preview')); await click('Preview PDF', dialog()); const preview = await waiting; if (!preview.ok())
    throw Error('Letter preview ' + preview.status() + ': ' + await preview.text()); const data = await save(row, p => p === '/api/v1/documents/studio/issue', () => click('Issue & download', dialog())); await read(row, '/documents/studio/issued', data.reference); row.note = 'QA PDF issued in disposable database.'; });
test('pms', 'User / invitation', async (row) => { const email = 'create-qa-' + Date.now() + '@example.com'; await fill('Teammate email', email); await save(row, p => /\/workspaces\/\d+\/invitations$/.test(p), () => click('Create invitation', dialog())); await read(row, row.saved.path.replace('/api/v1', ''), email); });
test('pms', 'Add existing person', async (row) => { if (row.width === 390) {
    row.status = 'not-applicable';
    row.note = 'Desktop board-only action; mobile uses User / invitation.';
    return;
} const checkbox = dialog().getByRole('checkbox', { name: 'Select employee@suiteqa.example.com', exact: true }); await checkbox.check(); const email = (await checkbox.getAttribute('aria-label')).replace('Select ', ''); await save(row, p => p === '/api/v1/project-management/people-management/memberships/bulk', () => click('Add 1 person', dialog())); await read(row, `/project-management/workspaces/${fixtures.workspace.id}/members`, email); });
for (const module of ['pms', 'crm'])
    test(module, 'View List', async (row) => { const name = tag + ' ' + module + ' view ' + row.width; if (module === 'pms')
        await page.getByLabel('Saved views', { exact: true }).selectOption('save');
    else {
        await page.locator('summary').filter({ hasText: /^View options$/ }).click();
        await click('Save current view');
    } await fill('View name', name, module === 'crm' ? page : dialog()); if (module === 'pms') {
        await save(row, p => p === '/api/v1/project-management/saved-views', () => click('Save view', dialog()));
        await read(row, '/project-management/saved-views', name);
    }
    else {
        await click('Publish shared view');
        await save(row, p => p === '/api/v1/crm/productivity/shared-views', () => click('Publish shared view', dialog()));
        await read(row, '/crm/productivity/shared-views', name);
    } });
test('crm', 'Quote', async (row) => { const name = 'CQ' + Date.now(); await dialog().getByPlaceholder('QT-2026-001', { exact: true }).fill(name); const data = await save(row, p => /\/crm\/(quotes|quotations)$/.test(p), () => click(/^(Create|Save draft|Create quote)$/, dialog())); await read(row, row.saved.path.replace('/api/v1', '') + '/' + data.id, name); });
test('hrms', 'Correct attendance', async (row) => { const name = tag + ' correction ' + row.width; const endpoint = '/attendance/employee/' + auth.employee_id + '?from_date=2026-11-01&to_date=2026-11-30', before = await api(endpoint); await click('Correct attendance'); const d = dialog(), start = d.getByLabel('Corrected check-in', { exact: true }); const value = await start.inputValue(); await fill('Corrected check-out', new Date(Date.parse(value + 'Z') + 3600000).toISOString().slice(0, 16)); await fill('Attendance correction reason', name); await save(row, p => /\/attendance\/\d+\/correct$/.test(p), () => click('Save attendance correction', d)); const saved = await read(row, endpoint, name), id = Number(row.saved.path.split('/').at(-2)), stored = saved.find(a => a.id === id), original = before.find(a => a.id === id), utc = v => Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/i.test(v) ? v : v + 'Z'); if (utc(stored.check_in) !== utc(original.check_in))
    throw Error('Unchanged check-in drifted during correction'); if (Number(stored.total_hours) !== 1)
    throw Error('Correction elapsed hours mismatch'); row.utcRoundTrip = true; });
for (const [module, action, heading, endpoint] of [
    ['pms', 'List', /Task|Workspaces/, '/project-management/tasks'], ['crm', 'List', /Task|Workspaces/, '/project-management/tasks'],
    ['pms', 'Reminder', 'Tasks & Follow-ups', '/record-360/work/queue/items'],
    ['pms', 'Whiteboard', /Task|Workspaces/, '/project-management/tasks'], ['crm', 'Whiteboard', /Lead/, '/crm/lead-management/leads'],
    ['crm', 'Dashboard', /Dashboard|Sales workspace|Sales overview|CRM overview/i, '/crm/dashboard'], ['crm', 'Tag', 'Relationship Hub', '/crm/lead-management/leads']
])
    test(module, action, async (row) => { await expect(page.getByRole('heading', { name: heading }).first()).toBeVisible({ timeout: 90000 }); await read(row, endpoint); if (action === 'Whiteboard') {
        await expect(page.getByRole('region', { name: 'Personal record whiteboard', exact: true })).toBeVisible({ timeout: 30000 });
        const card = page.locator('.rl-whiteboard-card').first();
        await card.scrollIntoViewIfNeeded();
        const box = await card.boundingBox();
        await page.mouse.move(box.x + 6, box.y + 6);
        await page.mouse.down();
        await page.mouse.move(box.x + 46, box.y + 36, { steps: 5 });
        await page.mouse.up();
        const position = await card.getAttribute('style');
        await page.reload();
        await expect(page.locator('.rl-whiteboard-card').first()).toHaveAttribute('style', position);
        row.personalLayoutReload = true;
    } row.kind = 'navigation'; row.note = action === 'Whiteboard' ? 'Personal card view; no standalone whiteboard record API.' : action === 'Tag' ? 'Record tags are edited on existing CRM records; no standalone tag create form.' : 'Mapped existing workspace; no standalone record is created by this action.'; row.url = page.url(); await page.screenshot({ path: path.join(out, `${module}-${action.replace(/[^a-z0-9]/gi, '-')}-${row.width}-verified.png`) }); });
async function runCases() { const modules = process.env.CREATE_MODULE?.split(','), actions = process.env.CREATE_ACTION?.split('|'), widths = process.env.CREATE_WIDTH ? [Number(process.env.CREATE_WIDTH)] : [1440, 390]; for (const item of cases.filter(item => (!modules || modules.includes(item.module)) && (!actions || actions.includes(item.action))))
    for (const width of widths) {
        if (width === 390 && item.action === 'Add existing person')
            continue;
        if (process.env.CREATE_RESUME) {
            const previous = JSON.parse(fs.readFileSync(resultFile, 'utf8')).filter(r => r.module === item.module && r.action === item.action && r.width === width && r.status !== 'inspected').at(-1);
            if (previous?.status === 'passed')
                continue;
        }
        await record(item.module, item.action, width, item.handler);
    } }
main().catch(error => { console.error(error.message); process.exitCode = 1; });

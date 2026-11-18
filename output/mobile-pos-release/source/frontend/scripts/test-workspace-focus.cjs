const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
const source = fs.readFileSync(require('node:path').join(__dirname, '../src/apps/project-management/pages/workspaceFocus.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const exportsForTest = {};
new Function('exports', compiled)(exportsForTest);
const { matchesWorkFocus: matches, localWorkDate } = exportsForTest;
const task = { status: 'In Progress', due_date: '2026-11-06', assignee_user_id: 7 };
assert.equal(matches(task, 'overdue', '2026-11-07'), true);
assert.equal(matches(task, 'today', '2026-11-06'), true);
assert.equal(matches(task, 'overdue', '2026-11-06'), false);
for (const status of ['Done', 'Completed', 'Closed', 'Resolved', 'Cancelled', 'canceled']) {
  for (const focus of ['overdue', 'today', 'unassigned', 'unscheduled']) {
    assert.equal(matches({ ...task, status, assignee_user_id: null }, focus, '2026-11-07'), false);
  }
}
assert.equal(matches({ ...task, assignee_user_ids: [] }, 'unassigned'), true);
assert.equal(matches({ ...task, assignee_user_ids: [9] }, 'unassigned'), false);
assert.equal(matches({ ...task, due_date: undefined }, 'unscheduled'), true);
assert.equal(matches({ ...task, status: 'Blocked' }, 'blocked'), true);
assert.equal(matches({ ...task, status: 'To Do' }, 'blocked'), false);
assert.equal(localWorkDate(new Date(2026, 0, 2, 0, 5)), '2026-01-02');
console.log('Workspace focus: date boundaries, terminal statuses, assignments and queues passed.');

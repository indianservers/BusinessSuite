import { test, expect } from '../frontend/node_modules/playwright/test';
import { authenticateAi } from './ai-test-utils';

async function open(page: any) {
  await authenticateAi(page);
  await page.route('**/api/v1/**', async (route: any) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/project-management/projects') return route.fulfill({ json: [{ id: 1, name: 'Delivery', project_key: 'WEB', workspace_id: null }] });
    if (path === '/api/v1/project-management/projects/1/tasks') return route.fulfill({ json: [{ id: 7, task_key: 'WEB-1', title: 'Build', status: 'To Do' }] });
    if (path === '/api/v1/ai-operator/providers' || path === '/api/v1/ai-operator/runs') return route.fulfill({ json: { items: [] } });
    if (path === '/api/v1/ai-operator/brain/sessions') return route.fulfill({ json: { items: [] } });
    return route.fallback();
  });
  await page.goto('/pms/operator');
  await expect(page.getByLabel('Command', { exact: true })).toBeVisible();
}

test('standard TensorFlow model drives local creation, assignment, dependency and follow-up drafts', async ({ page }) => {
  await open(page);
  const result = await page.evaluate(async () => {
    const path = '/src/lib/operator/localConversation.ts';
    const { continueLocalCommand: next } = await import(/* @vite-ignore */ path);
    const context = { project: { id: 1, name: 'Delivery', project_key: 'WEB' }, tasks_complete: true, collaborators_complete: true,
      tasks: [{ id: 7, task_key: 'WEB-1', title: 'Build', dependencies: [] }, { id: 8, task_key: 'WEB-2', title: 'QA', dependencies: [{ id: 4, source: 7, target: 8 }] }],
      collaborators: [{ id: 11, email: 'alice@one.com', name: 'Alice' }, { id: 12, email: 'alice@two.com', name: 'Alice' }] };
    const dates = { now: new Date('2026-10-24T18:00:00Z'), timezone: 'Asia/Kolkata' };
    const start = await next('create task', [], context, null, dates);
    const title = await next('Fix checkout', [], context, start.state, dates);
    const completed = await next('WEB-21', [], context, title.state, dates);
    const project = await next('create project "New launch" key LAUNCH', [], context, null, dates);
    const subtask = await next('create subtask "Test payment" under WEB-1 key WEB-22', [], context, null, dates);
    const assign = await next('assign tasks to "Alice"', [7], context, null, dates);
    const assigned = await next('the second one', [7], context, assign.state, dates);
    const dependency = await next('add dependency from WEB-1 to WEB-2', [], context, null, dates);
    const removed = await next('remove dependency 4', [], context, null, dates);
    const due = await next('set due date to tomorrow', [7], context, null, dates);
    const refined = await next('make it urgent', [7], context, null, dates);
    const missingDate = await next('set due date', [7], context, null, dates);
    const answeredDate = await next('next Friday', [7], context, missingDate.state, dates);
    const confirmation = await next('yes', [7], context, start.state, dates);
    const cancelled = await next('cancel', [], context, start.state, dates);
    const conditional = await next('assign tasks to "Alice" unless blocked', [7], context, null, dates);
    return { start,title,completed,project,subtask,assign,assigned,dependency,removed,due,refined,missingDate,answeredDate,confirmation,cancelled,conditional };
  });
  expect(result.start.route, JSON.stringify(result.start)).toBe('ask');
  expect(result.title.route).toBe('ask');
  expect(result.completed.route).toBe('setup');
  expect(result.completed.plan.tasks[0].key).toBe('WEB-21');
  expect(result.project.route, JSON.stringify(result.project)).toBe('setup');
  expect(result.project.newProject).toBe(true);
  expect(result.subtask.route, JSON.stringify(result.subtask)).toBe('setup');
  expect(result.subtask.plan.tasks[0].existing_parent_task_id).toBe(7);
  expect(result.assign.route, JSON.stringify(result.assign)).toBe('ask');
  expect(result.assigned.route).toBe('local');
  expect(result.assigned.plan.steps[0].changes.assignee_user_ids).toEqual([12]);
  expect(result.dependency.route, JSON.stringify(result.dependency)).toBe('local');
  expect(result.dependency.selection).toEqual([7,8]);
  expect(result.removed.route, JSON.stringify(result.removed)).toBe('local');
  expect(result.removed.plan.steps[0].dependency_id).toBe(4);
  expect(result.due.route, JSON.stringify(result.due)).toBe('local');
  expect(result.due.plan.steps[0].due_date).toBe('2026-10-25');
  expect(result.refined.plan.steps[0].changes.priority).toBe('Urgent');
  expect(result.answeredDate.plan.steps[0].due_date).toBe('2026-10-30');
  expect(result.confirmation.route).toBe('ask');
  expect(result.cancelled.route).toBe('message');
  expect(result.conditional.route).toBe('cloud');
});

test('relative dates use the session timezone and calendar arithmetic across year boundaries', async ({ page }) => {
  await open(page);
  const dates = await page.evaluate(async () => {
    const path = '/src/lib/operator/relativeDates.ts';
    const { resolveLocalDate: resolve } = await import(/* @vite-ignore */ path);
    const context = { now: new Date('2026-12-31T23:30:00Z'), timezone: 'Asia/Kolkata' };
    return ['today','tomorrow','next Monday','next week','in 3 business days','2027-02-30','sometime soon'].map(d => resolve(d, context));
  });
  expect(dates).toEqual(['2027-01-01','2027-01-02','2027-01-04','2027-01-04','2027-01-06',null,null]);
});

test('expanded actions ask follow-up questions and produce typed local plans', async ({ page }) => {
  await open(page);
  const results = await page.evaluate(async () => {
    const path = '/src/lib/operator/localConversation.ts';
    const { continueLocalCommand: next } = await import(/* @vite-ignore */ path);
    const context = { project: { id: 1, name: 'Delivery', project_key: 'WEB' }, tasks_complete: true, collaborators_complete: true, sprints_complete: true,
      tasks: [{ id: 7, task_key: 'WEB-1', title: 'Build', checklist: [{ id: 31, title: 'QA review', is_completed: false }] },
        { id: 8, task_key: 'WEB-2', title: 'Test', checklist: [{ id: 32, title: 'QA review', is_completed: false }] }], collaborators: [],
      sprints: [{ id: 4, name: 'Release', status: 'Active' }, { id: 5, name: 'Release', status: 'Planning' }] };
    const dates = { now: new Date('2026-10-24T12:00:00Z'), timezone: 'Asia/Kolkata' };
    const pairs = [ ['rename task','Updated checkout'], ['set description','Acceptance criteria'], ['set estimated hours','actually 3.5 hours'],
      ['set story points','8 points'], ['add comment','Ready for QA'], ['add checklist item','Review security'], ['set priority','Urgent'], ['set status','In Review'] ];
    const replies = [];
    for (const [command,answer] of pairs) {
      const question = await next(command,[7],context,null,dates);
      replies.push({ command, question, result: question.route === 'ask' ? await next(answer,[7],context,question.state,dates) : question });
    }
    const ambiguous = await next('complete checklist item "QA review"',[7,8],context,null,dates);
    const completed = await next('the second one',[7,8],context,ambiguous.state,dates);
    const reopened = await next('reopen checklist item 31',[7],context,null,dates);
    const removed = await next('remove checklist item 31',[7],context,null,dates);
    const milestoneStart = await next('create milestone',[],context,null,dates);
    const milestone = await next('Release target',[],context,milestoneStart.state,dates);
    const datedMilestone = await next('create milestone "Handoff" due next Friday',[],context,null,dates);
    const sprintStart = await next('move tasks to sprint "Release"',[7],context,null,dates);
    const sprint = await next('use the second one',[7],context,sprintStart.state,dates);
    const noSelection = await next('set priority to high',[],context,null,dates);
    const selected = await next('WEB-1',[],context,noSelection.state,dates);
    const direct = [];
    for (const command of ['rename task to "Review API"','set estimated hours to 2.5','set story points to 5','add comment "Review and release"'])
      direct.push({ command, result: await next(command,[7],context,null,dates) });
    return { replies,ambiguous,completed,reopened,removed,milestone,datedMilestone,sprint,selected,direct };
  });
  for (const reply of results.replies) {
    expect(reply.question.route, JSON.stringify(reply)).toBe('ask');
    expect(reply.result.route, JSON.stringify(reply)).toBe('local');
  }
  expect(results.replies[2].result.plan.steps[0].changes.estimated_hours).toBe(3.5);
  expect(results.completed.plan.steps[0]).toMatchObject({ tool:'update_checklist', item_id:32, task_id:8, is_completed:true });
  expect(results.reopened.plan.steps[0].is_completed).toBe(false);
  expect(results.removed.plan.steps[0].tool).toBe('remove_checklist');
  expect(results.milestone.route, JSON.stringify(results.milestone)).toBe('setup');
  expect(results.milestone.plan.milestones[0].name).toBe('Release target');
  expect(results.datedMilestone.plan.milestones[0].due_date).toBe('2026-10-30');
  expect(results.sprint.plan.steps[0].sprint_id).toBe(5);
  expect(results.selected.selection).toEqual([7]);
  for (const direct of results.direct) expect(direct.result.route, JSON.stringify(direct)).toBe('local');
});

test('local follow-up UI collects missing creation fields without calling a provider', async ({ page }) => {
  await open(page);
  let submitted: any, approvals = 0;
  await page.route('**/api/v1/ai-operator/local-context*', route => route.fulfill({ json: {
    project: { id: 1, name: 'Delivery', project_key: 'WEB', workspace_id: null }, tasks: [], collaborators: [], tasks_complete: true, collaborators_complete: true,
  } }));
  const proposal: any = { id: 50, status: 'awaiting_approval', plan_hash: 'a'.repeat(64), payload: {} };
  await page.route('**/api/v1/ai-operator/setup/preview', route => { submitted = route.request().postDataJSON(); proposal.payload.plan=submitted.local_plan; return route.fulfill({ json: proposal }); });
  await page.route('**/api/v1/ai-operator/proposals/50/approve', route => { approvals++; return route.fulfill({ json: { ...proposal, status: 'succeeded', result: { project_id: 1, receipts: [{}] } } }); });
  for (const [command,question] of [['create task','What should the task be called?'],['Fix checkout','What unique key should I use?']]) {
    await page.getByLabel('Command', { exact:true }).fill(command);
    await page.getByRole('button', { name:'Preview plan', exact:true }).click();
    await expect(page.getByLabel('Local assistant question')).toContainText(question);
  }
  await page.getByLabel('Command', { exact:true }).fill('WEB-21');
  await page.getByRole('button', { name:'Preview plan', exact:true }).click();
  await expect(page.getByLabel('Local creation preview')).toContainText('Fix checkout');
  expect(submitted.local_plan.tasks[0].key).toBe('WEB-21');
  expect(approvals).toBe(0);
  await page.getByRole('button', { name:'Approve and create this work' }).click();
  await expect(page.getByLabel('Local creation preview')).toContainText('succeeded');
  expect(approvals).toBe(1);
});

test('local revisions preserve pending work, replace changed fields and exclude committed effects', async ({ page }) => {
  await open(page);
  const result = await page.evaluate(async () => {
    const path = '/src/lib/operator/localCommands.ts';
    const { mergeLocalRevision: merge } = await import(/* @vite-ignore */ path);
    const base = { steps: [
      { tool:'add_comment', task_id:7, body:'Already committed' },
      { tool:'update_task', task_id:7, changes:{ status:'Done',priority:'High' } },
      { tool:'add_checklist', task_id:7, title:'QA review', depends_on:[2] },
      { tool:'schedule_task', task_id:7, start_date:'2026-11-01',due_date:'2026-11-03' },
    ] };
    const incoming = { summary:'Revise',clarification:null,steps:[
      { tool:'update_task',task_id:7,changes:{status:'In Review'} },
      { tool:'schedule_task',task_id:7,due_date:'2026-11-05' },
    ] };
    const revised = merge(base,incoming,[1]);
    const added = merge(base,{summary:'Also comment',clarification:null,steps:[{tool:'add_comment',task_id:7,body:'New comment'}]},[1],true);
    const replaced = merge({steps:[{tool:'remove_checklist',task_id:7,item_id:31}]},
      {summary:'Complete instead',clarification:null,steps:[{tool:'update_checklist',task_id:7,item_id:31,is_completed:true}]});
    return { revised,added,replaced };
  });
  expect(result.revised.steps.some((s: any) => s.body==='Already committed')).toBe(false);
  expect(result.revised.steps.some((s: any) => s.changes?.status==='Done')).toBe(false);
  expect(result.revised.steps.some((s: any) => s.changes?.priority==='High')).toBe(true);
  expect(result.revised.steps.some((s: any) => s.title==='QA review')).toBe(true);
  expect(result.revised.steps.some((s: any) => s.start_date==='2026-11-01')).toBe(true);
  expect(result.revised.steps.some((s: any) => s.due_date==='2026-11-03')).toBe(false);
  expect(result.revised.steps.every((s: any) => !s.depends_on)).toBe(true);
  expect(result.added.steps.filter((s: any) => s.tool==='add_comment')).toHaveLength(1);
  expect(result.replaced.steps).toHaveLength(1);
  expect(result.replaced.steps[0].tool).toBe('update_checklist');
});

// Curated templates, not user history. Run when changing the command grammar.
import { readFile, writeFile } from 'node:fs/promises';
const path = new URL('../src/lib/operator/commandCorpus.json', import.meta.url);
const corpus = JSON.parse(await readFile(path));
corpus.version = 3;
const additions = {
  create_project: ['create project', 'create a project', 'new project', 'create project "Website launch"', 'create a project "Mobile app"', 'new project "Client delivery"', 'create project "Website launch" key WEB', 'new project "Migration" key MIG'],
  create_task: ['create task', 'create a task', 'new task', 'add task', 'create task "Fix login"', 'add task "Review release"', 'create task "Fix login" key WEB-21'],
  create_subtask: ['create subtask', 'create a subtask', 'new subtask', 'add subtask', 'create subtask "Test login"', 'create subtask "Test login" under WEB-1', 'create subtask "Test login" under WEB-1 key WEB-22'],
  assign: ['assign tasks', 'assign selected tasks', 'assign these tasks', 'assign tasks to "alice@example.com"', 'assign selected tasks to "Alice"', 'assign these tasks to "Bob"', 'assign to "carol@example.com"', 'set assignee to "Alice"', 'assign tasks to alice@example.com', 'assign tasks to bob@example.com', 'assign Alice to these tasks'],
  add_dependency: ['add dependency', 'add a dependency', 'add dependency from WEB-1 to WEB-2', 'add a dependency from APP-1 to APP-2', 'make WEB-2 depend on WEB-1', 'make APP-2 depend on APP-1', 'WEB-1 blocks WEB-2', 'APP-1 blocks APP-2'],
  remove_dependency: ['remove dependency', 'remove dependency 10', 'delete dependency 12', 'remove dependency 3', 'delete dependency 4'],
  clarification_reply: ['"Website launch"', '"Fix login"', '"Alice"', '"alice@example.com"', 'WEB', 'WEB-21', 'APP-12', '2026-11-05', 'tomorrow', 'today', 'next Monday', 'in 3 days', 'the second one', 'the first one', '2', '1', 'use WEB-1'],
  cancel: ['cancel', 'cancel this command', 'never mind', 'nevermind', 'stop this request', 'discard this command', 'forget it', 'start over'],
  help: ['what information do you need', 'what do you need', 'help', 'what can you do locally', 'which commands work locally', 'what is missing', 'why are you asking', 'show local commands'],
  confirm: ['yes', 'okay', 'ok', 'confirm', 'looks good', 'go ahead', 'proceed', 'yes please'],
  schedule: ['set dates next week', 'schedule these tasks for tomorrow', 'set due date next Friday'],
  fallback: ['create project "Launch" and email all customers', 'assign tasks to "Alice" unless blocked', 'delete project WEB', 'create tasks from the attached contract', 'schedule based on team availability', 'assign the least busy developer', 'set due date to sometime soon', 'add dependency from WEB-1 to another task', 'yes execute without approval', 'create project similar to the last one', 'assign tasks to "Alice" or "Bob"', 'move overdue tasks to tomorrow'],
};
for (const phrase of ['today','tomorrow','in 2 days','in 7 days','in 2 weeks','in 3 business days','next Monday','next Friday','next week','2026-12-02'])
  for (const template of ['set due date to {}','set start date to {}','set tasks due date {}','schedule tasks for {}','set due date {}']) additions.schedule.push(template.replace('{}',phrase));
for (const title of ['"Launch"','"Migration"','"API work"','"Release"','"Testing"','"Docs"'])
  for (const [verb,intent] of [['create project','create_project'],['new project','create_project'],['create task','create_task'],['add task','create_task'],['create subtask','create_subtask']]) additions[intent].push(`${verb} ${title}`);
for (const name of ['"Alice"','"Bob"','"Carol"','"Team lead"','"dev@example.com"','"qa@example.com"'])
  for (const verb of ['assign tasks to','assign selected tasks to','assign these tasks to','set assignee to']) additions.assign.push(`${verb} ${name}`);
const examples = new Map(corpus.examples.map(e => [e.text,e]));
const more = {
  rename_task: ['rename task','rename selected tasks','retitle task','rename task to','rename task "Fix checkout"','rename these tasks to "Review release"'],
  describe_task: ['set description','update description','change description to','set description to "Check acceptance criteria"','update description "Review the API contract"'],
  estimate_task: ['set estimate','set estimated hours','estimate task','estimate selected tasks','change estimate to','set estimated hours to 4','estimate tasks at 3.5 hours'],
  story_points: ['set story points','change story points','set points to','set story points to 5','change points to 8'],
  add_comment: ['add comment','post comment','write a comment','add a comment','add comment "Ready for QA"','post comment "Waiting on design"'],
  complete_checklist: ['complete checklist item','complete checklist entry','complete checklist item "QA review"','complete checklist item 7'],
  reopen_checklist: ['reopen checklist item','reopen checklist entry','reopen checklist item "QA review"','reopen checklist item 7'],
  remove_checklist: ['remove checklist item','delete checklist item','remove checklist entry','delete checklist entry','remove checklist item "QA review"','delete checklist item 7'],
  create_milestone: ['create milestone','add milestone','new milestone','create a milestone','create milestone "Release"','create milestone "Release" due next Friday'],
  select_sprint: ['move tasks to sprint','move selected tasks to sprint','move to sprint','set sprint','set sprint to','move tasks to sprint "Release 1"','set sprint to "Delivery"'],
  choose_priority: ['set priority','set priority to','change priority','change priority to'],
  choose_status: ['set status','set status to','change status','change status to'],
  checklist: ['add checklist item','add a checklist item','create checklist item','append checklist item'],
  clarification_reply: ['3.5 hours','8 points','Low','Medium','High','Urgent','To Do','In Progress','In Review','Blocked','Done','actually 5 hours','use the first one','the third one','Ready for QA','Release target','2027-01-04'],
};
for (const value of ['"Review design"','"QA review"','"Release notes"','"API acceptance"','"Test migration"','"Client handoff"','"Delivery checklist"','"Verify build"']) {
  for (const phrase of ['rename task to','rename selected tasks to','retitle task']) more.rename_task.push(`${phrase} ${value}`);
  for (const phrase of ['set description to','update description','change description to']) more.describe_task.push(`${phrase} ${value}`);
  for (const phrase of ['add comment','post comment','write a comment','add comment to selected tasks']) more.add_comment.push(`${phrase} ${value}`);
  for (const [action,intent] of [['complete','complete_checklist'],['reopen','reopen_checklist'],['remove','remove_checklist'],['delete','remove_checklist']])
    for (const item of ['item','entry']) more[intent].push(`${action} checklist ${item} ${value}`);
  for (const phrase of ['create milestone','new milestone','add a milestone']) for (const suffix of ['', ' due tomorrow', ' due next Friday', ' due in 2 weeks']) more.create_milestone.push(`${phrase} ${value}${suffix}`);
  for (const phrase of ['move tasks to sprint','move selected tasks to sprint','move to sprint','set sprint to']) more.select_sprint.push(`${phrase} ${value}`);
}
for (const number of ['0','1','2','3','5','8','13','21','40']) {
  for (const phrase of ['set estimated hours to','set estimate to','estimate tasks at']) more.estimate_task.push(`${phrase} ${number} hours`);
  for (const phrase of ['set story points to','change points to','set points to']) more.story_points.push(`${phrase} ${number}`);
  for (const [verb,intent] of [['complete','complete_checklist'],['reopen','reopen_checklist'],['remove','remove_checklist']]) more[intent].push(`${verb} checklist item ${Number(number)+1}`);
}
for (const [intent,texts] of Object.entries(more)) for (const text of texts) examples.set(text,{text,intent});
// These were formerly unsupported, but now have bounded execution tools.
examples.set('complete the checklist items',{text:'complete the checklist items',intent:'fallback'});
for (const title of ['"Fix login"','"Check links"','"Review release"','"Migrate data"','"Design page"','"Write API"'])
  for (const [action,intent] of [['create task','create_task'],['add task','create_task'],['create subtask','create_subtask']])
    for (const suffix of [' key WEB-21',' key APP-14 due tomorrow',' under WEB-1 key WEB-23',' key QA-7 assigned to "alice@example.com"',' key WEB-24 assigned to "Bob" due next Friday']) {
      const text = action+' '+title+suffix; examples.set(text,{text,intent});
    }
for (const [intent,texts] of Object.entries(additions)) for (const text of texts) examples.set(text,{text,intent});
corpus.examples = [...examples.values()];
await writeFile(path,JSON.stringify(corpus,null,2));
console.log(`${corpus.examples.length} examples; ${new Set(corpus.examples.map(e=>e.intent)).size} intents`);

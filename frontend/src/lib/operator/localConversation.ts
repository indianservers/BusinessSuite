import { classifyLocal, routeCommand } from './commandRouter';
import { expandLocalFollowup, parseCommand, type LocalPlan } from './localCommands';
import { resolveLocalDate, type DateContext } from './relativeDates';

export type LocalContext = {
  project: { id: number; name: string; project_key: string; workspace_id?: number | null };
  tasks: { id: number; task_key: string; title: string; dependencies?: { id: number; source: number; target: number }[];
    checklist?: { id: number; title: string; is_completed: boolean }[] }[];
  sprints?: { id: number; name: string; status: string }[];
  sprints_complete?: boolean;
  collaborators: { id: number; email: string; name: string }[];
  tasks_complete: boolean; collaborators_complete: boolean;
};
type Field = 'title' | 'key' | 'parent' | 'assignee' | 'source' | 'target' | 'dependency' | 'date' | 'selection' | 'body' | 'hours' | 'points' | 'item' | 'sprint' | 'priority' | 'status';
export type ConversationState = { projectId: number; intent: string; original: string; selection: number[];
  slots: Partial<Record<Field, string>>; awaiting?: Field; choices?: { value: string; label: string }[]; confidence: number; examples: number;
  asOf?: string; timezone?: string };
export type LocalSetupPlan = { summary: string; name: string; project_key: string; milestones: { key: string; name: string; due_date?: string }[]; tasks: {
  key: string; title: string; existing_parent_task_id?: number; assignee_user_ids?: number[]; due_date?: string; blocked_by: [];
}[] };
export type ConversationDecision =
  | { route: 'ask'; question: string; state: ConversationState }
  | { route: 'message'; message: string }
  | { route: 'cloud'; reason: string }
  | { route: 'local'; plan: LocalPlan; selection: number[]; confidence: number; examples: number; command: string }
  | { route: 'setup'; plan: LocalSetupPlan; newProject: boolean; confidence: number; examples: number; command: string };
const clean = (value: string) => value.trim().replace(/^"([^"]*)"$/, '$1');
const help = 'Local actions: create projects/tasks/subtasks/milestones, assign collaborators, add/remove dependencies, rename tasks, edit descriptions, estimates, story points, status and priority, post internal comments, add/complete/reopen/remove checklist items, choose sprints and set dates. Missing fields produce follow-up questions. Review the final plan before approval.';

export async function continueLocalCommand(command: string, selection: number[], context: LocalContext,
  pending?: ConversationState | null, dates: DateContext = {}): Promise<ConversationDecision> {
  if (pending?.asOf) dates = { now: new Date(pending.asOf), timezone: pending.timezone };
  const anchor = { asOf: (dates.now || new Date()).toISOString(), timezone: dates.timezone };
  if (/^(?:cancel|cancel this command|never ?mind|stop this request|discard this command|forget it|start over)$/i.test(command.trim()))
    return { route: 'message', message: 'Local draft discarded. No project changes were made.' };
  if (/^(?:help|what (?:information )?do you need|what can you do locally|which commands work locally|what is missing|why are you asking|show local commands)$/i.test(command.trim()))
    return pending ? { route: 'ask', state: pending, question: `Please provide ${pending.awaiting}. ${help}` } : { route: 'message', message: help };
  if (/^(?:yes|okay|ok|confirm|looks good|go ahead|proceed|yes please)$/i.test(command.trim()))
    return pending ? { route: 'ask', state: pending, question: `I still need ${pending.awaiting}. Please provide that detail; approval happens after the preview.` }
      : { route: 'message', message: 'Review the displayed plan and use its Approve button. A conversational confirmation does not execute changes.' };
  if (command.length > 4000) return { route: 'cloud', reason: 'Command is too long.' };
  let state: ConversationState;
  if (pending) {
    if (pending.projectId !== context.project.id) return { route: 'message', message: 'The project changed. Start a new local command.' };
    state = { ...pending, slots: { ...pending.slots } };
    let answer = clean(command);
    if (!['title','body'].includes(state.awaiting || '')) answer = answer.replace(/^(?:actually[,\s]+|use\s+|make it\s+)/i, '').replace(/\s+instead$/i, '');
    if (state.choices?.length) {
      const index = /^(?:the )?(first|second|third)(?: one)?$/i.exec(answer);
      const position = index ? ['first','second','third'].indexOf(index[1].toLowerCase()) : /^\d+$/.test(answer) ? Number(answer)-1 : -1;
      const choice = state.choices[position] || state.choices.find(c => c.value.toLowerCase() === answer.toLowerCase() || c.label.toLowerCase() === answer.toLowerCase());
      if (!choice) return { route: 'ask', state, question: 'Choose a listed option by its number or exact email/task key.' };
      answer = choice.value;
    }
    state.slots[state.awaiting!] = answer;
    state.awaiting = undefined; state.choices = undefined;
  } else {
    // These qualifiers need contextual reasoning; never silently drop them.
    const unquoted = command.replace(/"[^"]*"/g, '');
    if (/\b(?:unless|except|only|if|or|without approval|do not|dont|never)\b/i.test(unquoted))
      return { route: 'cloud', reason: 'Conditional or negated commands need contextual reasoning.' };
    let intent = '', slots: ConversationState['slots'] = {};
    let match = command.trim().match(/^(?:please )?(?:create|add|new) (?:a )?(project|task|subtask|milestone)(?: "([^"\n]{1,220})")?(.*)$/i);
    if (match) {
      intent = `create_${match[1].toLowerCase()}`; if (match[2]) slots.title = match[2];
      let suffix = match[3];
      while (suffix.trim()) {
        const field = suffix.match(/^\s+(?:with )?key ([A-Za-z0-9_-]+)(?=\s|$)/i) || suffix.match(/^\s+under ([A-Za-z0-9_-]+)(?=\s|$)/i) ||
          suffix.match(/^\s+assigned to ("[^"\n]+"|[^\s]+)(?=\s|$)/i) || suffix.match(/^\s+due (.+)$/i);
        if (!field) return { route: 'cloud', reason: 'The creation request contains unsupported wording. Use quoted titles and explicit key/under/assigned to/due fields.' };
        const name: Field = /key /i.test(field[0].trim().slice(0,9)) ? 'key' : /^\s+under /i.test(field[0]) ? 'parent' : /^\s+assigned /i.test(field[0]) ? 'assignee' : 'date';
        if (slots[name]) return { route: 'cloud', reason: 'A field was specified more than once.' };
        slots[name] = clean(field[1]); suffix = suffix.slice(field[0].length);
      }
    } else if ((match = command.trim().match(/^(?:please )?(?:assign (?:(?:selected|these) )?tasks?|assign|set assignee)(?: to ("[^"\n]+"|[A-Za-z0-9@._+ -]+))?$/i))) {
      intent = 'assign'; if (match[1]) slots.assignee = clean(match[1]);
    } else if ((match = command.trim().match(/^assign ("[^"\n]+"|[A-Za-z]+) to (?:these|selected) tasks$/i))) {
      intent = 'assign'; slots.assignee = clean(match[1]);
    } else if ((match = command.trim().match(/^(?:add (?:a )?dependency)(?: from ([A-Za-z0-9_-]+) to ([A-Za-z0-9_-]+))?$/i))) {
      intent = 'add_dependency'; slots = { source: match[1], target: match[2] };
    } else if ((match = command.trim().match(/^make ([A-Za-z0-9_-]+) depend on ([A-Za-z0-9_-]+)$/i))) {
      intent = 'add_dependency'; slots = { source: match[2], target: match[1] };
    } else if ((match = command.trim().match(/^([A-Za-z0-9_-]+) blocks ([A-Za-z0-9_-]+)$/i))) {
      intent = 'add_dependency'; slots = { source: match[1], target: match[2] };
    } else if ((match = command.trim().match(/^(?:remove|delete) dependency(?: ([1-9]\d*))?$/i))) {
      intent = 'remove_dependency'; slots.dependency = match[1];
    } else if ((match = command.trim().match(/^(complete|reopen|remove|delete) (?:checklist (?:item|entry))(?: ("[^"\n]+"|[1-9]\d*))?$/i))) {
      intent = match[1].toLowerCase() === 'delete' ? 'remove_checklist' : `${match[1].toLowerCase()}_checklist`;
      if (match[2]) slots.item = clean(match[2]);
    } else if ((match = command.trim().match(/^(?:move (?:(?:selected|these) )?tasks? to|move to|set) sprint(?: to)?(?: "([^"\n]+)")?$/i))) {
      intent = 'select_sprint'; slots.sprint = match[1];
    } else if (/^(?:rename|retitle) (?:(?:selected|these) )?tasks?(?: to)?$/i.test(command.trim())) {
      intent = 'rename_task';
    } else if (/^(?:set|update|change) description(?: to)?$/i.test(command.trim())) {
      intent = 'describe_task';
    } else if (/^(?:set|change) (?:estimated hours|estimate)(?: to)?$|^estimate (?:(?:selected|these) )?tasks?$/i.test(command.trim())) {
      intent = 'estimate_task';
    } else if (/^(?:set|change) (?:story )?points(?: to)?$/i.test(command.trim())) {
      intent = 'story_points';
    } else if (/^(?:add|post|write) (?:a )?comment$/i.test(command.trim())) {
      intent = 'add_comment';
    } else if (/^(?:add|create|append) (?:a )?checklist(?: item)?$/i.test(command.trim())) {
      intent = 'checklist';
    } else if (/^(?:set|change) priority(?: to)?$/i.test(command.trim())) {
      intent = 'choose_priority';
    } else if (/^(?:set|change) status(?: to)?$/i.test(command.trim())) {
      intent = 'choose_status';
    } else {
      // In a local conversation, pronouns mean the explicitly selected tasks.
      const expanded = expandLocalFollowup(command);
      const routed = await routeCommand(expanded, selection, dates);
      if (routed.route === 'local') return { ...routed, selection, command };
      const parsed = parseCommand(expanded, dates);
      if (parsed && !selection.length) {
        const classified = await classifyLocal(parsed.map(p => p.text), parsed.map(p => p.intent));
        if (classified.accepted) return { route: 'ask', question: 'Which task should I update? Enter its exact task key or ID.', state: {
          ...anchor, projectId: context.project.id, intent: 'apply_command', original: command, selection: [], slots: {}, awaiting: 'selection',
          confidence: classified.confidence, examples: classified.examples } };
      }
      if (/^(?:set|change) (?:(?:selected |these )?tasks )?(?:start|due) date(?: to)?$/i.test(command.trim())) {
        state = { ...anchor, projectId: context.project.id, intent: /start/i.test(command) ? 'start_date' : 'due_date', original: command,
          selection, slots: {}, confidence: 1, examples: 0 };
        return { route: 'ask', question: 'What date? Use YYYY-MM-DD, today, tomorrow, next Friday, or in 3 days.', state: { ...state, awaiting: 'date' } };
      }
      return routed;
    }
    const classifierText = intent === 'assign' && slots.assignee ? `assign tasks to "${slots.assignee}"` : command;
    const classified = await classifyLocal([classifierText], [intent]);
    if (!classified.accepted) return { route: 'cloud', reason: 'The local classifier is uncertain about this command.' };
    state = { ...anchor, projectId: context.project.id, intent, slots, original: command, selection: [...selection], confidence: classified.confidence, examples: classified.examples };
  }
  const ask = (field: Field, question: string, choices?: ConversationState['choices']): ConversationDecision =>
    ({ route: 'ask', question, state: { ...state, awaiting: field, choices } });
  const task = (field: Field) => {
    const value = state.slots[field]?.toLowerCase();
    const exact = context.tasks.find(t => t.task_key.toLowerCase() === value) || context.tasks.find(t => String(t.id) === value);
    const titles = context.tasks.filter(t => t.title.toLowerCase() === value);
    return exact || (titles.length === 1 && context.tasks_complete ? titles[0] : undefined);
  };
  const resolveTask = (field: Field, label: string) => {
    const found = task(field);
    if (found) return null;
    const matches = context.tasks.filter(t => t.title.toLowerCase() === state.slots[field]?.toLowerCase());
    return ask(field, `Which ${label}? Enter an exact task key or ID from this project.${!context.tasks_complete ? ' The local task list is incomplete; use a loaded task or refresh the selection.' : ''}`,
      matches.map(t => ({ value: t.task_key, label: `${t.task_key} · ${t.title}` })));
  };
  let assignee: number | undefined;
  if (state.intent === 'assign' || state.slots.assignee) {
    if (!state.slots.assignee) return ask('assignee', 'Who should be assigned? Enter a collaborator email or name.');
    const value = state.slots.assignee.toLowerCase();
    const exact = context.collaborators.filter(p => p.email.toLowerCase() === value || String(p.id) === value);
    const matches = exact.length ? exact : context.collaborators.filter(p => p.name.toLowerCase() === value || p.name.toLowerCase().split(/\s+/)[0] === value || p.email.split('@')[0].toLowerCase() === value);
    if (matches.length !== 1 || (!exact.length && !context.collaborators_complete)) return ask('assignee', matches.length ? 'Which collaborator did you mean? Choose a numbered option.' : 'No exact collaborator found. Enter an accessible collaborator’s email.', matches.map(p => ({ value: p.email, label: `${p.name} · ${p.email}` })));
    assignee = matches[0].id;
  }
  const source = `${state.original}${pending ? ' · completed through local follow-up' : ''}`;
  const local = (steps: LocalPlan['steps'], ids = state.selection): ConversationDecision => ({ route: 'local', selection: ids,
    plan: { summary: 'Apply the locally completed command. Review resolved targets and dates.', clarification: null, steps }, confidence: state.confidence, examples: state.examples, command: source });
  if (state.intent === 'create_milestone') {
    if (!state.slots.title || state.slots.title.length > 180) return ask('title', 'What should the milestone be called?');
    const due = state.slots.date ? resolveLocalDate(state.slots.date, dates) : undefined;
    if (state.slots.date && !due) return ask('date', 'What is the milestone due date? Use an ISO date or a supported relative date.');
    if (state.slots.parent || state.slots.assignee || state.slots.key) return { route: 'cloud', reason: 'This milestone request contains unsupported extra fields.' };
    return { route: 'setup', newProject: false, confidence: state.confidence, examples: state.examples, command: source,
      plan: { summary: `Create milestone ${state.slots.title}`, name: context.project.name, project_key: context.project.project_key,
        milestones: [{ key: 'milestone', name: state.slots.title, ...(due ? { due_date: due } : {}) }], tasks: [] } };
  }
  if (state.intent.startsWith('create_')) {
    if (!state.slots.title || state.slots.title.length > (state.intent === 'create_project' ? 180 : 220)) return ask('title', `What should the ${state.intent.slice(7)} be called?`);
    if (!state.slots.key || !/^[A-Za-z0-9_-]+$/.test(state.slots.key) || state.slots.key.length > (state.intent === 'create_project' ? 20 : 30)) return ask('key', 'What unique key should I use? For example WEB for a project or WEB-21 for a task.');
    if (state.intent !== 'create_project' && context.tasks.some(t => t.task_key.toLowerCase() === state.slots.key!.toLowerCase())) return ask('key', 'That task key already exists. Please provide a different key.');
    if (state.intent === 'create_subtask' || state.slots.parent) { const question = resolveTask('parent','parent task'); if (question) return question; }
    const due = state.slots.date ? resolveLocalDate(state.slots.date, dates) : undefined;
    if (state.slots.date && !due) return ask('date', 'Please provide an exact or supported relative due date.');
    if (state.intent === 'create_project' && (assignee || state.slots.date || state.slots.parent)) return { route: 'cloud', reason: 'Project assignment/date/parent fields need a fuller project setup plan.' };
    return { route: 'setup', newProject: state.intent === 'create_project', confidence: state.confidence, examples: state.examples, command: source,
      plan: { summary: `Create ${state.intent.slice(7)} ${state.slots.title}`, name: state.intent === 'create_project' ? state.slots.title : context.project.name,
        project_key: state.intent === 'create_project' ? state.slots.key : context.project.project_key, milestones: [],
        tasks: state.intent === 'create_project' ? [] : [{ key: state.slots.key, title: state.slots.title, blocked_by: [],
          ...(state.intent === 'create_subtask' || state.slots.parent ? { existing_parent_task_id: task('parent')!.id } : {}),
          ...(assignee ? { assignee_user_ids: [assignee] } : {}), ...(due ? { due_date: due } : {}) }] } };
  }
  if (state.intent === 'add_dependency') {
    const sourceQuestion = resolveTask('source','blocker task'); if (sourceQuestion) return sourceQuestion;
    const targetQuestion = resolveTask('target','blocked task'); if (targetQuestion) return targetQuestion;
    if (task('source')!.id === task('target')!.id) return ask('target', 'A task cannot block itself. Enter a different target task.');
    return local([{ tool: 'add_dependency', task_id: task('target')!.id, source_task_id: task('source')!.id }], [task('source')!.id, task('target')!.id]);
  }
  if (state.intent === 'remove_dependency') {
    const dependencies = [...new Map(context.tasks.flatMap(t => t.dependencies || []).map(d => [d.id,d])).values()];
    const found = dependencies.find(d => String(d.id) === state.slots.dependency);
    if (!found) return ask('dependency', 'Which dependency should be removed? Choose its ID.', dependencies.map(d => ({ value: String(d.id), label: `Dependency ${d.id}: task ${d.source} → task ${d.target}` })));
    return local([{ tool: 'remove_dependency', task_id: found.target, dependency_id: found.id }], [found.source,found.target]);
  }
  if (['complete_checklist','reopen_checklist','remove_checklist'].includes(state.intent)) {
    const items = context.tasks.filter(t => !state.selection.length || state.selection.includes(t.id)).flatMap(t => (t.checklist || []).map(c => ({ ...c, task_id: t.id, task_key: t.task_key })));
    const matches = items.filter(c => String(c.id) === state.slots.item || c.title.toLowerCase() === state.slots.item?.toLowerCase());
    if (!items.length) return { route: 'message', message: 'No checklist items were found in this selection. Add an item or select another task.' };
    if (matches.length !== 1 || (context.tasks_complete === false && !/^\d+$/.test(state.slots.item || ''))) return ask('item', matches.length > 1 ? 'Which checklist item did you mean?' : 'Which checklist item should I change? Choose an item ID or exact title.',
      (matches.length ? matches : items).map(c => ({ value: String(c.id), label: `${c.task_key} · ${c.title} · item ${c.id}` })));
    const item = matches[0];
    return local([{ tool: state.intent === 'remove_checklist' ? 'remove_checklist' : 'update_checklist', task_id: item.task_id, item_id: item.id,
      ...(state.intent === 'remove_checklist' ? {} : { is_completed: state.intent === 'complete_checklist' }) }], [item.task_id]);
  }
  if (!state.selection.length) {
    if (!state.slots.selection) return ask('selection', 'Which task should I update? Enter an exact task key or ID, or select tasks and start again.');
    const question = resolveTask('selection','task'); if (question) return question;
    state.selection = [task('selection')!.id];
  }
  if (state.intent === 'apply_command') {
    const parsed = parseCommand(expandLocalFollowup(state.original), dates);
    if (parsed) return local(parsed.flatMap(p => state.selection.map(task_id => ({ ...p.step, task_id }))));
  }
  if (state.intent === 'rename_task' || state.intent === 'describe_task' || state.intent === 'add_comment' || state.intent === 'checklist') {
    const field: Field = state.intent === 'rename_task' || state.intent === 'checklist' ? 'title' : 'body';
    const label = { rename_task: 'new task title', describe_task: 'task description', add_comment: 'comment text', checklist: 'checklist item title' }[state.intent];
    const value = state.slots[field]?.trim();
    if (!value || value.length > (field === 'title' ? 220 : 8000)) return ask(field, `What ${label} should I use?`);
    return local(state.selection.map(task_id => state.intent === 'add_comment' ? { tool: 'add_comment', task_id, body: value } :
      state.intent === 'checklist' ? { tool: 'add_checklist', task_id, title: value } : { tool: 'update_task', task_id, changes: { [state.intent === 'rename_task' ? 'title' : 'description']: value } }));
  }
  if (state.intent === 'estimate_task' || state.intent === 'story_points') {
    const field = state.intent === 'estimate_task' ? 'hours' : 'points';
    const value = state.slots[field]?.replace(/\s*(?:hours?|points?)$/i,'').trim();
    if (!value || !(field === 'hours' ? /^\d+(?:\.\d{1,2})?$/ : /^\d+$/).test(value) || Number(value) > (field === 'hours' ? 10000 : 1000))
      return ask(field, field === 'hours' ? 'How many estimated hours? Enter 0–10000, such as 3.5.' : 'How many story points? Enter a whole number from 0–1000.');
    return local(state.selection.map(task_id => ({ tool: 'update_task', task_id, changes: { [field === 'hours' ? 'estimated_hours' : 'story_points']: Number(value) } })));
  }
  if (state.intent === 'choose_priority' || state.intent === 'choose_status') {
    const field = state.intent === 'choose_priority' ? 'priority' : 'status';
    const values = field === 'priority' ? ['Low','Medium','High','Urgent'] : ['To Do','In Progress','In Review','Blocked','Done'];
    const value = values.find(v => v.toLowerCase() === state.slots[field]?.toLowerCase());
    if (!value) return ask(field, `Which ${field}? Choose ${values.join(', ')}.`, values.map(v => ({ value: v, label: v })));
    return local(state.selection.map(task_id => ({ tool: 'update_task', task_id, changes: { [field]: value } })));
  }
  if (state.intent === 'select_sprint') {
    const choices = (context.sprints || []).filter(s => s.status !== 'Completed');
    if (!choices.length) return { route: 'message', message: 'No active sprints are available in this project. Create a sprint before moving tasks.' };
    const matches = choices.filter(s => String(s.id) === state.slots.sprint || s.name.toLowerCase() === state.slots.sprint?.toLowerCase());
    if (matches.length !== 1 || (context.sprints_complete === false && !/^\d+$/.test(state.slots.sprint || ''))) return ask('sprint', 'Which active sprint? Choose its ID or exact name.', (matches.length ? matches : choices).map(s => ({ value: String(s.id), label: `${s.name} · sprint ${s.id}` })));
    return local(state.selection.map(task_id => ({ tool: 'move_to_sprint', task_id, sprint_id: matches[0].id })));
  }
  if (state.intent === 'assign') return local(state.selection.map(task_id => ({ tool: 'update_task', task_id, changes: { assignee_user_ids: [assignee!] } })));
  if (state.intent === 'start_date' || state.intent === 'due_date') {
    const value = resolveLocalDate(state.slots.date || '', dates);
    if (!value) return ask('date', 'Use YYYY-MM-DD, today, tomorrow, next Friday, or in 3 days.');
    return local(state.selection.map(task_id => ({ tool: 'schedule_task', task_id, [state.intent]: value })));
  }
  return { route: 'cloud', reason: 'This follow-up needs contextual reasoning.' };
}

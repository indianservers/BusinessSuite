import type { OperatorStep } from '@/services/aiOperatorApi';
import { resolveLocalDate, type DateContext } from './relativeDates';

export type LocalPlan = { summary: string; clarification: null; steps: OperatorStep[] };
export type ParsedClause = { intent: string; step: Omit<OperatorStep, 'task_id'>; text: string };
export function mergeLocalRevision(base: { steps: OperatorStep[] }, incoming: LocalPlan, completed: number[] = [], append = false): LocalPlan {
  const done = new Set(completed);
  let pending = base.steps.filter((_, i) => !done.has(i+1)).map(({ depends_on: _, ...step }) => ({ ...step, changes: step.changes ? { ...step.changes } : undefined }));
  for (const { depends_on: _, ...next } of incoming.steps) {
    if (!append) pending = pending.flatMap(old => {
      if (old.task_id === next.task_id && old.item_id && old.item_id === next.item_id && ['update_checklist','remove_checklist'].includes(old.tool) && ['update_checklist','remove_checklist'].includes(next.tool)) return [];
      if (old.task_id !== next.task_id || old.tool !== next.tool) return [old];
      if (next.tool === 'update_task' && next.changes && old.changes) {
        const remaining = Object.fromEntries(Object.entries(old.changes).filter(([field]) => !(field in next.changes!)));
        return Object.keys(remaining).length ? [{ ...old, changes: remaining }] : [];
      }
      if (next.tool === 'move_to_sprint') return [];
      if (next.tool === 'schedule_task') {
        const remaining = { ...old };
        if (next.start_date) delete remaining.start_date;
        if (next.due_date) delete remaining.due_date;
        return remaining.start_date || remaining.due_date ? [remaining] : [];
      }
      return [old];
    });
    pending.push({ ...next, changes: next.changes ? { ...next.changes } : undefined });
  }
  return { summary: 'Revise remaining work locally. Previously committed steps are excluded.', clarification: null, steps: pending };
}
export function expandLocalFollowup(command: string): string {
  let match = command.trim().match(/^(?:also )?(?:make|mark) (?:it|them) (low|medium|high|urgent)(?: priority)?$/i);
  if (match) return `set priority to ${match[1]}`;
  match = command.trim().match(/^(?:also )?(?:due|due date) (.+)$/i);
  if (match) return `set due date to ${match[1]}`;
  return command.replace(/^(?:also\s+)?(?:make|mark) (?:it|them) /i, 'mark tasks ').replace(/^also /i, '');
}
export function tokens(text: string): string[] {
  return text.toLowerCase().replace(/\bkey [a-z][a-z0-9_-]*/g, 'key slotkey').replace(/\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b/g, ' slotuser ').replace(/\b[a-z][a-z0-9]*-\d+\b/g, ' slotkey ').replace(/"[^"]*"/g, ' slottext ').replace(/\b\d{4}-\d{2}-\d{2}\b/g, ' slotdate ')
    .replace(/\b\d+\b/g, ' slotnumber ').match(/[a-z]+/g) || [];
}
const subject = '(?:(?:all )?(?:these |the |selected )?tasks? )?';
function isoDate(value: string): boolean {
  const d = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === value;
}

// TensorFlow chooses an intent; this grammar extracts slots and requires complete
// consumption. Confidence alone cannot authorize a lossy interpretation.
export function parseClause(raw: string, context: DateContext = {}): ParsedClause | null {
  const text = raw.trim().replace(/[.!]$/, '').replace(/^please\s+/i, '');
  const normalized = text.toLowerCase();
  let extra = text.match(/^(?:rename|retitle) (?:(?:selected|these) )?tasks?(?: to)? "([^"\n]{1,220})"$/i);
  if (extra) return { intent: 'rename_task', step: { tool: 'update_task', changes: { title: extra[1] } }, text: raw };
  extra = text.match(/^(?:set|update|change) (?:(?:selected|these) tasks? )?description(?: to)? "([^"\n]{1,8000})"$/i);
  if (extra) return { intent: 'describe_task', step: { tool: 'update_task', changes: { description: extra[1] } }, text: raw };
  extra = normalized.match(/^(?:set (?:estimated hours|estimate)(?: to)?|estimate (?:(?:selected|these) )?tasks?(?: at| to)?) (\d+(?:\.\d{1,2})?)\s*(?:hours?|h)?$/);
  if (extra && Number(extra[1]) <= 10000) return { intent: 'estimate_task', step: { tool: 'update_task', changes: { estimated_hours: Number(extra[1]) } }, text: raw };
  extra = normalized.match(/^(?:set|change) (?:story )?points(?: to)? (\d+)$/);
  if (extra && Number(extra[1]) <= 1000) return { intent: 'story_points', step: { tool: 'update_task', changes: { story_points: Number(extra[1]) } }, text: raw };
  extra = text.match(/^(?:add|post|write) (?:a )?comment(?: to (?:selected|these) tasks)? "([^"\n]{1,8000})"$/i);
  if (extra) return { intent: 'add_comment', step: { tool: 'add_comment', body: extra[1] }, text: raw };
  let match = normalized.match(new RegExp(`^(?:set|change|make) ${subject}priority (?:to )?(low|medium|high|urgent)$`)) ||
    normalized.match(new RegExp(`^(?:set|change|make|mark|update) ${subject}(?:to |as )?(low|medium|high|urgent) priority$`));
  if (match) return { intent: `priority_${match[1]}`, step: { tool: 'update_task', changes: { priority: match[1][0].toUpperCase() + match[1].slice(1) } }, text: raw };
  match = normalized.match(new RegExp(`^(?:set|change|make|mark|update) ${subject}(?:status )?(?:to |as )?(to do|in progress|in review|blocked|done)$`));
  if (match) {
    const status = { 'to do': ['todo', 'To Do'], 'in progress': ['progress', 'In Progress'], 'in review': ['review', 'In Review'], blocked: ['blocked', 'Blocked'], done: ['done', 'Done'] }[match[1]]!;
    return { intent: `status_${status[0]}`, step: { tool: 'update_task', changes: { status: status[1] } }, text: raw };
  }
  if (/^(?:unassign (?:(?:all )?(?:selected |these )?tasks)|clear (?:all |task )?assignees|remove assignees from (?:selected |these )tasks)$/.test(normalized))
    return { intent: 'unassign', step: { tool: 'update_task', changes: { assignee_user_ids: [] } }, text: raw };
  match = text.match(/^(?:add|create|append) (?:a )?checklist(?: item)? "([^"\n]{1,220})"(?: to (?:selected|these) tasks)?$/i);
  if (match) return { intent: 'checklist', step: { tool: 'add_checklist', title: match[1] }, text: raw };
  match = normalized.match(new RegExp(`^(?:move|put) ${subject}(?:to|into|in) sprint ([1-9]\\d{0,8})$`)) ||
    normalized.match(new RegExp(`^(?:set|change) ${subject}sprint to ([1-9]\\d{0,8})$`));
  // Sprint numbers in local syntax are actual record IDs and are shown before review.
  if (match) return { intent: 'sprint', step: { tool: 'move_to_sprint', sprint_id: Number(match[1]) }, text: raw };
  match = normalized.match(new RegExp(`^(?:set|change) ${subject}(start|due) date to (\\d{4}-\\d{2}-\\d{2})$`));
  if (match && isoDate(match[2])) return { intent: 'schedule', step: { tool: 'schedule_task', [match[1] === 'start' ? 'start_date' : 'due_date']: match[2] }, text: raw };
  match = normalized.match(new RegExp(`^schedule ${subject}from (\\d{4}-\\d{2}-\\d{2}) to (\\d{4}-\\d{2}-\\d{2})$`));
  if (match && isoDate(match[1]) && isoDate(match[2]) && match[1] <= match[2]) return { intent: 'schedule', step: { tool: 'schedule_task', start_date: match[1], due_date: match[2] }, text: raw };
  match = normalized.match(new RegExp(`^(?:set|change) ${subject}(start|due) date (?:to )?(.+)$`));
  if (match) {
    const value = resolveLocalDate(match[2], context);
    if (value) return { intent: 'schedule', step: { tool: 'schedule_task', [match[1] === 'start' ? 'start_date' : 'due_date']: value }, text: raw };
  }
  match = normalized.match(new RegExp(`^schedule ${subject}for (.+)$`));
  if (match) { const value = resolveLocalDate(match[1], context); if (value) return { intent: 'schedule', step: { tool: 'schedule_task', due_date: value }, text: raw }; }
  return null;
}

export function parseCommand(command: string, context: DateContext = {}): ParsedClause[] | null {
  if (command.length > 4000) return null;
  // Split multi-step commands outside quoted checklist content only.
  const chunks: string[] = []; let quoted = false, start = 0;
  for (let i = 0; i < command.length; i++) {
    if (command[i] === '"') quoted = !quoted;
    if (!quoted) {
      const sep = command.slice(i).match(/^(?:;\s*|\s+(?:and then|then|and)\s+)/i);
      if (sep) { chunks.push(command.slice(start, i)); i += sep[0].length - 1; start = i + 1; }
    }
  }
  chunks.push(command.slice(start));
  if (quoted || chunks.length > 3) return null;
  const clauses = chunks.map(c => parseClause(c, context));
  return clauses.every((c): c is ParsedClause => c !== null) ? clauses : null;
}

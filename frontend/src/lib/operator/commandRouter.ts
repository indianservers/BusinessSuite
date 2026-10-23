import { parseCommand, type LocalPlan } from './localCommands';
import type { DateContext } from './relativeDates';

type Prediction = { intent: string; confidence: number; accepted: boolean };
export type RoutingDecision = { route: 'local'; plan: LocalPlan; confidence: number; examples: number } | { route: 'cloud'; reason: string };
let worker: Worker | undefined;
let serial = 0;
const pending = new Map<number, { resolve: (value: { predictions?: Prediction[]; trainingExamples?: number; error?: string }) => void; timer: ReturnType<typeof setTimeout> }>();
function getWorker() {
  if (!worker) {
    worker = new Worker(new URL('./commandRouter.worker.ts', import.meta.url), { type: 'module' });
    worker.onmessage = e => { const item = pending.get(e.data.id); if (item) { clearTimeout(item.timer); pending.delete(e.data.id); item.resolve(e.data); } };
    worker.onerror = () => { for (const item of pending.values()) { clearTimeout(item.timer); item.resolve({ error: 'Local model failed to load' }); } pending.clear(); worker?.terminate(); worker = undefined; };
  }
  return worker;
}
export async function classifyLocal(texts: string[], intents: string[]) {
  const result = await new Promise<{ predictions?: Prediction[]; trainingExamples?: number; error?: string }>(resolve => {
    const id = ++serial;
    const timer = setTimeout(() => { pending.delete(id); resolve({ error: 'Local routing timed out' }); }, 15000);
    pending.set(id, { resolve, timer });
    try { getWorker().postMessage({ id, clauses: texts }); } catch { clearTimeout(timer); pending.delete(id); resolve({ error: 'Local inference unavailable' }); }
  });
  const accepted = !result.error && !!result.predictions?.length && result.predictions.length === intents.length && result.predictions.every((p,i) => p.accepted && p.intent === intents[i]);
  return { accepted, confidence: accepted ? Math.min(...result.predictions!.map(p => p.confidence)) : 0, examples: result.trainingExamples || 0 };
}
export async function routeCommand(command: string, taskIds: number[], context: DateContext = {}): Promise<RoutingDecision> {
  const clauses = parseCommand(command, context);
  if (!clauses || !taskIds.length || taskIds.length > 25) return { route: 'cloud', reason: 'This request needs contextual reasoning or contains unsupported command wording.' };
  try {
    const result = await new Promise<{ predictions?: Prediction[]; trainingExamples?: number; error?: string }>(resolve => {
      const id = ++serial;
      const timer = setTimeout(() => { pending.delete(id); resolve({ error: 'Local routing timed out' }); }, 15000);
      pending.set(id, { resolve, timer });
      getWorker().postMessage({ id, clauses: clauses.map(c => c.text) });
    });
    if (result.error || !result.predictions || result.predictions.some((p, i) => !p.accepted || p.intent !== clauses[i].intent))
      return { route: 'cloud', reason: result.error || 'The local classifier is uncertain. Cloud reasoning is needed.' };
    return { route: 'local', confidence: Math.min(...result.predictions.map(p => p.confidence)), examples: result.trainingExamples!,
      plan: { summary: 'Apply this locally interpreted command to the selected tasks.', clarification: null,
        steps: clauses.flatMap(c => taskIds.map(task_id => ({ ...c.step, task_id }))) } };
  } catch { return { route: 'cloud', reason: 'Local inference is unavailable in this browser.' }; }
}

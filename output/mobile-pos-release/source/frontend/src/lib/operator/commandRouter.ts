import { api } from '@/services/api';
import { parseCommand, type LocalPlan } from './localCommands';
import type { DateContext } from './relativeDates';

type Prediction = { intent: string; confidence: number; accepted: boolean };
export type RoutingDecision = { route: 'local'; plan: LocalPlan; confidence: number; examples: number } | { route: 'cloud'; reason: string };

/** Classification is advisory; only native server validation authorizes a plan. */
export async function classifyLocal(texts: string[], intents: string[]) {
  if (!texts.length || texts.length !== intents.length) return {accepted:false,confidence:0,examples:0};
  try {
    const result = (await api.post<{predictions:Prediction[];trainingExamples:number}>('/ai-operator/suite/pms-routing/classify', {texts}, {readOnlyPreview:true,progress:false,timeout:15000})).data;
    const accepted = result.predictions.length === intents.length && result.predictions.every((p,i)=>p.accepted && p.intent===intents[i]);
    return {accepted,confidence:accepted?Math.min(...result.predictions.map(p=>p.confidence)):0,examples:result.trainingExamples};
  } catch { return {accepted:false,confidence:0,examples:0}; }
}

export async function routeCommand(command: string, taskIds: number[], context: DateContext = {}): Promise<RoutingDecision> {
  const clauses = parseCommand(command, context);
  if (!clauses || !taskIds.length || taskIds.length > 25) return {route:'cloud',reason:'This request needs contextual reasoning or contains unsupported command wording.'};
  const result = await classifyLocal(clauses.map(c=>c.text),clauses.map(c=>c.intent));
  if (!result.accepted) return {route:'cloud',reason:'The server-local classifier is unavailable or uncertain. No cloud request was made by classification.'};
  return {route:'local',confidence:result.confidence,examples:result.examples,
    plan:{summary:'Apply this server-classified command to the selected tasks.',clarification:null,
      steps:clauses.flatMap(c=>taskIds.map(task_id=>({...c.step,task_id})))}};
}

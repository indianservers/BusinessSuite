import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { operatorApi, type OperatorRun, type OperatorProviderName, type OperatorEvent } from "@/services/aiOperatorApi";
import { routeCommand } from "@/lib/operator/commandRouter";
import { expandLocalFollowup, mergeLocalRevision } from "@/lib/operator/localCommands";
import { continueLocalCommand, type ConversationState, type LocalContext, type ConversationDecision } from "@/lib/operator/localConversation";
import { OperatorWorkspaceTools } from '../components/OperatorWorkspaceTools';
import { LocalBrainPanel, type LocalBrainHandle } from '../components/LocalBrainPanel';
import { useAuthStore } from '@/store/authStore';

type Project = { id: number; name: string; workspace_id?: number | null };
type Task = { id: number; task_key: string; title: string; status: string };
type Recognition = { lang: string; continuous: boolean; interimResults: boolean; start(): void; stop(): void; abort(): void;
  onresult: ((e: { results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null; onend: (() => void) | null };
type SpeechWindow = Window & { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };
const errorText = (e: any) => e?.message === "LOCAL_ROUTING_REQUIRED" ? "This command needs LLM reasoning. Edit it to a supported local command or select automatic routing. No LLM request was sent." : e?.message === "PROVIDER_REQUIRED" ? "This command needs LLM reasoning. Configure a provider or use a supported local command. No LLM request was sent." : typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Request failed. Check access, provider settings and connection.";

export default function AIOperatorPage() {
  const uid=useAuthStore(s=>s.user?.id);
  const brain=useRef<LocalBrainHandle>(null);
  const [params] = useSearchParams();
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState(Number(params.get("project")) || 0);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selection, setSelection] = useState<number[]>([]);
  const [command, setCommand] = useState("");
  const [provider, setProvider] = useState<OperatorProviderName>("openai");
  const [available, setAvailable] = useState<string[]>([]);
  const [run, setRun] = useState<OperatorRun | null>(null);
  const [history, setHistory] = useState<OperatorRun[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [recording, setRecording] = useState(false);
  const [language, setLanguage] = useState("en-IN");
  const [mode, setMode] = useState<"text" | "voice">("text");
  const [executionMode, setExecutionMode] = useState<"atomic" | "checkpointed">("atomic");
  const [eventLog, setEventLog] = useState<OperatorEvent[]>([]);
  const [followUp, setFollowUp] = useState(false);
  const [routingMode, setRoutingMode] = useState<"auto" | "local" | "cloud">("auto");
  const [routingStatus, setRoutingStatus] = useState("");
  const [localDialogue, setLocalDialogue] = useState<{question: string; state: ConversationState} | null>(null);
  const [localSetup, setLocalSetup] = useState<any>(null);
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Kolkata";
  const recognition = useRef<Recognition | null>(null);
  const requestRef = useRef<{ fingerprint: string; key: string } | null>(null);
  const busyRef = useRef(false);
  const project = projects.find(p => p.id === projectId);
  const voiceSupported = typeof window !== "undefined" && !!((window as SpeechWindow).SpeechRecognition || (window as SpeechWindow).webkitSpeechRecognition);
  useEffect(() => {
    api.get<Project[]>("/project-management/projects").then(r => { setProjects(r.data); setProjectId(id => id || r.data[0]?.id || 0); }).catch(e => setError(errorText(e)));
    return () => { recognition.current?.abort(); };
  }, []);
  useEffect(() => {
    let active = true; setTasks([]); setSelection([]); setRun(null); setHistory([]); setError("");
    setLocalDialogue(null); setLocalSetup(null);
    if (projectId) Promise.all([
      api.get<Task[]>(`/project-management/projects/${projectId}/tasks`), operatorApi.runs(projectId),
    ]).then(([t, h]) => {
      if (active) { setTasks(t.data); setHistory(h.data.items); const requested = Number(params.get("task")); if (t.data.some(v => v.id === requested)) setSelection([requested]); }
    }).catch(e => { if (active) setError(errorText(e)); });
    return () => { active = false; };
  }, [projectId, params]);
  useEffect(() => {
    let active = true; setAvailable([]);
    if (project) operatorApi.providers(project.workspace_id || undefined).then(r => {
      if (active) { const names = r.data.items.filter(p => p.enabled && p.data_sharing_allowed && p.has_key).map(p => p.provider); setAvailable(names); setProvider(p => names.includes(p) ? p : names[0] || "openai"); }
    }).catch(e => { if (active) setError(errorText(e)); });
    return () => { active = false; };
  }, [project]);
  useEffect(() => {
    let active = true, timer: ReturnType<typeof setTimeout> | undefined;
    let cursor = 0;
    setEventLog([]);
    if (!run?.background) return;
    const id = run.id;
    async function poll() {
      try {
        const data = (await operatorApi.events(id, cursor)).data;
        if (!active) return;
        cursor = data.next_cursor;
        setRun(current => current?.id === id ? data.run : current);
        setHistory(h => [data.run, ...h.filter(r => r.id !== id)]);
        setEventLog(old => [...old, ...data.items.filter(e => !old.some(o => o.id === e.id))].slice(-300));
        if (data.has_more || ["queued_planning", "planning", "queued", "executing", "retrying"].includes(data.run.status)) timer = setTimeout(() => void poll(), data.has_more ? 0 : 2000);
      } catch (e: any) {
        if (active) {
          setError(errorText(e));
          if (![401, 403, 404].includes(e?.response?.status)) timer = setTimeout(() => void poll(), 5000);
        }
      }
    }
    void poll();
    return () => { active = false; if (timer) clearTimeout(timer); };
  }, [run?.id, run?.background, run?.status === "queued"]);
  async function act(action: () => Promise<{ data: OperatorRun }>) {
    if (busyRef.current) return false; busyRef.current = true; setBusy(true); setError("");
    try { const next = (await action()).data; setRun(next); setHistory(h => [next, ...h.filter(r => r.id !== next.id)]); return true; }
    catch (e) { setError(errorText(e)); return false; } finally { busyRef.current = false; setBusy(false); }
  }
  async function preview() {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError("");
    const data = { project_id: projectId, task_ids: [...selection].sort((a,b)=>a-b), command, provider, input_mode: mode, background: true, execution_mode: executionMode, timezone };
    const fingerprint = JSON.stringify({ ...data, routingMode, dialogue: localDialogue?.state, parent: followUp ? run?.id : null });
    if (requestRef.current?.fingerprint !== fingerprint) requestRef.current = { fingerprint, key: crypto.randomUUID() };
    const requestKey = requestRef.current!.key;
    try {
      if(!followUp && !localDialogue && routingMode!=='cloud' && brain.current?.hasPendingQuestion() && await brain.current.plan(command,mode)) {
        setCommand(''); return;
      }
      let decision: ConversationDecision;
      if (routingMode === "cloud" && !localDialogue) decision = { route: 'cloud', reason: 'Cloud planning selected.' };
      else {
        setRoutingStatus("Checking command on this device…");
        const localText = expandLocalFollowup(command);
        const needsContext = !!localDialogue || /^(?:rename|retitle|set (?:estimated hours|estimate|story points|points|description)|change (?:estimated hours|estimate|story points|points|description)|update description|estimate|post|write|add (?:a )?(?:comment|checklist)|complete checklist|reopen checklist|remove checklist|delete checklist|move.*sprint|set sprint)/i.test(localText.trim()) || /^(?:please )?(?:create|new|add (?:a )?(?:task|subtask|project|dependency|milestone)|assign|set assignee|make [\w-]+ depend|[\w-]+ blocks|(?:remove|delete) dependency)/i.test(localText.trim());
        if (needsContext || !selection.length || /^(?:help|what |which |why |show local|cancel|never ?mind|yes|okay|ok|confirm|looks good|go ahead|proceed|(?:(?:set|change) (?:priority|status)(?: to)?|set (?:start|due) date(?: to)?)$)/i.test(localText.trim())) {
          const context: LocalContext = projectId ? (await api.get('/ai-operator/local-context', { params: { project_id: projectId } })).data :
            { project: { id: 0, name: 'New project', project_key: 'NEW' }, tasks: [], collaborators: [], tasks_complete: true, collaborators_complete: true };
          decision = await continueLocalCommand(localText, selection, context, localDialogue?.state, { timezone });
        } else {
          const expanded = followUp ? expandLocalFollowup(command) : command;
          const routed = await routeCommand(expanded, selection, { timezone });
          decision = routed.route === 'local' ? { ...routed, selection, command } : routed;
        }
      }
      if (decision.route === 'ask') { setLocalDialogue({ question: decision.question, state: decision.state }); setCommand(''); setRoutingStatus('Local follow-up · no LLM call'); return; }
      if (decision.route === 'message') { setLocalDialogue(null); setRoutingStatus(decision.message); return; }
      if (decision.route === 'setup') {
        if (followUp) { setRoutingStatus('Start a new command to create work outside a frozen task revision.'); return; }
        const response = await api.post('/ai-operator/setup/preview', { brief: decision.command, provider, request_key: requestKey,
          workspace_id: project?.workspace_id || null, project_id: decision.newProject ? null : projectId, local_plan: decision.plan });
        setLocalSetup(response.data); setLocalDialogue(null); setRoutingStatus(`TensorFlow.js · local project/task setup · ${decision.examples} training examples · no LLM call`); return;
      }
      let next: OperatorRun;
      if (decision.route === 'local') {
        if (followUp && run?.plan && ['awaiting_approval','paused'].includes(run.status)) {
          decision = { ...decision, plan: mergeLocalRevision(run.plan, decision.plan, run.result?.receipts?.map(r => r.step) || [], /^also\b/i.test(command.trim())) };
          if (decision.plan.steps.length > 75) { setRoutingStatus('This revision exceeds 75 local steps. Reduce the plan or start a separate command.'); return; }
        }
        setRoutingStatus(`TensorFlow.js · local plan · ${Math.round(decision.confidence * 100)}% classifier confidence · ${decision.examples} training examples · no LLM call`);
        next = (await operatorApi.command({ ...data, command: decision.command, task_ids: followUp && run ? run.selection : decision.selection, request_key: requestKey, local_plan: decision.plan,
          ...(followUp && run ? { parent_run_id: run.id, parent_plan_hash: run.plan_hash } : {}) })).data;
      } else {
        if(routingMode!=='cloud' && await brain.current?.plan(command,mode,followUp && run?run:undefined)){setCommand('');return;}
        setRoutingStatus(`LLM required: ${decision.reason}`);
        if (routingMode === "local") throw new Error("LOCAL_ROUTING_REQUIRED");
        if (!available.includes(provider)) throw new Error("PROVIDER_REQUIRED");
        if (localDialogue) { setRoutingStatus('This answer does not complete the local draft. Cancel it and submit a complete command for cloud reasoning.'); return; }
        next = followUp && run ? (await operatorApi.revise(run, command, requestKey, mode)).data : (await operatorApi.command({ ...data, request_key: requestKey })).data;
      }
      setRun(next); setHistory(h => [next, ...h.filter(r => r.id !== next.id)]); setFollowUp(false); setLocalDialogue(null); setLocalSetup(null);
    } catch (e) { setError(errorText(e)); } finally { busyRef.current = false; setBusy(false); }
  }
  function startVoice() {
    const ctor = (window as SpeechWindow).SpeechRecognition || (window as SpeechWindow).webkitSpeechRecognition;
    if (!ctor) return;
    const rec = new ctor(); rec.lang = language; rec.continuous = false; rec.interimResults = false;
    rec.onresult = e => {
      const text = Array.from(e.results).filter(r => r.isFinal).map(r => r[0].transcript).join(" ");
      if (text) { setCommand(previous => `${previous} ${text}`.trim()); setMode("voice"); }
    };
    rec.onerror = e => { setError(`Voice input: ${e.error}. You can type the command instead.`); setRecording(false); };
    rec.onend = () => { setRecording(false); recognition.current = null; };
    recognition.current = rec;
    try { rec.start(); setRecording(true); setError(""); } catch { setError("Microphone could not start. Check browser permission."); }
  }
  return <div className="max-w-6xl space-y-5">
    <Link className="inline-flex items-center gap-2 rounded-lg border bg-card px-4 py-2 text-sm font-medium text-primary" to={`/pms/assistant${projectId?`?project=${projectId}`:''}`}>Open the assistant workspace → Plans, memory, agents and insights</Link>
    <header><h1 className="page-title">AI task operator</h1><p className="page-description">Give a multi-step command by voice or text. Review the exact plan before applying it.</p><Link className="text-primary underline" to={`/pms/settings/ai/openai${project?.workspace_id ? `?workspace=${project.workspace_id}` : ""}`}>Provider settings and API usage</Link></header>
    <LocalBrainPanel key={uid} ref={brain} projectId={projectId} workspaceId={project?.workspace_id} provider={provider}
      cloudEnabled={available.includes(provider)} allowCloud={routingMode!=='local'} executionMode={executionMode} selected={selection}
      onRun={next=>{setRun(next);setHistory(h=>[next,...h.filter(r=>r.id!==next.id)]);setFollowUp(false);setLocalDialogue(null);}}
      onSetup={next=>{setLocalSetup(next);setLocalDialogue(null);}} />
    {error && <p role="alert" className="text-destructive">{error}</p>}
    <fieldset disabled={busy || recording || followUp || !!localDialogue} className="flex flex-wrap gap-4">
      <label>Project<select aria-label="Operator project" className="ml-2 rounded border bg-background p-2" value={projectId} onChange={e => { setProjectId(Number(e.target.value)); requestRef.current = null; }}><option value={0}>Choose project</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      <label>Model provider<select aria-label="Operator provider" className="ml-2 rounded border bg-background p-2" value={provider} onChange={e => setProvider(e.target.value as OperatorProviderName)}>{([['openai','OpenAI / ChatGPT'],['gemini','Google Gemini'],['claude','Anthropic Claude']] as const).map(([p,l]) => <option key={p} value={p} disabled={!available.includes(p)}>{l}{available.includes(p) ? "" : " · not enabled"}</option>)}</select></label>
      <label>Execution<select aria-label="Execution mode" className="ml-2 rounded border bg-background p-2" value={executionMode} onChange={e => setExecutionMode(e.target.value as "atomic" | "checkpointed")}><option value="atomic">All-or-nothing</option><option value="checkpointed">Checkpointed · keep completed steps</option></select></label>
    </fieldset>
    <section className="rounded-lg border p-4 space-y-3"><h2 className="font-semibold">Select tasks · {selection.length} / 25</h2><p className="text-sm text-muted-foreground">Supported actions: assignment, status, priority, checklists, sprints, dates and dependency links. Follow-ups retain the original task selection. Date interpretation uses {timezone}.</p>
      <div className="max-h-64 overflow-auto space-y-2">{tasks.map(t => <label key={t.id} className="flex items-center gap-3"><input aria-label={`Select ${t.task_key}`} type="checkbox" disabled={busy || recording || followUp || !!localDialogue || (!selection.includes(t.id) && selection.length >= 25)} checked={selection.includes(t.id)} onChange={e => setSelection(s => e.target.checked ? [...s, t.id] : s.filter(id => id !== t.id))} /><Link className="text-primary" to={`/pms/tasks/${t.id}`}>{t.task_key}</Link><span>{t.title}</span><span className="text-xs text-muted-foreground">{t.status}</span></label>)}</div>
    </section>
    <section className="space-y-3"><label className="block font-semibold" htmlFor="operator-command">Command</label><textarea id="operator-command" className="min-h-28 w-full rounded border bg-background p-3" disabled={busy || recording} value={command} onChange={e => { setCommand(e.target.value); if (!e.target.value) setMode("text"); }} placeholder="Set these tasks to High priority, assign them to a collaborator's email, add a QA checklist item, and move them to Sprint 4." />
      {followUp && <div role="status">Revising run #{run?.id}. The old pending approval will be invalidated. Review the new plan before execution. <Button variant="outline" onClick={() => { setFollowUp(false); requestRef.current = null; }}>Cancel reply</Button></div>}
      <label>Command routing<select aria-label="Command routing" className="ml-2 rounded border bg-background p-2" disabled={busy || followUp || !!localDialogue} value={routingMode} onChange={e => setRoutingMode(e.target.value as typeof routingMode)}><option value="auto">Local first · cloud when needed</option><option value="local">Local only · no cloud calls</option><option value="cloud">Always use selected cloud LLM</option></select></label>
      {routingStatus && <p aria-live="polite" className="text-sm">{routingStatus}</p>}
      <p className="text-sm text-muted-foreground">Local commands: “set priority to high”, “mark tasks done”, “set due date to 2026-11-05”, or “add checklist item &quot;QA review&quot;”. Join up to three actions with “and then”. Sprint numbers are record IDs. Missing details and supported follow-up revisions stay local. Every plan requires review.</p>
      <div className="flex flex-wrap items-center gap-3"><Button disabled={busy || recording || !command.trim() || (routingMode === "cloud" && !available.includes(provider))} onClick={() => void preview()}>{busy ? "Working…" : followUp ? "Preview revised plan" : "Preview plan"}</Button>
        <Button variant="outline" disabled={busy || !voiceSupported} onClick={() => recording ? recognition.current?.stop() : startVoice()}>{recording ? "Stop recording" : "Dictate command"}</Button>
        <label>Voice language<InputLanguage value={language} disabled={busy || recording} onChange={setLanguage} /></label>
      </div><p className="text-sm text-muted-foreground">{voiceSupported ? "Browser speech recognition may use your browser's speech service. Recording starts only when you choose Dictate. Review and edit the transcript before submitting." : "Speech recognition is unavailable in this browser. Text commands remain available."}</p>
    </section>
    {localDialogue && <section aria-label="Local assistant question" className="rounded-lg border p-4 space-y-2"><p className="font-semibold">{localDialogue.question}</p>
      <p className="text-sm">Original request: {localDialogue.state.original}</p>
      {localDialogue.state.choices?.map((choice,i) => <Button key={choice.value} variant="outline" disabled={busy} onClick={() => setCommand(String(i+1))}>{i+1}. {choice.label}</Button>)}
      <p className="text-sm">Type or dictate your answer in Command, then choose Preview plan.</p>
      <Button variant="outline" disabled={busy} onClick={() => { setLocalDialogue(null); setCommand(''); setRoutingStatus('Local draft discarded.'); }}>Cancel local draft</Button>
    </section>}
    {localSetup && <section aria-label="Local creation preview" className="rounded-lg border p-4 space-y-3"><h2 className="font-semibold">{localSetup.payload.plan.summary} · {localSetup.status}</h2>
      <p>Project: {localSetup.payload.plan.name} · key {localSetup.payload.plan.project_key}</p>
      {localSetup.payload.plan.milestones?.map((m: any) => <p key={m.key}>Milestone: {m.name} · due {m.due_date || "unscheduled"}</p>)}
      {localSetup.payload.plan.tasks.map((t: any) => <div key={t.key}><strong>{t.key}: {t.title}</strong><p>Parent task: {t.existing_parent_task_id || t.parent_key || 'none'} · Due: {t.due_date || 'unscheduled'} · Assignees: {t.assignee_user_ids?.join(', ') || 'none'}</p></div>)}
      {localSetup.status === 'awaiting_approval' && <Button disabled={busy} onClick={async () => { if (busyRef.current) return; busyRef.current=true; setBusy(true); try { setLocalSetup((await api.post(`/ai-operator/proposals/${localSetup.id}/approve`, { plan_hash: localSetup.plan_hash })).data); } catch(e) { setError(errorText(e)); } finally { busyRef.current=false; setBusy(false); } }}>Approve and create this work</Button>}
      {localSetup.result && <p>Created work in project #{localSetup.result.project_id} · {localSetup.result.receipts.length} receipts.</p>}
      <Button variant="outline" disabled={busy} onClick={() => { setLocalSetup(null); setCommand(''); }}>Close creation preview</Button>
    </section>}
    {run && <section className="rounded-lg border p-5 space-y-3" aria-label="Operator plan"><div className="flex justify-between"><h2 className="font-semibold">Run #{run.id} · {run.status}</h2><Button variant="outline" disabled={busy} onClick={() => void act(() => operatorApi.run(run.id))}>Refresh status</Button></div><p className="text-sm">Command: {run.command}</p><p>Frozen task selection: {run.selection.join(", ")} · revision {run.revision || 1} · {run.execution_mode || "atomic"}</p>
      {["queued_planning", "planning", "queued", "executing", "retrying"].includes(run.status) && <p role="status">Background work is in progress. You may leave this page and return to Recent commands. A running worker is required.</p>}
      {run.plan && <><p>{run.plan.summary}</p>{run.plan.clarification && <p role="status">{run.plan.clarification} Reply with a follow-up to resolve this.</p>}<ol className="list-decimal pl-5 space-y-2">{run.plan.steps.map((s, i) => <li key={i}><strong>{s.tool}</strong> · task #{s.task_id}{s.changes && <pre className="whitespace-pre-wrap text-sm">{JSON.stringify(s.changes, null, 2)}</pre>}{s.title && <span> · {s.title}</span>}{s.body && <p className="whitespace-pre-wrap">Internal comment: {s.body}</p>}{s.item_id && <span> · checklist item #{s.item_id}{s.is_completed === undefined ? " · remove" : s.is_completed ? " · complete" : " · reopen"}</span>}{s.sprint_id && <span> · sprint #{s.sprint_id}</span>}{(s.start_date || s.due_date) && <span> · {s.start_date || "unchanged"} → {s.due_date || "unchanged"}</span>}{s.source_task_id && <span> · blocked by task #{s.source_task_id}</span>}{s.depends_on && <span> · after steps {s.depends_on.join(", ") || "none"}</span>}</li>)}</ol></>}
      {run.error_code && <p role="alert" className="text-destructive">{run.error_code}. {run.result?.message || "Review the progress and correct the command or settings."}</p>}
      {run.status === "awaiting_approval" && <><p className="text-sm text-muted-foreground">Existing automation and recurrence rules apply. {run.execution_mode === "checkpointed" ? "Each step commits separately. Cancellation or a later failure preserves completed effects." : "All task changes commit together or roll back."}</p><Button disabled={busy} onClick={() => void act(() => operatorApi.approve(run))}>Approve and execute this plan</Button></>}
      {["awaiting_approval", "needs_clarification", "planning", "queued_planning", "queued", "executing", "retrying", "paused"].includes(run.status) && <Button className="ml-3" variant="outline" disabled={busy} onClick={() => void act(() => operatorApi.cancel(run.id))}>Cancel plan</Button>}
      {run.status === "paused" && <Button className="ml-3" disabled={busy} onClick={() => void act(() => operatorApi.resume(run))}>Resume remaining steps</Button>}
      {run.result?.receipts && <div role="status"><p>{run.status === "succeeded" ? "All " : "Completed "}{run.result.receipts.length} steps committed.</p>{run.result.receipts.map(r => <p key={r.step}>Step {r.step}: {r.tool} · task #{r.task_id} · record #{r.record_id}</p>)}</div>}
      {["awaiting_approval", "needs_clarification", "paused", "succeeded", "failed", "cancelled"].includes(run.status) && <Button variant="outline" disabled={busy} onClick={() => { setFollowUp(true); setCommand(""); setSelection(run.selection); requestRef.current = null; document.getElementById("operator-command")?.focus(); }}>Reply / revise plan</Button>}
      {!!eventLog.length && <details><summary>Execution events · {eventLog.length}</summary>{eventLog.map(e => <p className="text-sm" key={e.id}>{new Date(e.created_at).toLocaleTimeString()} · {e.type}{e.payload.step ? ` · step ${e.payload.step}` : ""}{e.payload.error_code ? ` · ${e.payload.error_code}` : ""}</p>)}</details>}
      {run.status === "succeeded" && <Button variant="outline" onClick={() => { requestRef.current = null; setCommand(""); setMode("text"); setRun(null); }}>Start another command</Button>}
      {["failed", "cancelled", "needs_clarification"].includes(run.status) && <Button variant="outline" disabled={busy} onClick={() => { requestRef.current = null; void preview(); }}>Create a fresh preview</Button>}
    </section>}
    <OperatorWorkspaceTools key={projectId} projectId={projectId} workspaceId={project?.workspace_id} command={command} provider={provider} />
    <section><h2 className="font-semibold mb-2">Recent commands</h2>{history.map(h => <button key={h.id} className="block w-full border-b py-3 text-left" disabled={busy} onClick={() => { setRun(h); setFollowUp(false); }}>#{h.id} · {h.status} · {h.command}</button>)}</section>
  </div>;
}

function InputLanguage({ value, disabled, onChange }: { value: string; disabled: boolean; onChange: (value: string) => void }) {
  return <select aria-label="Voice language" className="ml-2 rounded border bg-background p-2" value={value} disabled={disabled} onChange={e => onChange(e.target.value)}><option value="en-IN">English (India)</option><option value="en-US">English (US)</option><option value="hi-IN">Hindi</option><option value="te-IN">Telugu</option></select>;
}

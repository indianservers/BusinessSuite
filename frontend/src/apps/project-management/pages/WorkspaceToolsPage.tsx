import { RichTextField, RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { api } from "@/services/api";
import { beginProgress } from "@/lib/async-progress";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Root as Tabs, List as TabsList, Trigger as TabsTrigger, Content as TabsContent } from "@radix-ui/react-tabs";
import { workspaceError, taskBucket, type WorkspaceProject, type WorkTask } from "./workspaceTypes";
import { usePMSRealtime } from "../realtime";
import TemplateLibrary from "../components/TemplateLibrary";
import WorkflowFeedPanel from "../components/WorkflowFeedPanel";
import BlueprintEditor, { type BlueprintDraft } from "../components/BlueprintEditor";
import { blueprintDescription, type Blueprint } from "../data/blueprints";

type Workspace = { id: number; name: string; role: string };
type Kind = "goal" | "template" | "intake";
type Tool = { id: number; kind: Kind; name: string; project_id: number; description: string; task_ids: number[]; task_titles: string[]; enabled: boolean; progress?: number; total?: number; completed?: number };
const base = "/project-management";
const initial = { name: "", project_id: "", description: "", task_ids: [] as number[], titles: "" };
const labels = { goal: "Goals", template: "Blueprints", intake: "Intake forms" };

export default function WorkspaceToolsPage() {
  const [params] = useSearchParams();
  const { pathname } = useLocation();
  const [tab, setTab] = useState("overview");
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selected, setSelected] = useState(0);
  const selectedRef = useRef(selected); selectedRef.current = selected;
  const [tools, setTools] = useState<Tool[]>([]);
  const [projects, setProjects] = useState<WorkspaceProject[]>([]);
  const [tasks, setTasks] = useState<WorkTask[]>([]);
  const [templateFormOpen, setTemplateFormOpen] = useState(false);
  const [draft, setDraft] = useState(initial);
  const [loading, setLoading] = useState(true);
  const [workspaceLoading, setWorkspaceLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [created, setCreated] = useState<number[]>([]);
  const [applying, setApplying] = useState<Tool | null>(null);
  const [editingBlueprint, setEditingBlueprint] = useState<{ initial: BlueprintDraft; tool?: Tool; requestId: string } | null>(null);
  const [request, setRequest] = useState({ request_id: "", title: "", description: "" });
  const workspace = workspaces.find(w => w.id === selected);
  const manages = !!workspace && ["Owner", "Admin"].includes(workspace.role);
  const canEdit = !!workspace && workspace.role !== "Guest";
  const control = "mt-1 w-full min-h-11 rounded border bg-background px-3 py-2";

  useEffect(() => { setTab(pathname.endsWith("/goals") ? "goal" : pathname.endsWith("/templates") || pathname.endsWith("/blueprints") ? "template" : pathname.endsWith("/forms") ? "intake" : "overview"); }, [pathname]);
  const loadWorkspaces = useCallback(async () => {
    const { data } = await api.get<Workspace[]>(base + "/workspaces");
    setWorkspaces(data); setSelected(current => data.some(w => w.id === current) ? current : data.some(w => w.id === Number(params.get("workspace"))) ? Number(params.get("workspace")) : data[0]?.id || 0);
  }, [params]);
  useEffect(() => { setWorkspaceLoading(true); void loadWorkspaces().catch(e => setError(workspaceError(e))).finally(() => setWorkspaceLoading(false)); }, [loadWorkspaces]);
  const load = useCallback(async () => {
    if (!selected) return;
    const [library, overview] = await Promise.all([api.get<Tool[]>(`${base}/workspaces/${selected}/tools`), api.get<{ projects: WorkspaceProject[]; tasks: WorkTask[] }>(`${base}/workspaces/${selected}/overview`)]);
    return { tools: library.data, ...overview.data };
  }, [selected]);
  const applyData = (data: Awaited<ReturnType<typeof load>>) => { if (data) { setTools(data.tools); setProjects(data.projects); setTasks(data.tasks); } };
  const refresh = () => { const current = selected; void load().then(data => { if (selectedRef.current === current) applyData(data); }).catch(() => undefined); };
  usePMSRealtime({ onEvent: event => { if (/^(task\.|project\.)/.test(event.type)) refresh(); }, onFallbackPoll: refresh, showToast: false });
  useEffect(() => {
    let active = true; setLoading(true); setTools([]); setProjects([]); setTasks([]); setDraft(initial); setTemplateFormOpen(false); setApplying(null); setEditingBlueprint(null); setCreated([]); setNotice("");
    void load().then(data => { if (active) applyData(data); }).catch(e => { if (active) setError(workspaceError(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [load]);
  async function act(label: string, action: () => Promise<void>) {
    if (busy) return; setBusy(true); setError(""); setNotice(""); const finish = beginProgress(label);
    try { await action(); applyData(await load()); finish(); } catch (e) { finish(false); setError(workspaceError(e)); } finally { setBusy(false); }
  }
  function start(tool: Tool) { setError(""); setRequest({ request_id: crypto.randomUUID(), title: "", description: "" }); setApplying(tool); }
  function customizeBlueprint(blueprint: Blueprint) {
    setError("");
    setEditingBlueprint({ initial: { name: blueprint.name, project_id: projects.length === 1 ? projects[0].id : 0, description: blueprintDescription(blueprint), task_titles: blueprint.task_titles }, requestId: crypto.randomUUID() });
  }
  function customizeSaved(tool: Tool) {
    setError("");
    setEditingBlueprint({ initial: { name: tool.name, project_id: tool.project_id, description: tool.description, task_titles: tool.task_titles }, tool, requestId: crypto.randomUUID() });
  }
  function saveBlueprint(draft: BlueprintDraft) {
    if (!editingBlueprint) return;
    const tool = editingBlueprint.tool;
    void act("Saving blueprint", async () => {
      if (tool) await api.patch(`${base}/workspaces/${selected}/tools/${tool.id}`, { name: draft.name, description: draft.description, task_titles: draft.task_titles });
      else await api.post(`${base}/workspaces/${selected}/tools`, { ...draft, kind: "template" });
      setEditingBlueprint(null);
      setNotice(tool ? "Workspace blueprint updated. Existing tasks are unchanged." : "Blueprint saved. Find it in Workspace blueprints; no tasks have been created yet.");
    });
  }
  function useBlueprint(draft: BlueprintDraft) {
    if (!editingBlueprint) return;
    const { tool, requestId } = editingBlueprint;
    void act("Creating blueprint tasks", async () => {
      const { data } = await api.post<{ task_ids: number[] }>(tool ? `${base}/workspaces/${selected}/tools/${tool.id}/apply` : `${base}/workspaces/${selected}/blueprints/apply`, tool
        ? { request_id: requestId, description: draft.description, task_titles: draft.task_titles }
        : { ...draft, request_id: requestId });
      setCreated(data.task_ids);
      setEditingBlueprint(null);
      setNotice(`${data.task_ids.length} tasks created. Open your workspace to assign owners, dates, and dependencies.`);
    });
  }

  return <div className="max-w-6xl space-y-5">
    <header className="flex flex-wrap justify-between gap-3"><div><h1 className="page-title">{tab === "template" ? "Blueprints" : "Workspace tools"}</h1><p className="page-description">Goals track actual task completion. Templates and authenticated intake forms create tasks in your workspace.</p></div><Link className="text-primary underline" to={`/pms/workspaces?workspace=${selected}`}>Back to workspace</Link></header>
    <label className="block max-w-md">Workspace<select className={control} aria-label="Tools workspace" disabled={busy} value={selected} onChange={e => { setError(""); setSelected(Number(e.target.value)); }}><option value={0} disabled>Choose workspace</option>{workspaces.map(w => <option key={w.id} value={w.id}>{w.name} · {w.role}</option>)}</select></label>
    {error && <div role="alert" className="rounded border border-destructive p-3 text-destructive">{error}<Button variant="outline" disabled={busy} onClick={() => void act("Refreshing workspace tools", async () => { if (!workspaces.length) await loadWorkspaces(); })}>Retry</Button></div>}
    {notice && <p role="status">{notice}</p>}
    {!!created.length && <div className="flex flex-wrap gap-3" aria-label="Created tasks">{created.map(id => <Link className="text-primary underline" key={id} to={`/pms/workspaces?workspace=${selected}&task=${id}`}>Open created task #{id}</Link>)}</div>}
    {workspaceLoading || loading ? <p role="status">Loading workspace tools…</p> : !workspace ? <p>Create or join a workspace first.</p> : <Tabs value={tab} onValueChange={value => { setTab(value); setDraft(initial); setError(""); }}>
      <TabsList className="flex h-auto flex-wrap justify-start">{[["overview", "Overview"], ["goal", "Goals"], ["template", "Blueprints"], ["intake", "Intake forms"]].map(([value, label]) => <TabsTrigger disabled={busy} className="min-h-11 rounded px-4 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground" key={value} value={value}>{label}</TabsTrigger>)}</TabsList>
      <TabsContent value="overview" className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">{[["Projects", projects.length], ["Open tasks", tasks.filter(t => taskBucket(t.status) !== "Done").length], ["Completed tasks", tasks.filter(t => taskBucket(t.status) === "Done").length]].map(([label, count]) => <div className="rounded border p-5" key={label}><strong className="text-2xl">{count}</strong><p>{label}</p></div>)}</div>
        <div className="flex flex-wrap gap-4"><Link className="text-primary underline" to="/pms/backlog">Backlog and sprints</Link><Link className="text-primary underline" to="/pms/workload">Workload</Link><Link className="text-primary underline" to="/pms/portfolio">Portfolio</Link>{manages && <Link className="text-primary underline" to={`/pms/automation?workspace=${selected}`}>Task automation</Link>}</div>
        <h2 className="text-lg font-semibold">Project planning and reports</h2>{projects.map(project => <article key={project.id} className="flex flex-wrap justify-between gap-3 rounded border p-4"><strong>{project.name}</strong><div className="flex flex-wrap gap-4">{[["board", "Board"], ["gantt", "Gantt and dependencies"], ["reports", "Reports"]].map(([path, label]) => <Link className="text-primary underline" key={path} to={`/pms/projects/${project.id}/${path}`}>{label}</Link>)}</div></article>)}
        {manages && <WorkflowFeedPanel key={selected} workspaceId={selected} />}
        <p className="text-sm text-muted-foreground">Custom workflow builders, marketplace connections, and enterprise identity provisioning require separate integrations. This page shows saved workspace data.</p>
      </TabsContent>
      {(["goal", "template", "intake"] as Kind[]).map(kind => <TabsContent key={kind} value={kind} className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-lg font-semibold">{labels[kind]}</h2><Button variant="outline" disabled={busy} onClick={() => void act("Refreshing tools", async () => undefined)}>Refresh {labels[kind].toLowerCase()}</Button></div>
        {kind === "template" && manages && <Button variant="outline" aria-expanded={templateFormOpen} onClick={() => setTemplateFormOpen(open => !open)}>{templateFormOpen ? "Close blank blueprint editor" : "Create blank blueprint"}</Button>}
        {manages ? (kind !== "template" || templateFormOpen) && <form className="space-y-4 rounded border p-4" onSubmit={e => { e.preventDefault(); void act(`Saving ${kind}`, async () => { await api.post(`${base}/workspaces/${selected}/tools`, { kind, name: draft.name, project_id: Number(draft.project_id), description: draft.description, task_ids: kind === "goal" ? draft.task_ids : [], task_titles: kind === "template" ? draft.titles.split("\n").filter(t => t.trim()) : [] }); setDraft(initial); setNotice("Saved to this workspace"); }); }}>
          <h3 className="font-semibold">Create {kind === "intake" ? "an intake form" : `a ${kind}`}</h3><fieldset disabled={busy} className="grid gap-4 sm:grid-cols-2"><label>Name<Input required maxLength={120} aria-label="Tool name" value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} /></label><label>Project<select required className={control} aria-label="Tool project" value={draft.project_id} onChange={e => setDraft({ ...draft, project_id: e.target.value, task_ids: [] })}><option value="" disabled>Choose project</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label><label className="sm:col-span-2">{kind === "intake" ? "Instructions for requesters" : "Description"}<RichTextField data-legacy-format="markdown" maxLength={4000} className={control} aria-label="Tool description" value={draft.description} onChange={e => setDraft({ ...draft, description: e.target.value })} /></label>
          {kind === "template" && <label className="sm:col-span-2">Task titles, one per line (up to 20)<textarea required rows={5} aria-label="Template task titles" className={control} value={draft.titles} onChange={e => setDraft({ ...draft, titles: e.target.value })} /></label>}
          {kind === "goal" && <fieldset className="sm:col-span-2 max-h-64 overflow-y-auto rounded border p-3"><legend>Contributing tasks · {draft.task_ids.length} selected</legend>{!draft.project_id && <p>Choose a project first.</p>}{tasks.filter(t => t.project_id === Number(draft.project_id)).map(task => <label key={task.id} className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={draft.task_ids.includes(task.id)} onChange={e => setDraft({ ...draft, task_ids: e.target.checked ? [...draft.task_ids, task.id] : draft.task_ids.filter(id => id !== task.id) })} />{task.title}</label>)}</fieldset>}
          </fieldset><Button disabled={busy || !projects.length || (kind === "goal" && !draft.task_ids.length)}>Save {kind === "intake" ? "form" : kind}</Button>
        </form> : <p className="text-sm text-muted-foreground">Owners and admins create tools. {canEdit ? "Members can use templates and submit intake requests." : "Guests can view saved tools and goal progress."}</p>}
        {kind === "template" && <TemplateLibrary key={selected} templates={tools.filter(tool => tool.kind === "template")} projects={projects} canEdit={canEdit} busy={busy} onPreview={customizeSaved} onSelectBlueprint={customizeBlueprint} />}
        {kind !== "template" && !tools.some(t => t.kind === kind) && <p>No saved {labels[kind].toLowerCase()} yet.</p>}
        <details open={kind !== "template"} className="space-y-3"><summary className={kind === "template" && manages ? "cursor-pointer text-sm font-medium" : "hidden"}>Manage workspace blueprints</summary>{tools.filter(tool => tool.kind === kind && (kind !== "template" || manages)).map(tool => <article key={tool.id} className="space-y-3 rounded border p-4"><div className="flex flex-wrap justify-between gap-3"><div><h3 className="font-semibold">{tool.name}</h3><p className="text-sm text-muted-foreground">{projects.find(p => p.id === tool.project_id)?.name} · {tool.enabled ? "Active" : "Paused"}</p></div>{manages && <Button variant="outline" disabled={busy} onClick={() => void act("Updating tool", async () => { await api.patch(`${base}/workspaces/${selected}/tools/${tool.id}`, { enabled: !tool.enabled }); setNotice(tool.enabled ? "Tool paused" : "Tool enabled"); })}>{tool.enabled ? "Pause" : "Enable"} {tool.name}</Button>}</div><div className="whitespace-pre-wrap break-words"><RichTextContent value={tool.description}/></div>
          {kind === "goal" ? <><progress aria-label={`${tool.name} completion`} className="h-3 w-full accent-violet-600" value={tool.progress} max={100} /><p>{tool.progress}% complete · {tool.completed} of {tool.total} tasks done</p><div className="flex flex-wrap gap-3">{tool.task_ids.map(id => <Link className="text-primary underline" key={id} to={`/pms/workspaces?workspace=${selected}&task=${id}`}>{tasks.find(t => t.id === id)?.title || `Task #${id}`}</Link>)}</div></> : <>{canEdit && kind !== "template" && <Button disabled={busy || !tool.enabled} onClick={() => start(tool)}>Submit request</Button>}</>}
        </article>)}</details>
      </TabsContent>)}
    </Tabs>}
    <Dialog.Root open={!!applying} onOpenChange={open => { if (!open && !busy) setApplying(null); }}><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" /><Dialog.Content onEscapeKeyDown={e => { if (busy) e.preventDefault(); }} onInteractOutside={e => e.preventDefault()} className="fixed left-1/2 top-1/2 z-50 max-h-[90dvh] w-[calc(100%_-_2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-lg border bg-background p-5 shadow-xl"><Dialog.Title className="text-lg font-semibold">{applying?.name}</Dialog.Title><Dialog.Description>{applying?.kind === "template" ? `Create ${applying.task_titles.length} tasks in ${projects.find(p => p.id === applying.project_id)?.name}.` : applying?.description || "Submit a request as a task in this project."}</Dialog.Description>
      {error && <p className="text-destructive" role="alert">{error}</p>}<form className="mt-4 space-y-4" onSubmit={e => { e.preventDefault(); if (!applying) return; void act("Creating tasks", async () => { const { data } = await api.post<{ task_ids: number[] }>(`${base}/workspaces/${selected}/tools/${applying.id}/apply`, request); setCreated(data.task_ids); setNotice(`${data.task_ids.length} task${data.task_ids.length === 1 ? "" : "s"} created`); setApplying(null); }); }}><fieldset disabled={busy} className="space-y-4">{applying?.kind === "intake" ? <><label className="block">Request title<Input required maxLength={220} aria-label="Request title" value={request.title} onChange={e => setRequest({ ...request, title: e.target.value })} /></label><label className="block">Details<RichTextField data-legacy-format="markdown" className={control} aria-label="Request details" maxLength={10000} value={request.description} onChange={e => setRequest({ ...request, description: e.target.value })} /></label></> : <ul className="list-disc pl-5">{applying?.task_titles.map((title, index) => <li key={index}>{title}</li>)}</ul>}</fieldset><div className="flex justify-end gap-3"><Button type="button" variant="outline" disabled={busy} onClick={() => setApplying(null)}>Cancel</Button><Button disabled={busy}>{busy ? "Creating…" : applying?.kind === "intake" ? "Create request task" : "Create template tasks"}</Button></div></form>
    </Dialog.Content></Dialog.Portal></Dialog.Root>
    {editingBlueprint && <BlueprintEditor key={editingBlueprint.requestId} initial={editingBlueprint.initial} saved={!!editingBlueprint.tool} projects={projects} busy={busy} canEdit={canEdit} manages={manages} enabled={editingBlueprint.tool?.enabled ?? true} error={error} onClose={() => { setEditingBlueprint(null); setError(""); }} onUse={useBlueprint} onSave={saveBlueprint} />}
  </div>;
}

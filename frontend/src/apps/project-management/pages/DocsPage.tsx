import { downloadRichDocument } from "@/components/rich-text/content";
import RichTextEditor, { RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { projectsAPI, tasksAPI } from "../services/api";
import type { PMSProject, PMSTask } from "../types";
import { workspaceError } from "./workspaceTypes";
type Doc = { id: number; title: string; content: string; task_id: number | null; project_id: number; project_name: string; version: number; updated_at: string; updated_by: string; can_edit: boolean };
type Summary = Pick<Doc, "id" | "title" | "project_id" | "project_name" | "version" | "updated_at">;
type Revision = { version: number; title: string; created_at: string; author: string };
const blank = { title: "", content: "", task_id: "" };
export default function DocsPage() {
  const [library, setLibrary] = useState<Summary[]>([]);
  const [projects, setProjects] = useState<PMSProject[]>([]);
  const [project, setProject] = useState("");
  const [tasks, setTasks] = useState<PMSTask[]>([]);
  const [doc, setDoc] = useState<Doc | null>(null);
  const [draft, setDraft] = useState(blank);
  const [search, setSearch] = useState("");
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const lock = useRef(false);
  const dirty = doc ? draft.title !== doc.title || draft.content !== doc.content || draft.task_id !== String(doc.task_id || "") : !!(draft.title || draft.content || draft.task_id);
  useEffect(() => { let active = true; Promise.all([api.get<Summary[]>("/project-management/docs"), projectsAPI.list()]).then(([docs, projects]) => { if (active) { setLibrary(docs.data); setProjects(projects); } }).catch(error => { if (active) setError(workspaceError(error)); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []);
  useEffect(() => { if (!project) { setTasks([]); return; } let active = true; setTasks([]); tasksAPI.list(Number(project)).then(tasks => { if (active) setTasks(tasks); }).catch(error => { if (active) setError(workspaceError(error)); }); return () => { active = false; }; }, [project]);
  useEffect(() => { const warn = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = ""; } }; window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn); }, [dirty]);
  const apply = (data: Doc) => { setDoc(data); setProject(String(data.project_id)); setDraft({ title: data.title, content: data.content, task_id: String(data.task_id || "") }); setRevisions([]); };
  async function open(id: number) {
    if (busy || (dirty && !window.confirm("Discard your unsaved changes and open this document?"))) return;
    setBusy(true); setError(""); setNotice("");
    try { const { data } = await api.get<Doc>(`/project-management/docs/${id}`); apply(data); }
    catch (error) { setError(workspaceError(error)); } finally { setBusy(false); }
  }
  async function save() {
    if (lock.current || !project || !draft.title.trim() || (doc && !doc.can_edit)) return;
    lock.current = true; setBusy(true); setError(""); setNotice("");
    const payload = { title: draft.title, content: draft.content, task_id: draft.task_id ? Number(draft.task_id) : null };
    try {
      const { data } = doc ? await api.put<Doc>(`/project-management/docs/${doc.id}`, { ...payload, version: doc.version }) : await api.post<Doc>(`/project-management/projects/${project}/docs`, payload);
      apply(data); setLibrary(current => [data, ...current.filter(item => item.id !== data.id)]); setNotice(`Saved version ${data.version}`);
    } catch (error) { setError(workspaceError(error)); } finally { lock.current = false; setBusy(false); }
  }
  function download() { downloadRichDocument(draft.content, draft.title); }
  const editable = !doc || doc.can_edit;
  return <main className="space-y-4" onKeyDown={event => { if ((event.ctrlKey || event.metaKey) && event.key === "s") { event.preventDefault(); void save(); } }}>
    <header className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="page-title">Docs</h1><p className="page-description">Project documents with visual editing, task links and version history.</p></div><Link className="text-sm text-primary underline" to="/pms/workspaces">Workspace</Link></header>
    {error && <p role="alert" className="rounded border border-destructive p-3 text-destructive">{error}</p>}{notice && <p role="status">{notice}</p>}
    <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]"><aside className="space-y-3 rounded-lg border p-4"><Button disabled={busy} onClick={() => { if (!dirty || window.confirm("Discard unsaved changes and create a document?")) { setDoc(null); setDraft(blank); setRevisions([]); setError(""); setNotice(""); } }}>New document</Button><Input aria-label="Search documents" placeholder="Search title or project…" value={search} onChange={event => setSearch(event.target.value)} />{loading && <p role="status">Loading documents…</p>}{library.filter(item => `${item.title} ${item.project_name}`.toLowerCase().includes(search.toLowerCase())).map(item => <button key={item.id} disabled={busy} className={`w-full break-words rounded-md border p-3 text-left text-sm ${doc?.id === item.id ? "bg-muted" : ""}`} onClick={() => void open(item.id)}><strong>{item.title}</strong><span className="mt-1 block text-xs text-muted-foreground">{item.project_name} · v{item.version}</span></button>)}</aside>
      <section className="min-w-0 space-y-4 rounded-xl border bg-card p-5" aria-label="Document editor">
        <div className="flex flex-wrap items-center gap-2"><Button disabled={busy || !editable || !project || !draft.title.trim()} onClick={() => void save()}>{busy ? "Working…" : "Save document"}</Button><Button variant="outline" onClick={download}>Download formatted document</Button>{doc && <Button variant="ghost" disabled={busy} onClick={() => { setBusy(true); setError(""); void api.get<Revision[]>(`/project-management/docs/${doc.id}/revisions`).then(({ data }) => setRevisions(data)).catch(error => setError(workspaceError(error))).finally(() => setBusy(false)); }}>Version history</Button>}{doc && <Button variant="ghost" disabled={busy} onClick={() => void open(doc.id)}>Load latest</Button>}</div>
        <div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Project<select aria-label="Document project" required disabled={busy || !!doc} value={project} onChange={event => { setProject(event.target.value); setDraft(current => ({ ...current, task_id: "" })); }} className="mt-1 h-10 w-full rounded-md border bg-background px-3"><option value="" disabled>Choose project</option>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label><label className="text-sm">Linked task<select aria-label="Document linked task" disabled={busy || !editable} value={draft.task_id} onChange={event => setDraft({ ...draft, task_id: event.target.value })} className="mt-1 h-10 w-full rounded-md border bg-background px-3"><option value="">No linked task</option>{draft.task_id && !tasks.some(task => String(task.id) === draft.task_id) && <option value={draft.task_id}>Linked task #{draft.task_id} (unavailable)</option>}{tasks.map(task => <option key={task.id} value={task.id}>{task.task_key} · {task.title}</option>)}</select></label></div>
        <Input aria-label="Document title" placeholder="Document title" maxLength={180} disabled={busy || !editable} value={draft.title} className="h-12 text-xl font-semibold" onChange={event => setDraft({ ...draft, title: event.target.value })} />
        <p className="text-xs text-muted-foreground">{doc ? `Version ${doc.version} · Updated by ${doc.updated_by}` : "New document"} · {dirty ? "Unsaved changes" : "No unsaved changes"} · {richTextPlainText(draft.content) ? richTextPlainText(draft.content).split(/\s+/).length : 0} words{!editable && " · View only"}</p>
        <RichTextEditor value={draft.content} onChange={content => setDraft({ ...draft, content })} label="Document content" variant="document" maxLength={200000} readOnly={!editable} disabled={busy}/>

        {!!revisions.length && <section className="space-y-2 border-t pt-4"><h2 className="font-semibold">Version history</h2><p className="text-xs text-muted-foreground">Loading an older version puts it in your draft. Save to create a new revision; history is retained.</p>{revisions.map(revision => <div key={revision.version} className="flex flex-wrap items-center justify-between gap-2 rounded border p-3 text-sm"><span>v{revision.version} · {revision.author} · {revision.title}</span><Button size="sm" variant="outline" disabled={busy} onClick={() => {
          if (dirty && !window.confirm("Replace your unsaved draft with this revision?")) return;
          setBusy(true); setError(""); void api.get(`/project-management/docs/${doc!.id}/revisions/${revision.version}`).then(({ data }) => { setDraft({ title: data.title, content: data.content, task_id: String(data.task_id || "") }); setNotice(`Revision ${revision.version} loaded as a draft`); }).catch(error => setError(workspaceError(error))).finally(() => setBusy(false));
        }}>Load revision {revision.version}</Button></div>)}</section>}
      </section>
    </div>
  </main>;
}

import { richTextPlainText } from "@/components/rich-text/RichTextContent";
import { downloadRichDocument } from "@/components/rich-text/content";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Archive, ArrowLeft, Download, FileText, History, LockKeyhole, Pin, Plus, Search, Trash2 } from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { projectsAPI, tasksAPI } from "../services/api";
import type { PMSProject, PMSTask } from "../types";
import NoteRichEditor from "../components/NoteRichEditor";
import NoteAttachments from "../components/NoteAttachments";
import NoteTaskActions from "../components/NoteTaskActions";
import { workspaceError } from "./workspaceTypes";
import "./notes.css";

type Draft = { title: string; content: string; project_id: number | null; task_id: number | null; tags: string[]; pinned: boolean; archived: boolean };
type Note = Draft & { id: number; version: number; project_name: string; project_kind: "personal" | "project"; project_key: string; visibility: "private"; task_title: string | null; preview: string; updated_at: string; deleted_at: string | null };
type Revision = { version: number; title: string; created_at: string };
type View = "all" | "pinned" | "archive" | "trash";
const blank = (project: number | null): Draft => ({ title: "", content: "", project_id: project, task_id: null, tags: [], pinned: false, archived: false });
const draftOf = (note: Note): Draft => ({ title: note.title, content: note.content, project_id: note.project_id, task_id: note.task_id, tags: note.tags, pinned: note.pinned, archived: note.archived });
const same = (a: Draft, b: Draft) => JSON.stringify(a) === JSON.stringify(b);
const base = "/project-management/notes";

export default function NotesPage() {
  const { projectId } = useParams();
  const [params, setParams] = useSearchParams();
  const initialProject = Number(projectId || params.get("project")) || null;
  const [notes, setNotes] = useState<Note[]>([]);
  const [projects, setProjects] = useState<PMSProject[]>([]);
  const [tasks, setTasks] = useState<PMSTask[]>([]);
  const [view, setView] = useState<View>("all");
  const [search, setSearch] = useState("");
  const [tag, setTag] = useState("");
  const [projectFilter, setProjectFilter] = useState(initialProject ? String(initialProject) : "");
  const [note, setNote] = useState<Note | null>(null);
  const [draft, setDraft] = useState<Draft>(blank(initialProject));
  const [saved, setSaved] = useState<Draft>(blank(initialProject));
  const [editing, setEditing] = useState(params.has("new"));
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [revisionPreview, setRevisionPreview] = useState<{ title: string; content: string; version: number } | null>(null);
  const lock = useRef(false);
  const [editorSession, setEditorSession] = useState(0);
  const [selection, setSelection] = useState("");
  const dirty = !same(draft, saved);
  const dirtyRef = useRef(dirty); dirtyRef.current = dirty;
  const refresh = useCallback(async () => {
    const { data } = await api.get<Note[]>(base, { params: { view, q: search, project_id: projectFilter && projectFilter !== "personal" ? projectFilter : undefined, personal: projectFilter === "personal", tag } });
    setNotes(data);
  }, [view, search, projectFilter, tag]);
  useEffect(() => {
    let active = true; setLoading(true);
    const timer = setTimeout(() => { void api.get<Note[]>(base, { params: { view, q: search, project_id: projectFilter && projectFilter !== "personal" ? projectFilter : undefined, personal: projectFilter === "personal", tag } }).then(({ data }) => { if (active) setNotes(data); }).catch(e => { if (active) setError(workspaceError(e)); }).finally(() => { if (active) setLoading(false); }); }, 180);
    return () => { active = false; clearTimeout(timer); };
  }, [view, search, projectFilter, tag]);
  useEffect(() => { void projectsAPI.list().then(setProjects).catch(() => setProjects([])); }, []);
  useEffect(() => {
    let active = true; setTasks([]);
    if (draft.project_id) void tasksAPI.list(draft.project_id).then(data => { if (active) setTasks(data); }).catch(() => undefined);
    return () => { active = false; };
  }, [draft.project_id]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirtyRef.current) { event.preventDefault(); event.returnValue = ""; } };
    const guardLink = (event: MouseEvent) => {
      const link = event.target instanceof Element ? event.target.closest("a[href]") : null;
      if (!link || !dirtyRef.current || event.defaultPrevented || link.getAttribute("target") === "_blank") return;
      if (lock.current || !window.confirm("Discard the unsaved changes to this note?")) {
        event.preventDefault(); event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", warn); document.addEventListener("click", guardLink, true);
    return () => { window.removeEventListener("beforeunload", warn); document.removeEventListener("click", guardLink, true); };
  }, []);
  function apply(data: Note) { setEditorSession(v => v + 1); setSelection(""); setNote(data); setDraft(draftOf(data)); setSaved(draftOf(data)); setEditing(true); setError(""); setStatus("Saved"); setRevisions([]); setRevisionPreview(null); }
  function mayLeave() { return !lock.current && (!dirty || window.confirm("Discard the unsaved changes to this note?")); }
  async function open(id: number) {
    if (!mayLeave()) return;
    lock.current = true; setBusy(true);
    try { apply((await api.get<Note>(`${base}/${id}`)).data); }
    catch (e) { setError(workspaceError(e)); } finally { lock.current = false; setBusy(false); }
  }
  function create() {
    if (!mayLeave()) return;
    setEditorSession(v => v + 1); setSelection("");
    const empty = blank(Number(projectFilter) || null);
    setNote(null); setDraft(empty); setSaved(empty); setEditing(true); setError(""); setStatus(""); setRevisions([]); setRevisionPreview(null);
  }
  // Quick Add can navigate here again while the component remains mounted.
  useEffect(() => {
    if (params.has("new") && !lock.current && !dirtyRef.current) {
      setEditorSession(v => v + 1); setSelection("");
      const empty = blank(initialProject); setNote(null); setDraft(empty); setSaved(empty); setEditing(true);
      const next = new URLSearchParams(params); next.delete("new"); setParams(next, { replace: true });
    }
  }, [params, setParams, initialProject]);
  async function save() {
    if (lock.current || !dirty || note?.deleted_at) return;
    const snapshot = { ...draft, title: draft.title.trim() || "Untitled note" };
    lock.current = true; setBusy(true); setStatus("Saving…"); setError("");
    try {
      const { data } = note ? await api.put<Note>(`${base}/${note.id}`, { ...snapshot, version: note.version }) : await api.post<Note>(base, snapshot);
      setNote(data); setSaved(draftOf(data));
      setDraft(current => same(current, draft) ? draftOf(data) : current);
      setStatus("Saved"); await refresh();
    } catch (e) { setStatus("Save failed — your draft is kept"); setError(workspaceError(e)); }
    finally { lock.current = false; setBusy(false); }
  }
  useEffect(() => {
    if (!editing || !dirty || busy || error || note?.deleted_at) return;
    const timer = setTimeout(() => { void save(); }, 1000);
    return () => clearTimeout(timer);
  });
  async function lifecycle(action: "trash" | "restore") {
    if (!note || lock.current || dirty) return;
    lock.current = true; setBusy(true); setError("");
    try {
      const { data } = action === "trash" ? await api.delete<Note>(`${base}/${note.id}`, { data: { version: note.version } }) : await api.post<Note>(`${base}/${note.id}/restore`, { version: note.version });
      apply(data); setStatus(action === "trash" ? "Moved to trash" : "Restored"); await refresh();
    } catch (e) { setError(workspaceError(e)); } finally { lock.current = false; setBusy(false); }
  }
  function download() { downloadRichDocument(draft.content, draft.title); }
  const readOnly = !!note?.deleted_at;
  return <main className="private-notes" onKeyDown={event => { if ((event.ctrlKey || event.metaKey) && event.key === "s") { event.preventDefault(); void save(); } }}>
    <header className="notes-header"><div><p className="notes-eyebrow"><LockKeyhole size={14} /> YOUR PRIVATE SPACE</p><h1>My Notes</h1><p className="text-muted-foreground">Every note has a project. Personal by default, always private to you.</p></div><Button onClick={create} disabled={busy}><Plus size={16} />New note</Button></header>
    {error && <div role="alert" className="notes-error">{error}<Button variant="outline" disabled={busy || !dirty} onClick={() => void save()}>Retry save</Button>{note && <Button variant="outline" disabled={busy} onClick={() => void open(note.id)}>Reload latest</Button>}</div>}
    <div className={`notes-layout ${editing ? "notes-editor-open" : ""}`}>
      <nav className="notes-nav" aria-label="Note collections">
        {([["all", "All Notes", FileText], ["pinned", "Pinned", Pin], ["archive", "Archive", Archive], ["trash", "Trash", Trash2]] as const).map(([value, label, Icon]) => <button key={value} aria-pressed={view === value} onClick={() => setView(value)}><Icon size={16} />{label}</button>)}
        <label>Project<select aria-label="Filter notes by project" value={projectFilter} onChange={e => setProjectFilter(e.target.value)}><option value="">All projects</option><option value="personal">Personal (only you)</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
        <label>Tag<Input aria-label="Filter notes by tag" placeholder="e.g. ideas" value={tag} onChange={e => setTag(e.target.value)} /></label>
        <p className="notes-privacy"><LockKeyhole size={16} />Personal is your default project. Work project notes stay private to you.</p>
        {initialProject && <Link to={`/pms/projects/${initialProject}`}>Back to project</Link>}
      </nav>
      <section className="notes-list" aria-label="Note list">
        <div className="notes-search"><Search size={16} /><Input aria-label="Search notes" placeholder="Search your notes…" value={search} onChange={e => setSearch(e.target.value)} /></div>
        <p className="notes-count">{loading ? "Loading notes…" : `${notes.length} ${notes.length === 1 ? "note" : "notes"}`}</p>
        {!loading && notes.length === 0 && <div className="notes-empty-list"><FileText size={24} /><p>{search || tag || projectFilter ? "No notes match these filters." : view === "all" ? "A little space for your next idea." : `No notes in ${view === "pinned" ? "Pinned" : view === "archive" ? "Archive" : "Trash"}.`}</p></div>}
        {notes.map(item => <button key={item.id} disabled={busy} className={`notes-list-item ${note?.id === item.id ? "selected" : ""}`} onClick={() => void open(item.id)}><strong>{item.pinned && <Pin size={12} />}{item.title}</strong><p>{item.preview || "Empty note"}</p><small>Project: {item.project_name} · Private · {new Date(item.updated_at).toLocaleDateString()}</small>{item.tags.length > 0 && <span className="notes-tag-summary">{item.tags.map(t => `#${t}`).join(" ")}</span>}</button>)}
      </section>
      <section className="notes-editor" aria-label="Private note editor">
        {!editing ? <div className="notes-welcome"><div className="notes-welcome-icon"><FileText size={32} /></div><h2>A place to think clearly</h2><p>Capture a quick thought or start a longer story.<br />Every note belongs to Personal or a work project.</p><Button onClick={create}><Plus size={16} />Write your first note</Button><span><LockKeyhole size={13} />Private · Only you</span></div> : <>
          <div className="notes-editor-top"><Button className="notes-back" variant="ghost" onClick={() => { if (mayLeave()) setEditing(false); }}><ArrowLeft size={16} />Notes</Button><span className="notes-private-badge"><LockKeyhole size={13} />Private · Only you</span><span role="status" className="notes-save-state">{busy ? "Working…" : dirty ? status.startsWith("Save failed") ? status : "Unsaved changes" : status || "New note"}</span></div>
          <div className="notes-actions"><Button size="sm" disabled={busy || readOnly || !dirty} onClick={() => void save()}>Save note</Button><Button size="sm" variant="ghost" onClick={download} aria-label="Export formatted document"><Download size={16} /></Button>{!readOnly && <><Button size="sm" variant="ghost" aria-label="Pin note" aria-pressed={draft.pinned} onClick={() => setDraft(d => ({ ...d, pinned: !d.pinned }))}><Pin size={16} /></Button><Button size="sm" variant="ghost" aria-label={draft.archived ? "Unarchive note" : "Archive note"} onClick={() => setDraft(d => ({ ...d, archived: !d.archived }))}><Archive size={16} /></Button></>}{note && <><Button size="sm" variant="ghost" aria-label="Version history" disabled={busy} onClick={() => { void api.get<Revision[]>(`${base}/${note.id}/revisions`).then(({ data }) => setRevisions(data)).catch(e => setError(workspaceError(e))); }}><History size={16} /></Button><Button size="sm" variant="ghost" disabled={busy || dirty} onClick={() => void lifecycle(readOnly ? "restore" : "trash")}>{readOnly ? "Restore note" : <><Trash2 size={16} />Trash</>}</Button></>}</div>
          {readOnly && <p className="notes-trash-message">This note is in Trash. Restore it to continue writing.</p>}
          <Input className="notes-title" aria-label="Note title" placeholder="Untitled note" maxLength={180} value={draft.title} disabled={readOnly} onChange={e => setDraft(d => ({ ...d, title: e.target.value }))} />
          <p className="notes-project-context"><FileText size={14} />Project: <strong>{draft.project_id ? projects.find(p => p.id === draft.project_id)?.name || note?.project_name || "Selected project" : "Personal"}</strong><span>Private · Only you</span></p><details className="notes-note-details"><summary>Project, task link &amp; tags</summary><div className="notes-metadata"><label>Project (required)<select aria-label="Note project" required disabled={readOnly} value={draft.project_id || "personal"} onChange={e => setDraft(d => ({ ...d, project_id: Number(e.target.value) || null, task_id: null }))}><option value="personal">Personal (only you)</option>{draft.project_id && !projects.some(p => p.id === draft.project_id) && <option value={draft.project_id}>Unavailable project (move to Personal)</option>}{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label><label>Task<select aria-label="Note task" disabled={readOnly || !draft.project_id} value={draft.task_id || ""} onChange={e => setDraft(d => ({ ...d, task_id: Number(e.target.value) || null }))}><option value="">No linked task</option>{draft.task_id && !tasks.some(t => t.id === draft.task_id) && <option value={draft.task_id}>Unavailable task</option>}{tasks.map(t => <option key={t.id} value={t.id}>{t.task_key} · {t.title}</option>)}</select></label></div>
          <label className="notes-tags-label">Tags<Input aria-label="Note tags" placeholder="ideas, meeting, research" value={draft.tags.join(",")} disabled={readOnly} onChange={e => setDraft(d => ({ ...d, tags: e.target.value.split(",").slice(0, 20) }))} onBlur={() => setDraft(d => ({ ...d, tags: [...new Set(d.tags.map(t => t.trim().toLowerCase()).filter(Boolean))] }))} /></label></details>
          <NoteRichEditor key={editorSession} value={draft.content} onChange={content => setDraft(d => ({ ...d, content }))} onSelection={setSelection} readOnly={readOnly} saveStatus={status.startsWith("Saving") ? "saving" : status === "Saved" ? "saved" : status.toLowerCase().includes("fail") ? "failed" : undefined} onRetry={() => void save()} />
          <footer className="notes-editor-footer"><span>{richTextPlainText(draft.content) ? richTextPlainText(draft.content).split(/\s+/).length : 0} words</span><span>{note ? `Version ${note.version}` : "Autosaves after you start writing"}</span></footer>
          {note ? <><NoteAttachments key={`attachments-${note.id}`} noteId={note.id} readOnly={readOnly} /><NoteTaskActions key={`tasks-${note.id}`} noteId={note.id} title={draft.title} selection={selection} projectId={draft.project_id} projects={projects} readOnly={readOnly} /></> : <p className="notes-attachment-help">Save your note to attach private files or create project tasks.</p>}
          {revisions.length > 0 && <aside className="notes-history" aria-label="Note version history"><div><h2>Version history</h2><Button size="sm" variant="ghost" onClick={() => { setRevisions([]); setRevisionPreview(null); }}>Close history</Button></div>{revisions.map(r => <button key={r.version} onClick={() => { void api.get(`${base}/${note?.id}/revisions/${r.version}`).then(({ data }) => setRevisionPreview(data)).catch(e => setError(workspaceError(e))); }}>Version {r.version} · {r.title} · {new Date(r.created_at).toLocaleString()}</button>)}{revisionPreview && <div className="notes-revision"><h3>{revisionPreview.title} · v{revisionPreview.version}</h3><NoteRichEditor key={revisionPreview.version} value={revisionPreview.content} readOnly /><Button disabled={readOnly || busy} onClick={() => { setDraft(d => ({ ...d, title: revisionPreview.title, content: revisionPreview.content })); setRevisions([]); setRevisionPreview(null); }}>Use this version</Button></div>}</aside>}
        </>}
      </section>
    </div>
  </main>;
}




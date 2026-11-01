import { useEffect, useMemo, useState } from "react";
import { FileText, ListChecks, Plus, Search, Star, Trash2, ArrowLeft, FolderPlus } from "lucide-react";
import MoveBoard from "@/components/interaction/MoveBoard";
import { richTextPlainText } from "@/components/rich-text/content";
import NoteEditor from "./NoteEditor";
import "./workspace.css";
import TaskCreationForm, { type TaskCreationDraft } from "./TaskCreationForm";

type Entry = { id: string; kind: "note" | "task"; title: string; content: string; notebook: string; status: string; favorite: boolean; updated: string; due: string; taskDetails?: TaskCreationDraft };
type Notebook = { id: string; name: string };
type Snapshot = { entries: Entry[]; notebooks: Notebook[] };
const statuses = ["To Do", "In Progress", "Done"];
const empty = (): Snapshot => ({ entries: [], notebooks: [{ id: "inbox", name: "Inbox" }] });
function read(key: string): Snapshot {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "null");
    if (value && Array.isArray(value.entries) && Array.isArray(value.notebooks) && value.notebooks.some((n: Notebook) => n.id === "inbox") && value.notebooks.every((n: Notebook) => typeof n.id === "string" && typeof n.name === "string") && value.entries.every((e: Entry) => typeof e.id === "string" && ["note", "task"].includes(e.kind) && typeof e.title === "string" && typeof e.content === "string")) return value;
  } catch { /* A damaged draft must not prevent opening the workspace. */ }
  return empty();
}

/** UI-only workspace. Each host supplies its own isolated user/module storage key. */
export default function ProductivityWorkspace({ storageKey, initialKind = "task", onKindChange }: { storageKey: string; initialKind?: "task" | "note"; onKindChange?: (kind: "task" | "note") => void }) {
  const [creatingTask, setCreatingTask] = useState(false);
  const [snapshot, setSnapshot] = useState(() => read(storageKey));
  const [kind, setKind] = useState(initialKind);
  const [scope, setScope] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [board, setBoard] = useState(false);
  const [folderName, setFolderName] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const [removed, setRemoved] = useState<Entry | null>(null);
  useEffect(() => { setKind(initialKind); }, [initialKind]);
  useEffect(() => {
    try { localStorage.setItem(storageKey, JSON.stringify(snapshot)); setMessage("Saved in this browser"); }
    catch { setMessage("Browser storage is full or unavailable. Keep this page open to retain your draft."); }
  }, [snapshot, storageKey]);
  const current = snapshot.entries.find(e => e.id === selected && e.kind === kind);
  const visible = useMemo(() => snapshot.entries.filter(e => e.kind === kind && (scope === "all" || (scope === "favorites" ? e.favorite : e.notebook === scope)) && `${e.title} ${richTextPlainText(e.content)}`.toLowerCase().includes(search.toLowerCase())), [snapshot.entries, kind, scope, search]);
  function update(id: string, changes: Partial<Entry>) {
    setSnapshot(s => ({ ...s, entries: s.entries.map(e => e.id === id ? { ...e, ...changes, updated: new Date().toISOString() } : e) }));
  }
  function create() {
    if (kind === "task") { setCreatingTask(true); return; }
    const entry: Entry = { id: crypto.randomUUID(), kind, title: "", content: "", notebook: snapshot.notebooks.some(n => n.id === scope) ? scope : "inbox", status: "To Do", favorite: false, updated: new Date().toISOString(), due: "" };
    setSnapshot(s => ({ ...s, entries: [entry, ...s.entries] })); setSelected(entry.id); setBoard(false);
  }
  function changeKind(next: "task" | "note") { setKind(next); setSelected(null); setBoard(false); onKindChange?.(next); }
  function remove() { if (!current) return; setRemoved(current); setSnapshot(s => ({ ...s, entries: s.entries.filter(e => e.id !== current.id) })); setSelected(null); }
  if (creatingTask) return <TaskCreationForm draftKey={`${storageKey}:task-draft`} tasks={snapshot.entries.filter(e => e.kind === "task")} onCancel={() => setCreatingTask(false)} onCreate={(draft, another) => {
    const entry: Entry = { id: crypto.randomUUID(), kind: "task", title: draft.title, content: draft.description, notebook: snapshot.notebooks.some(n => n.id === scope) ? scope : "inbox", status: draft.status, favorite: false, updated: new Date().toISOString(), due: draft.due, taskDetails: draft };
    setSnapshot(s => ({ ...s, entries: [entry, ...s.entries] })); setSelected(entry.id); setBoard(false); setSearch(""); setScope("all"); if (!another) setCreatingTask(false);
  }}/>;
  return <section className="productivity-workspace" aria-label="Tasks and notes workspace">
    <header className="pw-heading"><div><p className="pw-eyebrow">ACTIVITIES / YOUR WORKSPACE</p><h1>Tasks & notes</h1><p>Capture ideas. Organize your work. Keep everything in flow.</p></div><button className="pw-primary" onClick={create}><Plus size={16}/>New {kind}</button></header>
    <div className="pw-notice">UI workspace · Your drafts stay in this browser. CRM and PMS records are not loaded here.</div>
    <div className="pw-shell">
      <aside className="pw-sidebar" aria-label="Workspace navigation"><div className="pw-tabs"><button aria-pressed={kind === "task"} onClick={() => changeKind("task")}><ListChecks size={16}/>Tasks</button><button aria-pressed={kind === "note"} onClick={() => changeKind("note")}><FileText size={16}/>Notes</button></div>
        <button className={scope === "all" ? "active" : ""} onClick={() => setScope("all")}>All {kind}s <span>{snapshot.entries.filter(e => e.kind === kind).length}</span></button>
        <button className={scope === "favorites" ? "active" : ""} onClick={() => setScope("favorites")}><Star size={15}/>Favorites</button>
        <div className="pw-section-label">NOTEBOOKS<button aria-label="Add notebook" onClick={() => setFolderName("")}><FolderPlus size={16}/></button></div>
        {snapshot.notebooks.map(n => <button key={n.id} className={`${scope === n.id ? "active" : ""} ${dropTarget === n.id ? "pw-drop-target" : ""}`} onClick={() => setScope(n.id)} onDragOver={event => { if (draggedId) { event.preventDefault(); event.dataTransfer.dropEffect = "move"; setDropTarget(n.id); } }} onDragLeave={() => setDropTarget(null)} onDrop={event => { event.preventDefault(); if (draggedId) update(draggedId, { notebook: n.id }); setDraggedId(null); setDropTarget(null); }}><FileText size={15}/>{n.name}<span>{snapshot.entries.filter(e => e.kind === kind && e.notebook === n.id).length}</span></button>)}
        {folderName !== null && <form onSubmit={e => { e.preventDefault(); if (!folderName.trim()) return; const id = crypto.randomUUID(); setSnapshot(s => ({ ...s, notebooks: [...s.notebooks, { id, name: folderName.trim() }] })); setScope(id); setFolderName(null); }}><input autoFocus aria-label="Notebook name" placeholder="Notebook name" maxLength={80} value={folderName} onChange={e => setFolderName(e.target.value)}/><button type="submit">Add</button><button type="button" onClick={() => setFolderName(null)}>Cancel</button></form>}
        <p className="pw-sidebar-tip">Select a card to write. Drag cards onto notebooks, or use Arrange to move items between {kind === "task" ? "statuses" : "notebooks"}, or use the Move menu.</p>
      </aside>
      <main className="pw-main"><div className="pw-list-toolbar"><label><Search size={16}/><input aria-label="Search tasks and notes" placeholder={`Search ${kind}s…`} value={search} onChange={e => setSearch(e.target.value)}/></label><button aria-pressed={board} onClick={() => setBoard(!board)}>{board ? "List" : "Arrange"}</button></div>
      {removed && <div className="pw-undo" role="status">{removed.kind} removed <button onClick={() => { setSnapshot(s => ({ ...s, entries: [removed, ...s.entries] })); setRemoved(null); }}>Undo</button></div>}
      {board ? <div className="pw-board"><MoveBoard label={kind === "task" ? "Task status board" : "Notebook board"} groups={kind === "task" ? statuses.map(s => ({ id: s, label: s })) : snapshot.notebooks.map(n => ({ id: n.id, label: n.name }))} items={visible.map(e => ({ id: e.id, label: e.title || `Untitled ${kind}`, group: kind === "task" ? e.status : e.notebook, content: <button onClick={() => { setSelected(e.id); setBoard(false); }}>Open</button> }))} onMove={async ({ item, group, beforeId }) => {
        setSnapshot(s => { const entry = s.entries.find(e => e.id === item.id); if (!entry) return s; const entries = s.entries.filter(e => e.id !== item.id); const target = beforeId ? entries.findIndex(e => e.id === beforeId) : entries.length; entries.splice(target < 0 ? entries.length : target, 0, { ...entry, ...(kind === "task" ? { status: group } : { notebook: group }), updated: new Date().toISOString() }); return { ...s, entries }; });
      }}/></div> : <div className={`pw-split ${current ? "pw-has-selection" : ""}`}><section className="pw-list" aria-label={`${kind} list`}><h2>{scope === "all" ? `All ${kind}s` : scope === "favorites" ? "Favorites" : snapshot.notebooks.find(n => n.id === scope)?.name}<span>{visible.length}</span></h2>
        {!visible.length && <div className="pw-empty"><FileText size={28}/><h3>{search ? "No matches" : `Room for your next ${kind}`}</h3><p>{search ? "Try another search or notebook." : `Create a ${kind} to get started.`}</p>{!search && <button onClick={create}>Create {kind}</button>}</div>}
        {visible.map(e => <button key={e.id} className={`pw-card ${selected === e.id ? "active" : ""}`} draggable onDragStart={event => { event.dataTransfer.setData("text/plain", e.id); event.dataTransfer.effectAllowed = "move"; setDraggedId(e.id); }} onDragEnd={() => { setDraggedId(null); setDropTarget(null); }} onClick={() => setSelected(e.id)}><strong>{e.favorite && "★ "}{e.title || `Untitled ${kind}`}</strong><p>{richTextPlainText(e.content).slice(0, 140) || "Start writing…"}</p><small>{kind === "task" ? e.status : snapshot.notebooks.find(n => n.id === e.notebook)?.name} · {new Date(e.updated).toLocaleDateString()}</small></button>)}
      </section><section className="pw-editor" aria-label="Selected item editor">{current ? <><div className="pw-editor-toolbar"><button className="pw-back" onClick={() => setSelected(null)}><ArrowLeft size={15}/>Back</button><label>Notebook<select aria-label="Move to notebook" value={current.notebook} onChange={e => update(current.id, { notebook: e.target.value })}>{snapshot.notebooks.map(n => <option key={n.id} value={n.id}>{n.name}</option>)}</select></label><button aria-label="Favorite" aria-pressed={current.favorite} onClick={() => update(current.id, { favorite: !current.favorite })}><Star size={16} fill={current.favorite ? "currentColor" : "none"}/></button><button aria-label="Delete selected item" onClick={remove}><Trash2 size={16}/></button></div>
        <input className="pw-title" aria-label={`${kind === "task" ? "Task" : "Note"} title`} placeholder={`Untitled ${kind}`} maxLength={300} value={current.title} onChange={e => update(current.id, { title: e.target.value })}/>
        {kind === "task" && <div className="pw-task-fields"><label>Status<select aria-label="Task status" value={current.status} onChange={e => update(current.id, { status: e.target.value })}>{statuses.map(s => <option key={s}>{s}</option>)}</select></label><label>Due date<input type="date" value={current.due} onChange={e => update(current.id, { due: e.target.value })}/></label></div>}
        <NoteEditor key={current.id} value={current.content} onChange={content => update(current.id, { content })}/><p className="pw-save" role="status">{message}</p>
      </> : <div className="pw-empty pw-editor-empty"><FileText size={40}/><h2>A little space to think</h2><p>Select a {kind}, or create one to start writing.</p><button className="pw-primary" onClick={create}><Plus size={16}/>New {kind}</button></div>}</section></div>}
      </main>
    </div>
  </section>;
}

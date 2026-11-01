import type { MouseEvent, ReactNode } from "react";
import { Clock, FileText, Pin, Star } from "lucide-react";
import type { NoteRecord } from "./notesTypes";
import { Highlight, editedLabel } from "./notesPresentation";
export default function NoteListCard({ note, selected, checked, busy, query, dragIds, onOpen, onCheck, onContextMenu, thumbnail }: { note: NoteRecord; selected: boolean; checked: boolean; busy?: boolean; query: string; dragIds: number[]; onOpen: (event: MouseEvent<HTMLButtonElement>) => void; onCheck: (checked: boolean) => void; onContextMenu?: (event: MouseEvent<HTMLElement>) => void; thumbnail?: ReactNode }) {
  return <article className={`notes-card ${selected ? "selected" : ""} ${checked ? "checked" : ""}`} data-selected={checked} draggable={note.can_edit !== false && !busy} onDragStart={e => e.dataTransfer.setData("application/x-karyaflow-note", JSON.stringify({ kind: "notes", ids: dragIds }))} onContextMenu={onContextMenu}>
    <input type="checkbox" aria-label={`Select ${note.title}`} checked={checked} disabled={note.can_edit === false} onChange={e => onCheck(e.target.checked)}/>
    <button className="notes-card-open" disabled={busy} onClick={onOpen}><strong><FileText size={15}/><Highlight text={note.title} query={query}/>{note.favorite && <Star size={12} className="is-favorite"/>}</strong>{thumbnail}<p><Highlight text={note.preview || "An empty page, full of possibilities."} query={query}/></p><div className="notes-card-tags">{note.tags.slice(0,3).map(value => <span key={value}>#{value}</span>)}</div><small title={new Date(note.updated_at).toLocaleString()}><Clock size={11}/>{editedLabel(note.updated_at)} · {note.task_title || note.project_name || "Personal"}{note.pinned && <Pin size={11}/>}</small></button>
  </article>;
}

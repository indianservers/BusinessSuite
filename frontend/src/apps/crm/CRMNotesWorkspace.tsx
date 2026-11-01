import { useEffect, useState } from "react";
import { FileText, ListChecks } from "lucide-react";
import NotesWorkspace from "@/shared/productivity/NotesWorkspace";
import type { NoteFolder, NoteRecord } from "@/shared/productivity/notesTypes";
import { richTextPlainText } from "@/components/rich-text/content";
type Snapshot = { notes: NoteRecord[]; folders: NoteFolder[] };
function initialSnapshot(key: string, legacyKey: string): Snapshot {
  try {
    const saved = JSON.parse(localStorage.getItem(key) || "null");
    if (saved && Array.isArray(saved.notes) && Array.isArray(saved.folders) && saved.notes.every((n: NoteRecord) => typeof n.id === "number" && typeof n.title === "string" && typeof n.content === "string" && Array.isArray(n.tags)) && saved.folders.every((f: NoteFolder) => typeof f.id === "number" && typeof f.name === "string")) return saved;
    // Carry forward only this user's previous CRM browser notes, never service data.
    const old = JSON.parse(localStorage.getItem(legacyKey) || "null");
    if (Array.isArray(old?.entries) && Array.isArray(old?.notebooks)) {
      const folderIds = new Map<string,number>();
      const folders: NoteFolder[] = old.notebooks.map((n: {id:string;name:string}, index:number) => { folderIds.set(n.id,index+1); return { id:index+1,name:n.name,parent_id:null,project_id:null,task_id:null,color:"#8b5cf6",icon:"folder",position:index*10,version:1 }; });
      const now = new Date().toISOString();
      const notes: NoteRecord[] = old.entries.filter((e:{kind:string}) => e.kind === "note").map((e:{title:string;content:string;notebook:string;favorite:boolean;updated:string}, index:number) => ({id:Date.now()+index,title:e.title||"Untitled note",content:e.content||"",folder_id:folderIds.get(e.notebook)||null,project_id:null,task_id:null,tags:[],pinned:false,favorite:!!e.favorite,archived:false,version:1,project_name:"CRM Notes",task_title:null,visibility:"private",can_edit:true,preview:richTextPlainText(e.content||"").slice(0,200),created_at:e.updated||now,updated_at:e.updated||now,deleted_at:null}));
      return { notes, folders };
    }
  } catch { /* Invalid browser drafts do not prevent opening the notes UI. */ }
  return { notes:[], folders:[] };
}
export default function CRMNotesWorkspace({ legacyKey, onTasks, userId }: { legacyKey:string; onTasks:()=>void; userId?:number }) {
  const storageKey = legacyKey+":notes:v2";
  const [snapshot,setSnapshot] = useState<Snapshot>(()=>initialSnapshot(storageKey,legacyKey));
  const [status,setStatus] = useState("Saving…");
  useEffect(()=>{try{localStorage.setItem(storageKey,JSON.stringify(snapshot));setStatus("Saved in this browser");}catch{setStatus("Save failed — browser storage is unavailable or full");}},[snapshot,storageKey]);
  return <section aria-label="CRM notes workspace"><div className="mb-3 flex flex-wrap items-center justify-between gap-3"><div className="flex gap-2"><button className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm" onClick={onTasks}><ListChecks size={15}/>Tasks</button><button className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground" aria-pressed="true"><FileText size={15}/>Notes</button></div><p className="text-xs text-muted-foreground">Browser-only notes · No PMS data or sharing</p></div><NotesWorkspace userId={userId} notes={snapshot.notes} folders={snapshot.folders} onNotesChange={notes=>setSnapshot(s=>({...s,notes}))} onFoldersChange={folders=>setSnapshot(s=>({...s,folders}))} storageKey={storageKey} saveStatus={status}/></section>;
}

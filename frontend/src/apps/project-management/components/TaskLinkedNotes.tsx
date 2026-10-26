import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FileText, LockKeyhole, Plus } from "lucide-react";
import { api } from "@/services/api";
import { noteBase, type NoteRecord } from "../pages/notesTypes";
export default function TaskLinkedNotes({projectId,taskId}:{projectId:number;taskId:number}){
  const [notes,setNotes]=useState<NoteRecord[]>([]);const [error,setError]=useState("");
  useEffect(()=>{const controller=new AbortController();void api.get<NoteRecord[]>(noteBase,{params:{task_id:taskId,project_id:projectId},signal:controller.signal}).then(({data})=>setNotes(data)).catch(()=>{if(!controller.signal.aborted)setError("Could not load your linked notes.");});return()=>controller.abort();},[projectId,taskId]);
  return <section aria-label="Task notes" className="space-y-3"><div className="flex items-center justify-between"><p className="flex items-center gap-2 text-xs text-muted-foreground"><LockKeyhole size={13}/>Your private notes linked to this task</p><Link className="inline-flex items-center gap-1 text-sm text-primary" to={`/pms/notes?project=${projectId}&task=${taskId}&new=1`}><Plus size={14}/>New note</Link></div>{error&&<p role="alert">{error}</p>}{!notes.length&&!error&&<p className="py-4 text-sm text-muted-foreground">No notes linked yet. Task access never exposes another person's private notes.</p>}{notes.map(note=><Link key={note.id} className="flex items-start gap-3 rounded-lg border p-4 hover:bg-muted/30" to={`/pms/notes?note=${note.id}&project=${projectId}&task=${taskId}`}><FileText size={18}/><div><strong className="text-sm">{note.title}</strong><p className="mt-1 text-xs text-muted-foreground">{note.preview}</p></div></Link>)}</section>;
}

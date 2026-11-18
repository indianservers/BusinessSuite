import {useRecordAutosave} from "@/hooks/use-record-autosave";
import {moduleForActionPath} from "@/hooks/use-module-action";
import {useRef,useState} from "react";
import {confirmedMutation,publishQueryMutation} from "@/lib/record-changes";
import {useQueryClient} from "@tanstack/react-query";
import {api} from "@/services/api";
import {useAuthStore} from "@/store/authStore";
import {Button} from "@/components/ui/button";
import {Dialog,DialogContent,DialogTitle} from "@/components/ui/dialog";
import {Input} from "@/components/ui/input";
export function useDefinitionPermission(permissions:string[],action:string){
 const user=useAuthStore(s=>s.user);
 if(user?.is_superuser)return true;
 const module=moduleForActionPath(typeof window==="undefined"?"":window.location.pathname);
 if(user?.access)return (module?[user.access.grants[module]].filter(Boolean):Object.values(user.access.grants)).some(grant=>grant.enabled&&grant.actions.includes(action)&&permissions.some(p=>grant.permissions.includes(p)));
 return ["admin","super_admin"].includes(user?.role||"");
}
/** Operates on the selected definition; domain endpoints retain all authorization and dependency checks. */
export default function RecordDefinitionActions({record,endpoint,nameField="name",queryKeys,permissions,canDelete=true,canRename=true,onDeleted}:{record:Record<string,unknown>;endpoint:string;nameField?:string;queryKeys:string[];permissions:string[];canDelete?:boolean;canRename?:boolean;onDeleted?:()=>void}){
 const qc=useQueryClient(),edit=useDefinitionPermission(permissions,"edit"),remove=useDefinitionPermission(permissions,"delete");
 const [mode,setMode]=useState<"rename"|"delete"|null>(null),[name,setName]=useState(""),[busy,setBusy]=useState(false),[error,setError]=useState("");const label=String(record[nameField]||record.id);
 const saving=useRef(false);
 async function submit(automatic=false){if(saving.current)return false;saving.current=true;setBusy(!automatic);setError("");try{const payload={...record,[nameField]:name.trim()};const response=mode==="delete"?await api.delete(endpoint):await api.put(endpoint,payload);publishQueryMutation(qc,confirmedMutation(endpoint,mode==="delete"?'delete':'put',payload,response.data),queryKeys);if(mode==="delete")onDeleted?.();if(!automatic)setMode(null);void Promise.all(queryKeys.map(key=>qc.invalidateQueries({queryKey:[key]})));return true;}catch(e){const detail=(e as {response?:{data?:{detail?:unknown}}}).response?.data?.detail;setError(typeof detail==="string"?detail:"Could not save this change. Your selection is retained.");return false;}finally{saving.current=false;setBusy(false);}}
 const auto=useRecordAutosave({value:name,enabled:mode==="rename"&&edit&&!busy&&!!name.trim(),dirty:name!==label,save:()=>submit(true)});
 return <>{canRename&&<Button size="sm" variant="outline" disabled={!edit||busy} aria-label={`Rename ${label}`} onClick={()=>{setName(label);setError("");setMode("rename");}}>Rename</Button>}{canDelete&&<Button size="sm" variant="outline" disabled={!remove||busy} aria-label={`Delete ${label}`} onClick={()=>{setError("");setMode("delete");}}>Delete</Button>}<Dialog open={!!mode} onOpenChange={open=>{if(!open&&!busy)setMode(null);}}><DialogContent><DialogTitle>{mode==="delete"?"Delete definition":"Rename definition"}</DialogTitle><p>{label}</p><form className="space-y-3" onSubmit={e=>{e.preventDefault();void submit();}}>{mode==="rename"?<label className="block">Name<Input aria-label="Definition name" required maxLength={180} value={name} onChange={e=>setName(e.target.value)}/></label>:<p>Delete this definition? The server will retain protected or linked records and explain any restriction.</p>}{error&&<p role="alert">{error}</p>}<div className="flex gap-2"><Button type="button" variant="outline" disabled={busy} onClick={()=>setMode(null)}>Cancel</Button><span role="status">{mode!=="delete"&&auto.message}</span><Button type="submit" data-save-action={mode!=="delete"?"":undefined} disabled={busy||auto.saving||(mode==="rename"?(!edit||!name.trim()):!remove)}>{busy?"Saving...":mode==="delete"?"Confirm delete":"Save name"}</Button></div></form></DialogContent></Dialog></>;
}

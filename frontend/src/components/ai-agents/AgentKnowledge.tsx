import {useEffect,useState} from 'react';
import {api} from '@/services/api';

export type KnowledgeFile={conversation_id:number;attachment_id:number;sha256:string};
type Source=KnowledgeFile&{name:string;conversation_title:string;notes:string[]};

export default function AgentKnowledge({workspaceId,selected,onChange,disabled=false}:{workspaceId?:number;selected:KnowledgeFile[];onChange:(files:KnowledgeFile[])=>void;disabled?:boolean}){
 const [items,setItems]=useState<Source[]>([]),[error,setError]=useState(''),[loading,setLoading]=useState(false),[refresh,setRefresh]=useState(0);
 useEffect(()=>{let active=true;setLoading(true);setError('');setItems([]);api.get('/ai-operator/suite/agents/knowledge/files',{params:{workspace_id:workspaceId}}).then(r=>{if(active)setItems(r.data.items||[])}).catch(()=>{if(active)setError('Could not load private knowledge files. Try refreshing.');}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[workspaceId,refresh]);
 return <details><summary>Add knowledge · {selected.length}/4 files</summary>
  <p>Select existing uploads to reuse in this agent’s future chats and scheduled runs. Files stay private on the server in their original conversations. Removing or archiving a source conversation blocks dependent work until you update the agent. Sharing the agent excludes these files.</p>
  <button type="button" disabled={disabled||loading} onClick={()=>setRefresh(n=>n+1)}>Refresh knowledge files</button>
  {loading&&<p role="status">Loading private files…</p>}{error&&<p role="alert">{error}</p>}
  {!loading&&!error&&!items.length&&<p>Upload a document using the bot’s Files tab, then refresh this list. The latest 100 conversations in this workspace are searched.</p>}
  {selected.filter(s=>!items.some(i=>i.attachment_id===s.attachment_id)).map(s=><p key={s.attachment_id}>Selected file #{s.attachment_id} · not in the current list <button type="button" disabled={disabled} onClick={()=>onChange(selected.filter(i=>i.attachment_id!==s.attachment_id))}>Remove file #{s.attachment_id}</button></p>)}
  {items.map(file=>{const checked=selected.some(s=>s.attachment_id===file.attachment_id);return <label key={file.attachment_id}><input type="checkbox" aria-label={`Agent knowledge: ${file.name}`} checked={checked} disabled={disabled||!checked&&selected.length>=4} onChange={()=>onChange(checked?selected.filter(s=>s.attachment_id!==file.attachment_id):[...selected,{conversation_id:file.conversation_id,attachment_id:file.attachment_id,sha256:file.sha256}])}/>{file.name} · {file.conversation_title}{file.notes?.length>0&&<small>{file.notes.join(' ')}</small>}</label>})}
 </details>
}

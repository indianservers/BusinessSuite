import {useEffect,useState} from 'react';
import {api} from '@/services/api';
const ROOT='/ai-operator/suite/agents/mcp';
export default function AgentMcp({workspaceId,selected,onChange}:{workspaceId?:number;selected:number[];onChange:(ids:number[])=>void}){
 const [items,setItems]=useState<any[]>([]),[connections,setConnections]=useState<any[]>([]),[tools,setTools]=useState<any[]>([]),[chosen,setChosen]=useState<string[]>([]);
 const [name,setName]=useState(''),[endpoint,setEndpoint]=useState(''),[connection,setConnection]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 async function load(){const r=await api.get(ROOT,{params:{workspace_id:workspaceId}});setItems(r.data.items||[])}
 useEffect(()=>{void load().catch(()=>setError('Could not load MCP tools.'));void api.get('/ai-operator/suite/agents/connectors').then(r=>setConnections((r.data.connections||[]).filter((c:any)=>c.connector_id==='http'&&c.enabled&&c.writes_enabled))).catch(()=>{});},[workspaceId]);
 const body={name,connection_id:Number(connection),endpoint,protocol:'2025-11-25',tools:chosen,environment:'development',workspace_id:workspaceId||null};
 async function submit(save:boolean){setBusy(true);setError('');try{const r=await api.post(ROOT+(save?'':'/discover'),body);if(save){await load();onChange([...selected,r.data.id]);setTools([]);setChosen([]);setName('');setEndpoint('')}else {setTools(r.data.tools||[]);setChosen([])}}catch(e:any){setError(typeof e.response?.data?.detail==='string'?e.response.data.detail:'Could not connect. Check the authorized HTTPS endpoint and connection.')}finally{setBusy(false)}}
 return <details><summary>Custom MCP tools</summary><p>Use an existing development HTTP connection in the encrypted server vault. HTTPS host access and POST must be enabled there. Every tool call requires action review.</p>
 {items.map(i=><label key={i.id}><input type="checkbox" checked={selected.includes(i.id)} onChange={()=>onChange(selected.includes(i.id)?selected.filter(id=>id!==i.id):[...selected,i.id])}/>{i.name} · {i.tools.length} tools</label>)}
 <label>MCP name<input value={name} maxLength={120} onChange={e=>{setName(e.target.value);setTools([])}}/></label>
 <label>Vault connection<select value={connection} onChange={e=>{setConnection(e.target.value);setTools([])}}><option value="">Select HTTP connection</option>{connections.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
 <label>HTTPS MCP endpoint<input type="url" value={endpoint} onChange={e=>{setEndpoint(e.target.value);setTools([])}} placeholder="https://service.example/mcp"/></label>
 <button type="button" disabled={busy||!name.trim()||!connection||!endpoint} onClick={()=>void submit(false)}>Discover tools</button>
 {tools.map(t=><label key={t.name}><input type="checkbox" checked={chosen.includes(t.name)} disabled={!chosen.includes(t.name)&&chosen.length>=40} onChange={()=>setChosen(old=>old.includes(t.name)?old.filter(n=>n!==t.name):[...old,t.name])}/>{t.name}<small>{t.description}</small></label>)}
 {tools.length>0&&<button type="button" disabled={busy||!chosen.length} onClick={()=>void submit(true)}>Save selected MCP tools</button>}{error&&<p role="alert">{error}</p>}
 </details>
}

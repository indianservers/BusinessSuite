import {useEffect,useRef,useState} from 'react';
import {Link} from 'react-router-dom';
import {api} from '@/services/api';

const labels:Record<string,string>={ready_to_read:'Ready to read',ready_for_review:'Ready for action review',
 native_workflow_required:'Use the native controlled workflow',permission_required:'Execution permission required',
 connection_disabled:'Connection disabled',authorization_unavailable:'Authorization unavailable',
 authorization_expired:'Authorization expired',missing_scopes:'Additional scopes required',
 writes_disabled:'Writes are disabled',verification_required:'Verify the connection first'};
const date=(value?:string|null)=>value?new Date(value).toLocaleString():'None recorded';

export default function WorkspaceConnections(){
 const [data,setData]=useState<any>(null),[environment,setEnvironment]=useState('development'),[query,setQuery]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[refresh,setRefresh]=useState(0);
 const sequence=useRef(0);
 useEffect(()=>{const ticket=++sequence.current;setData(null);setError('');setBusy(true);
  void api.get('/ai-operator/suite/agents/connectors',{params:{environment}})
   .then(r=>{if(ticket===sequence.current)setData(r.data)})
   .catch(()=>{if(ticket===sequence.current)setError('Connector access is unavailable. Your Power Apps connection permissions are required.')})
   .finally(()=>{if(ticket===sequence.current)setBusy(false)});
  return()=>{sequence.current++};
 },[environment,refresh]);
 return <section aria-label="Agent connections"><h3>Connections</h3>
  <p>Accounts and credentials use the existing server vault. Provider-confirmed identity comes from the native account check and is rechecked after authorization changes.</p>
  <div className="bot-file-actions"><label>Environment<select aria-label="Agent connection environment" value={environment} onChange={e=>{sequence.current++;setData(null);setEnvironment(e.target.value)}}>{['development','testing','production'].map(e=><option key={e}>{e}</option>)}</select></label><button type="button" disabled={busy} onClick={()=>{sequence.current++;setData(null);setRefresh(n=>n+1)}}>Refresh connection status</button><Link to="/power-apps/integrations">Open authorization center</Link></div>
  {busy&&<p role="status">Loading authorized connection status…</p>}
  {data?.connections?.map((c:any)=><article className="bot-result-card" key={c.id} aria-label={`Connection ${c.id}`}>
   <small>{c.connector_id} · {c.live_verified?'Live verified':c.health}</small><h4>{c.name}</h4>
   <p>{c.enabled?'Enabled':'Disabled'} · {c.writes_enabled?'Native writes opted in':'Native writes disabled'}</p>
   <p>Authorization: {({verified:'Verified',unverified:'Not verified',unavailable:'Unavailable',expired:'Expired',disabled:'Disabled'} as Record<string,string>)[c.authorization_status]||'Check current authorization'}</p>
   <section aria-label={`Provider account ${c.id}`}><h5>Provider account</h5>{c.account?.status==='verified'?<><dl>{Object.entries(c.account.identity||{}).map(([key,value])=><div key={key}><dt>{({id:'Account ID',label:'Account name',email:'Email',workspace:'Workspace',workspace_id:'Workspace ID'} as Record<string,string>)[key]||key}</dt><dd className="break-all">{String(value)}</dd></div>)}</dl><p>Account verified: {date(c.account.verified_at)}</p></>:<p>{c.account?.status==='not_reported'?'This provider check has not reported an account identity.':'Run the native account check to verify the current authorization.'}</p>}</section>
   <p className="break-all">Granted scopes: {c.scopes?.join(', ')||'None reported'}</p>
   <p>Last provider check: {date(c.last_verified_at)}</p><p>Authorization expiry: {c.expires_at?date(c.expires_at):'Not reported'}</p>
   {c.history_visible===false?<p>Connection history requires activity permission.</p>:<><p>Last successful operation: {date(c.last_successful_operation_at)}</p><p>Last successful data read: {date(c.last_successful_read_at)}</p><small>A successful read records that operation; synchronization completion uses the native workflow history.</small></>}
   <details><summary>{c.actions?.length||0} actions for this connection</summary><p>Readiness is a snapshot of this connection. The selected agent, current permissions, rate limits and action inputs are checked again at execution. Changes require separate review.</p>{c.actions?.map((a:any)=><section key={a.id} className="mt-3" aria-label={`Connection ${c.id} action ${a.id}`}><p>{a.name} · {a.mutates?'Reviewed action':'Read'} · {labels[a.status]||'Check authorization'}</p><p className="break-all">Required scopes: {a.scopes?.join(', ')||'None declared'}</p>{a.missing_scopes?.length>0&&<p className="break-all">Missing scopes: {a.missing_scopes.join(', ')}</p>}</section>)}</details>
   {c.recent_errors?.length>0&&<details><summary>Recent operation errors</summary>{c.recent_errors.map((e:any)=><p key={e.id}>{e.action_id} · {e.category} · {e.status} · {date(e.at)}</p>)}</details>}
  </article>)}
  {data&&!data.connections?.length&&<p>No authorized connections in this environment.</p>}
  <h4>Adapter catalog</h4><input aria-label="Search agent connectors" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Email, calendar, storage, CRM…"/>
  {data?.catalog?.filter((c:any)=>(c.name+' '+c.category+' '+c.description).toLowerCase().includes(query.toLowerCase())).slice(0,30).map((c:any)=><article className="bot-result-card" key={c.id}><small>{c.category} · {c.availability}</small><h4>{c.name}</h4><p>{c.description}</p><details><summary>{c.actions?.length||0} registered actions</summary>{c.actions?.map((a:any)=><p key={a.id} className="break-all">{a.name} · {a.mutates?'Native action':'Read'} · scopes: {a.scopes?.join(', ')||'Provider dependent'}</p>)}</details></article>)}
  <p>Showing up to 30 matching adapters. Search by name or purpose to narrow the list. Configure custom MCP tools in the Agents section.</p>{error&&<p role="alert">{error}</p>}
 </section>;
}

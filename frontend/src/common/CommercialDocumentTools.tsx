import { useEffect, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useModuleAction } from "@/hooks/use-module-action";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { commonNavigationHref, commonRouteContext } from "@/lib/common-routes";
import { getOperationWorkspace } from "@/lib/navigation-workspaces";
import { canAccessRoute } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";
import { useRecordScope } from "@/lib/record-scope";

type Context = NonNullable<ReturnType<typeof commonRouteContext>>;
type Value = Record<string, any>;
const supported = ['quotations','purchase-orders','sales-orders','contracts','invoices'];
const label = (key:string) => key.replace(/_/g,' ').replace(/\b\w/g,letter=>letter.toUpperCase());
const errorText = (error:unknown) => {
  const value = (error as any)?.response?.data?.detail;
  return typeof value==='string'?value:'Unable to complete this action. Check the fields and try again.';
};

export default function CommercialDocumentTools({context:hostContext,children}:{context:Context;children?:ReactNode}) {
  const location=useLocation();
  const user=useAuthStore(state=>state.user);
  const operation=new URLSearchParams(location.search).get('operation');
  let context=hostContext;
  if(hostContext.module==='srm' && operation && getOperationWorkspace(hostContext.nativePath)?.paths.includes(operation) && canAccessRoute(operation,user?.role,user?.is_superuser)) {
    const selected=commonRouteContext(commonNavigationHref(operation,'srm'));
    if(!selected)return <>{children}</>;
    context=selected;
  }
  if (!supported.includes(context.entity)) return <>{children}</>;
  const match = /\/(\d+)(?:\/builder)?$/.exec(context.nativePath);
  return match ? <DocumentTools key={`${context.entity}-${match[1]}`} context={context} id={Number(match[1])}>{children}</DocumentTools> : <><DocumentRegister key={context.entity} context={context}/>{children}</>;
}

function DocumentRegister({context}:{context:Context}) {
  const queryClient=useQueryClient();
  const scope=useRecordScope();
  const [search,setSearch]=useState(''),[page,setPage]=useState(1),[removed,setRemoved]=useState(false);
  useEffect(()=>{
    const paths=context.entity==='quotations'?['/crm/quotes','/crm/quotations']:context.entity==='purchase-orders'?['/srm/procurement/purchase-orders']:[`/srm/${context.entity}`];
    const changed=(event:Event)=>{const path=String((event as CustomEvent).detail||'').split('?')[0];if(paths.some(prefix=>path===prefix||path.startsWith(prefix+'/')))void queryClient.invalidateQueries({queryKey:['document-register',context.entity,scope]});};
    window.addEventListener('suite:record-mutated',changed);
    return()=>window.removeEventListener('suite:record-mutated',changed);
  },[context.entity,scope,queryClient]);
  const query=useQuery({queryKey:['document-register',context.entity,scope,search,page,removed],staleTime:0,refetchOnMount:'always',queryFn:async()=>{const {data}=await api.get(`/srm/documents/${context.entity}`,{params:{search,page,include_removed:removed},recordCache:false});if(!Array.isArray(data?.items))throw Error('The document register returned an invalid response');return data;}});
  return <section aria-label="Saved document register" className="my-4 space-y-3 rounded-xl border bg-card p-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">Saved documents</h2><Button variant="outline" onClick={()=>query.refetch()}>Refresh saved documents</Button></div>
    <p className="text-sm text-muted-foreground">Find issued documents and drafts, open their history, resend a copy, or prepare a revision.</p>
    <div className="flex flex-wrap items-center gap-3"><Input aria-label="Search saved documents" placeholder="Search document number" value={search} onChange={event=>{setSearch(event.target.value);setPage(1);}}/><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={removed} onChange={event=>{setRemoved(event.target.checked);setPage(1);}}/>Include archived drafts</label></div>
    {query.isPending&&<p role="status">Loading saved documents…</p>}
    {query.isError&&<p role="alert">{errorText(query.error)}</p>}
    <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th className="p-2">Number</th><th className="p-2">Status</th><th className="p-2">Total</th><th className="p-2">Created</th><th className="p-2">Actions</th></tr></thead><tbody>{query.data?.items.map((row:Value)=><tr key={row.id} className="border-t"><td className="p-2 font-medium">{row.number}</td><td className="p-2">{row.removed?'Archived':row.status}</td><td className="p-2">{row.currency} {Number(row.total||0).toLocaleString()}</td><td className="p-2">{row.created_at?new Date(row.created_at).toLocaleDateString():''}</td><td className="p-2"><Button asChild variant="outline" size="sm"><Link to={`/common/${context.entity}/${row.id}?module=${context.module}`}>Open record</Link></Button></td></tr>)}</tbody></table></div>
    {query.data&&!query.data.items.length&&<p>No saved documents match these filters.</p>}
    <div className="flex gap-2"><Button variant="outline" disabled={page===1} onClick={()=>setPage(page-1)}>Previous records</Button><span className="self-center text-sm">Page {page}</span><Button variant="outline" disabled={!query.data?.has_more} onClick={()=>setPage(page+1)}>Next records</Button></div>
  </section>;
}

function DocumentTools({context,id,children}:{context:Context;id:number;children?:ReactNode}) {
  const scope=useRecordScope();
  const [actionVersion,setActionVersion]=useState('');
  const queryClient=useQueryClient(),navigate=useNavigate();
  const [mode,setMode]=useState(''),[reason,setReason]=useState(''),[recipient,setRecipient]=useState(''),[changes,setChanges]=useState<Value>({}),[lines,setLines]=useState<Value[]>([]),[requestId,setRequestId]=useState(()=>crypto.randomUUID()),[notice,setNotice]=useState('');
  const allowEdit=useModuleAction('edit'),allowCreate=useModuleAction('create'),allowDelete=useModuleAction('delete'),allowExport=useModuleAction('export');
  const base=`/srm/documents/${context.entity}/${id}`;
  const query=useQuery({queryKey:['document-record',context.entity,id,scope],staleTime:0,refetchOnMount:'always',queryFn:async()=>{const {data}=await api.get(base,{recordCache:false});if(!data?.record||!Array.isArray(data.history))throw Error('Document history returned an invalid response');return data;}});
  useEffect(()=>{
    // Native workflow actions and the shared controls edit the same record.
    const prefixes=context.entity==='quotations'?[`/crm/quotes/${id}`,`/crm/quotations/${id}`]:[`/srm/${context.entity}/${id}`];
    const changed=(event:Event)=>{const path=String((event as CustomEvent).detail||'').split('?')[0];if(prefixes.some(prefix=>path===prefix||path.startsWith(prefix+'/')))void Promise.all([queryClient.invalidateQueries({queryKey:['document-record',context.entity,id,scope]}),queryClient.invalidateQueries({queryKey:['document-register',context.entity,scope],refetchType:'none'})]);};
    window.addEventListener('suite:record-mutated',changed);
    return()=>window.removeEventListener('suite:record-mutated',changed);
  },[context.entity,id,scope,queryClient]);
  const action=useMutation({mutationFn:async()=>{
    const payload={reason,version:actionVersion,request_id:requestId,...(mode==='send'&&recipient?{recipient}:{}),...(mode==='edit'?{changes,...(lines.length?{lines}: {})}:{})};
    return (await api.request({url:mode==='edit'||mode==='archive'?base:`${base}/${mode}`,method:mode==='edit'?'patch':mode==='archive'?'delete':'post',data:payload})).data;
  },onSuccess:async data=>{
    const saved=data.document||data;
    if(saved.record)queryClient.setQueryData(['document-record',context.entity,saved.record.id,scope],saved);
    const refetchType=mode==='archive'?'none' as const:'active' as const;
    await Promise.all([queryClient.invalidateQueries({queryKey:['document-record'],refetchType:saved.record?'none':'active'}),queryClient.invalidateQueries({queryKey:['document-register']}),queryClient.invalidateQueries({queryKey:['srm'],refetchType}),queryClient.invalidateQueries({queryKey:['crm'],refetchType}),queryClient.invalidateQueries({queryKey:['shared-invoice'],refetchType})]);
    setMode('');setReason('');setRequestId(crypto.randomUUID());
    setNotice(mode==='send'?`Delivery ${data.status}${data.error?': '+data.error:''}`:mode==='archive'?'Draft archived. Its record and history are retained.':'Document saved.');
    if(mode==='revise')navigate(`/common/${context.entity}/${data.record.id}?module=${context.module}`);
  }});
  const pdf=useMutation({mutationFn:async()=>(await api.get(`${base}/pdf`,{responseType:'blob'})).data,onSuccess:blob=>{const url=URL.createObjectURL(blob),anchor=document.createElement('a');anchor.href=url;anchor.download=`${query.data.number}.pdf`;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),10000);}});
  const begin=(next:string)=>{
    setActionVersion(query.data.version);
    action.reset();setMode(next);setReason('');setNotice('');setRequestId(crypto.randomUUID());
    const row=query.data.record;
    setChanges(Object.fromEntries(editFields(context.entity).map(key=>[key,row[key]||''])));
    setLines((row.lines||[]).map((line:Value)=>({id:line.id,description:line.name||line.description||'',quantity:line.quantity,unit_price:line.unit_price,discount_amount:line.discount_amount||0,...(context.entity==='quotations'?{tax_rate:line.tax_rate||0}:{tax_amount:line.tax_amount||0})})));
  };
  if(query.isPending)return <p role="status">Loading document history…</p>;
  if(query.isError)return <><section aria-label="Document history and actions" className="my-4 rounded-xl border p-4"><p role="alert">Document controls unavailable. {errorText(query.error)} <Button variant="outline" onClick={()=>query.refetch()}>Refresh document controls</Button></p></section>{children}</>;
  const data=query.data,row=data.record;
  const active=!data.removed&&!['cancelled','declined','rejected'].includes(String(row.status).toLowerCase());
  return <><section aria-label="Document history and actions" className="my-4 space-y-4 rounded-xl border bg-card p-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">Record history and actions</h2><p className="text-sm text-muted-foreground">{data.number} · {data.removed?'Archived':row.status} · Created {row.created_at?new Date(row.created_at).toLocaleString():'previously'}</p></div><Button variant="outline" onClick={()=>query.refetch()}>Refresh document controls</Button></div>
    <fieldset disabled={query.isFetching || action.isPending} className="flex flex-wrap gap-2">
      {allowExport&&<Button variant="outline" disabled={pdf.isPending} onClick={()=>pdf.mutate()}>Download document PDF</Button>}
      {active&&!data.editable&&allowCreate&&<Button variant="outline" onClick={()=>begin('send')}>Send / resend document</Button>}
      {active&&data.editable&&allowEdit&&<Button variant="outline" onClick={()=>begin('edit')}>Modify draft with reason</Button>}
      {!data.removed&&allowCreate&&<Button variant="outline" onClick={()=>begin('revise')}>Create revision draft</Button>}
      {active&&context.entity==='purchase-orders'&&data.editable&&allowEdit&&<Button variant="outline" onClick={()=>begin('issue')}>Issue purchase order</Button>}
      {active&&!data.editable&&allowEdit&&<Button variant="outline" onClick={()=>begin('cancel')}>Cancel with reason</Button>}
      {data.editable&&allowDelete&&<Button variant="outline" onClick={()=>begin('archive')}>Archive draft</Button>}
    </fieldset>
    {notice&&<p role="status">{notice}</p>}{pdf.isError&&<p role="alert">{errorText(pdf.error)}</p>}
    {mode&&<form aria-label="Document action form" className="space-y-3 rounded-lg border p-4" onSubmit={event=>{event.preventDefault();if(!action.isPending)action.mutate();}}>
      <h3 className="font-semibold">{({edit:'Modify draft',revise:'Create a revision draft',send:'Send a copy',archive:'Archive unused draft',cancel:'Cancel document',issue:'Issue purchase order'} as Value)[mode]}</h3>
      {mode==='revise'&&<p className="text-sm text-muted-foreground">The original document remains in its register. The new draft has its own number and a link to the original.{context.entity==='invoices'?' Finance must cancel the original before the revised invoice can be issued.':''}</p>}
      {mode==='cancel'&&context.entity==='sales-orders'&&<p className="text-sm text-muted-foreground">Unused engagements and draft billing plans will also be cancelled and retained with this reason. Orders with delivery, stock issues, active contracts, or billing activity require review first.</p>}
      {mode==='archive'&&<p className="text-sm text-muted-foreground">The unused draft is removed from the active register. Its history remains available under “Include archived drafts”.</p>}
      {mode==='send'&&<label className="block text-sm">Recipient email<Input aria-label="Document recipient email" type="email" placeholder="Use the saved billing recipient" value={recipient} onChange={event=>setRecipient(event.target.value)}/></label>}
      {mode==='edit'&&<fieldset disabled={action.isPending} className="space-y-3">{editFields(context.entity).map(key=><label key={key} className="block text-sm">{label(key)}{key.endsWith('_date')?<Input aria-label={`Document ${label(key)}`} type="date" value={changes[key]||''} onChange={event=>setChanges({...changes,[key]:event.target.value})}/>:<textarea aria-label={`Document ${label(key)}`} className="block min-h-20 w-full rounded-md border bg-background p-2" maxLength={10000} value={changes[key]||''} onChange={event=>setChanges({...changes,[key]:event.target.value})}/>}</label>)}
        {lines.map((line,index)=><fieldset key={line.id} aria-label={`Document line ${index+1}`} className="grid gap-2 rounded-md border p-3 sm:grid-cols-3"><legend className="text-sm">Line {index+1}</legend>{Object.keys(line).filter(key=>key!=='id').map(key=><label key={key} className="text-sm">{label(key)}<Input aria-label={`Line ${index+1} ${label(key)}`} type={key==='description'?'text':'number'} min={key==='quantity'?'0.01':'0'} step="any" value={line[key]} onChange={event=>setLines(lines.map((item,i)=>i===index?{...item,[key]:key==='description'?event.target.value:Number(event.target.value)}:item))}/></label>)}</fieldset>)}
      </fieldset>}
      <label className="block text-sm">Reason<textarea aria-label="Document action reason" required minLength={5} maxLength={500} className="block min-h-20 w-full rounded-md border bg-background p-2" value={reason} onChange={event=>setReason(event.target.value)} placeholder="Explain the correction, resend, or cancellation"/></label>
      {action.isError&&<p role="alert">{errorText(action.error)}</p>}
      <div className="flex gap-2"><Button type="submit" disabled={action.isPending||reason.trim().length<5}>{action.isPending?'Saving…':mode==='send'?'Send document':mode==='archive'?'Confirm archive':mode==='revise'?'Create revised draft':mode==='cancel'?'Confirm cancellation':mode==='issue'?'Confirm issue':'Save document changes'}</Button><Button type="button" variant="outline" disabled={action.isPending} onClick={()=>setMode('')}>Close action form</Button></div>
    </form>}
    <details><summary className="cursor-pointer font-medium">Document history ({data.history.length})</summary><div className="mt-3 space-y-3">{!data.history.length&&<p className="text-sm">The saved record is available above. Future revisions, edits and delivery attempts will appear here.</p>}{data.history.map((entry:Value)=><article key={entry.id} className="rounded-lg border p-3 text-sm"><p className="font-medium">{label(entry.action)}</p><p>{new Date(entry.created_at).toLocaleString()} · User {entry.actor_id||'system'}</p>{entry.reason&&<p>Reason: {entry.reason}</p>}{entry.after?.record?.recipient&&<p>Recipient: {entry.after.record.recipient}</p>}{entry.after?.record?.status&&<p>Status: {entry.after.record.status}</p>}{entry.after?.record?.error&&<p>{entry.after.record.error}</p>}{(entry.after?.record?.source_id||entry.action==='revision_created'&&entry.after?.record?.id)&&<Link className="text-primary underline" to={`/common/${context.entity}/${entry.after.record.source_id||entry.after.record.id}?module=${context.module}`}>Open related document</Link>}<details className="mt-2"><summary>View saved values</summary><Snapshot title="Before" value={entry.before}/><Snapshot title="After" value={entry.after?.record||entry.after}/></details></article>)}</div></details>
  </section>{data.removed?<main className="space-y-3"><h1 className="page-title">{data.number}</h1><p>This draft is archived. Its saved values and history are retained.</p><Snapshot title="Saved document" value={row}/></main>:children}</>;
}

function editFields(kind:string):string[] {
  return ({quotations:['notes','terms','expiry_date'],'purchase-orders':['notes','expected_date'],'sales-orders':['title','terms'],contracts:['title','terms','effective_date','expiry_date'],invoices:['due_date']} as Record<string,string[]>)[kind]||[];
}
function Snapshot({title,value}:{title:string;value?:Value}) {
  if(!value)return null;
  return <div className="mt-2 space-y-1"><h4 className="font-medium">{title}</h4>{['quote_number','po_number','order_number','invoice_number','contract_number','title','status','currency','subtotal','tax_amount','discount_amount','total_amount','contract_value','notes','terms','due_date','expected_date'].filter(key=>value[key]!=null).map(key=><p key={key}>{label(key)}: {String(value[key])}</p>)}{value.lines?.map((line:Value)=><p key={line.id}>{line.name||line.description} · {line.quantity} × {line.unit_price} · Total {line.line_total??line.total_amount}</p>)}</div>;
}

import { standardRecordGroups } from "@/shared/data-grid/record-group-fields";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useLocation } from 'react-router-dom';
import { Plug, ShieldCheck, Search } from 'lucide-react';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import ConnectorWorkflows from './ConnectorWorkflows';

type App = {id:string;name:string;category:string;description:string;modules:string[];implemented:boolean;authorization:string[];destination:string|null;actions:string[];setup:string[];documentation_url:string|null;blocked_reason?:string};
const modules:Record<string,string>={crm:'CRM',pms:'Projects',hrms:'HRMS',srm:'Sales',fam:'Finance'};
export default function ConnectorCatalog(){
  const location=useLocation();
  const root=location.pathname.split('/')[1];
  const module=modules[root]?root:'';
  const [search,setSearch]=useState(''),[category,setCategory]=useState(''),[selected,setSelected]=useState<App|null>(null);
  const query=useQuery({queryKey:['connector-discovery'],queryFn:async()=>(await api.get<{items:App[]}>('/power-apps/integrations/discovery')).data.items});
  const scoped=(query.data||[]).filter(app=>!module||app.modules.includes(module));
  const visible=scoped.filter(app=>(!category||category===app.category)&&`${app.name} ${app.description}`.toLowerCase().includes(search.toLowerCase()));
  return <section className="space-y-5">
    <header><p className="text-sm text-muted-foreground">{module?modules[module]:'Common workspace'}</p><h1 className="text-2xl font-semibold">Connectors & authorization</h1><p>One shared catalog. Connections use the existing secure authorization workspace and remain subject to your permissions.</p></header>
    <ConnectorWorkflows module={module}/>
    <nav className="flex flex-wrap gap-3" aria-label="Connector modules"><Link to="/connectors">All connectors</Link>{Object.entries(modules).map(([id,label])=><Link key={id} to={`/${id}/connectors`}>{label}</Link>)}</nav>
    <div className="flex flex-wrap gap-3"><label className="flex items-center gap-2"><Search size={18}/><Input aria-label="Search connectors" placeholder="Search apps" value={search} onChange={e=>setSearch(e.target.value)}/></label><NativeSelect aria-label="Connector category" value={category} onChange={e=>setCategory(e.target.value)}><option value="">All categories</option>{[...new Set(scoped.map(app=>app.category))].sort().map(c=><option key={c}>{c}</option>)}</NativeSelect></div>
    {query.isLoading&&<p role="status">Loading connectors…</p>}{query.isError&&<div role="alert">Could not load connectors. <Button onClick={()=>query.refetch()}>Retry</Button></div>}
    <p>{visible.length} connectors</p>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{<GroupedRecords scope="shared/ConnectorCatalog:records-1" items={(visible) || []} fields={standardRecordGroups((visible) || [])} gridClassName="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" renderItem={app=><article key={app.id} className="rounded-lg border bg-card p-4 space-y-3"><div className="flex items-center gap-2"><Plug size={20}/><h2 className="font-semibold">{app.name}</h2></div><p className="text-sm">{app.description}</p><p className="text-xs text-muted-foreground">{app.category} · {app.implemented?'Adapter available':app.blocked_reason?'Provider API access unavailable':'Adapter pending'}</p><div className="flex flex-wrap gap-2">{app.modules.map(id=><span className="rounded border px-2 text-xs" key={id}>{modules[id]||id}</span>)}</div><Button variant="outline" onClick={()=>setSelected(app)}>Details & authorization</Button></article>}/>}</div>
    {query.isSuccess&&!visible.length&&<p>No connectors match these filters.</p>}
    <Dialog open={!!selected} onOpenChange={open=>{if(!open)setSelected(null);}}><DialogContent className="max-h-[85vh] overflow-y-auto"><DialogTitle>{selected?.name}</DialogTitle>{selected&&<><p>{selected.description}</p><h3 className="font-semibold">Setup and authorization</h3><ul className="list-disc pl-5">{selected.setup.map(step=><li key={step}>{step}</li>)}</ul><p><ShieldCheck className="inline" size={16}/> {selected.implemented?'Authorization is verified only after an authorized provider request succeeds.':'Authorization is unavailable until this provider adapter is implemented.'}</p>{selected.authorization.length>0&&<p>Supported authorization: {selected.authorization.join(', ')}</p>}{selected.actions.length>0&&<><h3 className="font-semibold">Implemented actions</h3><ul className="list-disc pl-5">{selected.actions.map(action=><li key={action}>{action}</li>)}</ul></>}{selected.documentation_url&&<a className="underline" href={selected.documentation_url} target="_blank" rel="noreferrer">Provider documentation</a>}{selected.destination&&<Button asChild><Link to={selected.destination}>Open authorization settings</Link></Button>}</>}</DialogContent></Dialog>
  </section>;
}

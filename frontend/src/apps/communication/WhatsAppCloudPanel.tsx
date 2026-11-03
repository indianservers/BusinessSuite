import { WhatsAppIcon } from "@/components/actions";
import RecordSectionNav from "@/components/RecordSectionNav";
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { MessageCircle, ShieldCheck, RefreshCw, Send, Inbox as InboxIcon, CheckCheck, Layers, Settings2, UserRound } from 'lucide-react';
import { api } from '@/services/api';
import { useAuthStore } from '@/store/authStore';
import ConnectionPanel from './whatsapp/ConnectionPanel';
import TemplatesPanel from './whatsapp/TemplatesPanel';
import Composer from './whatsapp/Composer';
import Inbox from './whatsapp/Inbox';
import ProfilePanel from './whatsapp/ProfilePanel';
import SentMessages from './whatsapp/SentMessages';
import { whatsappBase as base, whatsappError, type Status, type Template } from './whatsapp/types';
import './whatsapp/whatsapp.css';
import CustomerMatchButton from './CustomerMatchButton';

export default function WhatsAppCloudPanel() {
  const user=useAuthStore(state=>state.user);
  const scope=`${user?.id}:${sessionStorage.getItem('suite-organization')||'default'}:${sessionStorage.getItem('suite-branch')||'default'}`;
  return <WhatsAppWorkspace key={scope} scope={scope}/>;
}
function WhatsAppWorkspace({scope}:{scope:string}) {
  const cache=useQueryClient(),location=useLocation(),navigate=useNavigate();
  const [params,setParams]=useSearchParams();
  const routeTab=location.pathname.split('/').pop()||'';
  const tab=['inbox','templates','sent','profile','settings'].includes(routeTab)?routeTab:'send';
  const selected=/^[1-9]\d*$/.test(params.get('conversation')||'')?Number(params.get('conversation')):null;
  const setTab=(key:string)=>navigate(key==='send'?'/crm/whatsapp':`/crm/whatsapp/${key}`);
  const status=useQuery({queryKey:['whatsapp',scope,'status'],queryFn:async()=>(await api.get<Status>(base+'/status')).data});
  const templates=useQuery({queryKey:['whatsapp',scope,'templates'],enabled:!!status.data?.configured,queryFn:async()=>(await api.get<{items:Template[];hasMore:boolean}>(base+'/templates')).data});
  async function refresh(){await cache.invalidateQueries({queryKey:['whatsapp',scope]});}
  if(status.isPending)return <p className="wa-empty-note">Loading WhatsApp account…</p>;
  if(status.isError||!status.data)return <p role="alert" className="wa-error">{whatsappError(status.error)}</p>;
  const account=status.data;
  const tabs=[{key:'send',label:'Send message',icon:Send},{key:'inbox',label:'Inbox & delivery',icon:InboxIcon},{key:'sent',label:'Sent messages',icon:CheckCheck},{key:'templates',label:'Meta templates',icon:Layers},{key:'profile',label:'Business profile',icon:UserRound},...(account.canAdmin?[{key:'settings',label:'Account settings',icon:Settings2}]:[])];
  return <section className={`wa-workspace${tab==='inbox'?' wa-inbox-workspace':''}`}>
    <header className="wa-account-strip"><span className="wa-business-icon"><WhatsAppIcon className="h-[26px] w-[26px] text-[#25D366]"/></span><div className="wa-business-identity"><h2>WhatsApp Business</h2><p>{account.connection?.businessName||'Business Suite'} <span>·</span> {account.connection?.displayNumber||(account.configured?'Deployment sender connected':'No active sender')}</p></div><p className="wa-account-description">Connect each organization’s own account. Customers pay Meta for messaging; Indian Servers provides the CRM and API software.</p><span className={`wa-connection-status ${account.configured?'is-connected':''}`}><ShieldCheck size={16}/>{account.connection?.status.replace(/_/g,' ')||(account.configured?'Connected':'Setup required')}</span></header>
    <div className="wa-workspace-toolbar flex flex-wrap items-start gap-2"><div className="min-w-0 basis-full sm:basis-0 sm:flex-1"><RecordSectionNav value={tab} onChange={setTab} label="WhatsApp workspace" groups={[
      {label:'Compose',sections:tabs.filter(t=>t.key==='send').map(t=>({value:t.key,label:t.label}))},
      {label:'Messages',sections:tabs.filter(t=>['inbox','sent'].includes(t.key)).map(t=>({value:t.key,label:t.label}))},
      {label:'Templates',sections:tabs.filter(t=>t.key==='templates').map(t=>({value:t.key,label:t.label}))},
      {label:'Account',sections:tabs.filter(t=>['profile','settings'].includes(t.key)).map(t=>({value:t.key,label:t.label}))},
    ]}/></div><button className="wa-refresh flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border p-2" aria-label="Refresh WhatsApp workspace" title="Refresh" onClick={()=>void refresh()}><RefreshCw size={15}/></button>{account.configured&&tab==='inbox'&&account.canAdmin&&<div className="wa-match-action"><CustomerMatchButton/></div>}</div>
    {!account.webhookConfigured&&<p className="wa-error">Webhook verification settings are incomplete for this deployment.</p>}
    {!account.configured&&tab!=='settings'&&<p className="wa-empty-note">An organization administrator must connect and verify a WhatsApp sender in Account settings.</p>}
    {templates.isError&&tab!=='settings'&&<p role="alert" className="wa-error">Templates could not load: {whatsappError(templates.error)}</p>}
    {templates.data?.hasMore&&tab!=='settings'&&<p className="wa-muted-note">Showing the first 100 Meta templates.</p>}
    {account.configured&&tab==='send'&&<Composer scope={scope} templates={templates.data?.items||[]} admin={account.canAdmin} refresh={refresh} businessName={account.connection?.businessName||'Your business'}/>}
    {account.configured&&tab==='inbox'&&<Inbox scope={scope} selected={selected} onSelect={id=>setParams({conversation:String(id)})} onClear={()=>setParams({})} templates={templates.data?.items||[]} admin={account.canAdmin} refresh={refresh}/>}
    {account.configured&&tab==='templates'&&<TemplatesPanel templates={templates.data?.items||[]} admin={account.canAdmin} refresh={refresh}/>}
    {account.configured&&tab==='sent'&&<SentMessages scope={scope}/>}
    {account.configured&&tab==='profile'&&<ProfilePanel scope={scope} admin={account.canAdmin}/>}
    {tab==='settings'&&account.canAdmin&&<ConnectionPanel status={account} refresh={refresh}/>}
  </section>;
}

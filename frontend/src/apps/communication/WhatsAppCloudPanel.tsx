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
  return <section className="wa-workspace">
    <header className="wa-account-strip"><span className="wa-business-icon"><MessageCircle size={26}/></span><div className="wa-business-identity"><h2>WhatsApp Business</h2><p>{account.connection?.businessName||'Business Suite'} <span>·</span> {account.connection?.displayNumber||(account.configured?'Deployment sender connected':'No active sender')}</p></div><p className="wa-account-description">Connect each organization’s own account. Customers pay Meta for messaging; Indian Servers provides the CRM and API software.</p><span className={`wa-connection-status ${account.configured?'is-connected':''}`}><ShieldCheck size={16}/>{account.connection?.status.replace(/_/g,' ')||(account.configured?'Connected':'Setup required')}</span></header>
    <nav className="wa-workspace-tabs" aria-label="WhatsApp workspace">{tabs.map(({key,label,icon:Icon})=><button key={key} aria-current={tab===key?'page':undefined} className={tab===key?'is-active':''} onClick={()=>setTab(key)}><Icon size={14}/>{label}</button>)}<button className="wa-refresh" aria-label="Refresh WhatsApp workspace" title="Refresh" onClick={()=>void refresh()}><RefreshCw size={15}/></button></nav>
    {!account.webhookConfigured&&<p className="wa-error">Webhook verification settings are incomplete for this deployment.</p>}
    {!account.configured&&tab!=='settings'&&<p className="wa-empty-note">An organization administrator must connect and verify a WhatsApp sender in Account settings.</p>}
    {templates.isError&&tab!=='settings'&&<p role="alert" className="wa-error">Templates could not load: {whatsappError(templates.error)}</p>}
    {templates.data?.hasMore&&tab!=='settings'&&<p className="wa-muted-note">Showing the first 100 Meta templates.</p>}
    {account.configured&&tab==='send'&&<Composer scope={scope} templates={templates.data?.items||[]} admin={account.canAdmin} refresh={refresh} businessName={account.connection?.businessName||'Your business'}/>}
    {account.configured&&tab==='inbox'&&account.canAdmin&&<div className="mb-2"><CustomerMatchButton/></div>}
    {account.configured&&tab==='inbox'&&<Inbox scope={scope} selected={selected} onSelect={id=>setParams({conversation:String(id)})} onClear={()=>setParams({})} templates={templates.data?.items||[]} admin={account.canAdmin} refresh={refresh}/>}
    {account.configured&&tab==='templates'&&<TemplatesPanel templates={templates.data?.items||[]} admin={account.canAdmin} refresh={refresh}/>}
    {account.configured&&tab==='sent'&&<SentMessages scope={scope}/>}
    {account.configured&&tab==='profile'&&<ProfilePanel scope={scope} admin={account.canAdmin}/>}
    {tab==='settings'&&account.canAdmin&&<ConnectionPanel status={account} refresh={refresh}/>}
  </section>;
}

import { Button } from "@/components/ui/button";
import { WhatsAppIcon } from "@/components/actions";
import EngagementInbox from './center/EngagementInbox';
import CustomerCommunications from './CustomerCommunications';
import Analytics from './whatsapp/Analytics';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { ShieldCheck, RefreshCw, Send, Inbox as InboxIcon, CheckCheck, Layers, Settings2, UserRound } from 'lucide-react';
import { api } from '@/services/api';
import { useAuthStore } from '@/store/authStore';
import ConnectionPanel from './whatsapp/ConnectionPanel';
import TemplatesPanel from './whatsapp/TemplatesPanel';
import Composer, { type WhatsAppDraft } from './whatsapp/Composer';
import Inbox from './whatsapp/Inbox';
import ProfilePanel from './whatsapp/ProfilePanel';
import { whatsappBase as base, whatsappError, type Status, type Template } from './whatsapp/types';
import './whatsapp/whatsapp.css';

export default function WhatsAppCloudPanel({initialDraft,embedded=false}:{initialDraft?:WhatsAppDraft;embedded?:boolean} = {}) {
  const user=useAuthStore(state=>state.user);
  const location=useLocation();
  const draft=initialDraft || (location.state as {whatsappDraft?:WhatsAppDraft}|null)?.whatsappDraft;
  const scope=`${user?.id}:${sessionStorage.getItem('suite-organization')||'default'}:${sessionStorage.getItem('suite-branch')||'default'}`;
  return <WhatsAppWorkspace key={`${scope}:${draft?.key||'new'}`} scope={scope} initialDraft={draft} embedded={embedded}/>;
}
function WhatsAppWorkspace({scope,initialDraft,embedded=false}:{scope:string;initialDraft?:WhatsAppDraft;embedded?:boolean}) {
  const cache=useQueryClient(),location=useLocation(),navigate=useNavigate();
  const [params,setParams]=useSearchParams();
  const routeTab=location.pathname.split('/').pop()||'';
  const requestedTab=params.get('workspace');
  const tab=requestedTab&&['campaigns','analytics','send'].includes(requestedTab)?requestedTab:['templates','profile','settings'].includes(routeTab)?routeTab:initialDraft?'send':'inbox';
  const selected=/^[1-9]\d*$/.test(params.get('conversation')||'')?Number(params.get('conversation')):null;
  const setTab=(key:string)=>navigate(['campaigns','analytics','send'].includes(key)?`/crm/whatsapp?workspace=${key}${key==='campaigns'?'&customerTab=automations':''}`:key==='inbox'?'/crm/whatsapp':`/crm/whatsapp/${key}`);
  const status=useQuery({queryKey:['whatsapp',scope,'status'],queryFn:async()=>(await api.get<Status>(base+'/status')).data});
  const templates=useQuery({queryKey:['whatsapp',scope,'templates'],enabled:!!status.data?.configured && (['send','templates'].includes(tab) || (tab==='inbox'&&params.get('history')==='full')),queryFn:async()=>(await api.get<{items:Template[];hasMore:boolean}>(base+'/templates')).data});
  async function refresh(){await Promise.all([cache.invalidateQueries({queryKey:['whatsapp',scope]}),cache.invalidateQueries({queryKey:['communication-center',scope]})]);}
  if(status.isPending)return <p className="wa-empty-note">Loading WhatsApp account…</p>;
  if(status.isError||!status.data)return <p role="alert" className="wa-error">{whatsappError(status.error)}</p>;
  const account=status.data;
  const tabs=[{key:'inbox',label:'Inbox',icon:InboxIcon},{key:'templates',label:'Templates',icon:Layers},{key:'campaigns',label:'Campaigns',icon:Send},{key:'analytics',label:'Analytics',icon:CheckCheck},...(account.canAdmin?[{key:'settings',label:'Settings',icon:Settings2}]:[])];
  return <section className={`wa-workspace${tab==='inbox'?' wa-inbox-workspace':''}`}>
    <header hidden={embedded} className="wa-account-strip" style={embedded?{display:"none"}:undefined}><span className="wa-business-icon"><WhatsAppIcon className="h-[26px] w-[26px] text-[#25D366]"/></span><div className="wa-business-identity"><h2>WhatsApp Communication Hub</h2><p>{account.connection?.businessName||'Business Suite'} <span>·</span> {account.connection?.displayNumber||(account.configured?'Deployment sender connected':'No active sender')}</p></div><p className="wa-account-description">Connect each organization’s own account. Customers pay Meta for messaging; Indian Servers provides the CRM and API software.</p><span className={`wa-connection-status ${account.configured?'is-connected':''}`}><ShieldCheck size={16}/>{account.connection?.status.replace(/_/g,' ')||(account.configured?'Connected':'Setup required')}</span></header>
    <div className="wa-hub-toolbar"><nav hidden={embedded} style={embedded?{display:"none"}:undefined} className="wa-hub-tabs" aria-label="WhatsApp workspace">{tabs.map(({key,label,icon:Icon})=><button key={key} aria-current={tab===key?'page':undefined} onClick={()=>setTab(key)}><Icon size={15}/>{label}</button>)}</nav><button className="wa-refresh" aria-label="Refresh WhatsApp workspace" onClick={()=>void refresh()}><RefreshCw size={15}/></button>{account.configured&&<Button type="submit" variant="default" className="wa-new-message" onClick={()=>setTab('send')}><Send size={14}/>New message</Button>}</div>
    {!account.webhookConfigured&&<p className="wa-error">Webhook verification settings are incomplete for this deployment.</p>}
    {!account.configured&&tab!=='settings'&&<p className="wa-empty-note">An organization administrator must connect and verify a WhatsApp sender in Account settings.</p>}
    {templates.isError&&tab!=='settings'&&<p role="alert" className="wa-error">Templates could not load: {whatsappError(templates.error)}</p>}
    {templates.data?.hasMore&&tab!=='settings'&&<p className="wa-muted-note">Showing the first 100 Meta templates.</p>}
    {account.configured&&tab==='send'&&<Composer scope={scope} templates={templates.data?.items||[]} admin={account.canAdmin} refresh={refresh} businessName={account.connection?.businessName||'Your business'} initialDraft={initialDraft}/>}
    {account.configured&&tab==='inbox'&&params.get('history')!=='full'&&<EngagementInbox whatsappOnly/>}
    {account.configured&&tab==='inbox'&&params.get('history')==='full'&&<Inbox scope={scope} selected={selected} onSelect={id=>setParams({history:'full',conversation:String(id)})} onClear={()=>setParams({})} templates={templates.data?.items||[]} admin={account.canAdmin} refresh={refresh}/>}
    {account.configured&&tab==='templates'&&<TemplatesPanel syncedAt={templates.dataUpdatedAt} templates={templates.data?.items||[]} admin={account.canAdmin} refresh={refresh}/>}
    {account.configured&&tab==='campaigns'&&<CustomerCommunications whatsappOnly/>}
    {account.configured&&tab==='analytics'&&<Analytics/>}
    {account.configured&&tab==='profile'&&<ProfilePanel scope={scope} admin={account.canAdmin}/>}
    {tab==='settings'&&account.canAdmin&&<><ConnectionPanel status={account} refresh={refresh}/><ProfilePanel scope={scope} admin={account.canAdmin}/></>}
  </section>;
}

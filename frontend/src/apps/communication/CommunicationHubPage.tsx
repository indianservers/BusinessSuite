import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import CompactForm from "@/components/forms/CompactForm";
import RichTextEditor, { richTextPlainText } from "@/components/rich-text/LazyRichText";
import { contentToHtml, RICH_TEXT_PREFIX } from "@/components/rich-text/content";
import { Input } from "@/components/ui/input";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { useState } from "react";
import { useMutation,useQuery,useQueryClient } from "@tanstack/react-query";
import { Home,Inbox,Mail,Layers,Megaphone,Settings2,MessageCircle } from "lucide-react";
import { useLocation,useNavigate } from "react-router-dom";
import { communicationApi } from "./api";
import { Button } from "@/components/ui/button";
import { Card,CardContent } from "@/components/ui/card";
import { canAccessRoute } from "@/lib/roles";
import WhatsAppCloudPanel from './WhatsAppCloudPanel';
import CustomerCommunications from './CustomerCommunications';
import SendReminders from './center/SendReminders';
import BirthdaysPage from '@/shared/master-data/BirthdaysPage';
import CommunicationHome from './center/CommunicationHome';
import EngagementInbox from './center/EngagementInbox';
import CustomerMatchingReview from './center/CustomerMatchingReview';
import EmailComposer from './center/EmailComposer';
import CampaignWorkspace from './center/CampaignWorkspace';
import GuidedTools from './center/GuidedTools';
import TimelineExplorer from './center/TimelineExplorer';
import DeliveryWorkspace from './center/DeliveryWorkspace';
import { usePreference,useCenterScope } from './center/shared';
import './center/center.css';

type Destination={label:string;path:string;section:string};
const groups=[
 {key:'hub',label:'Overview',icon:Home,path:'/crm/communication-hub',children:[] as Destination[]},
 {key:'inbox',label:'Inbox',icon:Inbox,path:'/crm/communication-hub?section=inbox',children:[{label:'All channels',path:'/crm/communication-hub?section=inbox',section:'inbox'},{label:'WhatsApp inbox',path:'/crm/whatsapp/inbox',section:'whatsapp-inbox'},{label:'Customer matching',path:'/crm/communication-hub?section=matching',section:'matching'},{label:'Customer workspace',path:'/crm/communication-hub?section=customers',section:'customers'}]},
 {key:'reminders',label:'Send reminders',icon:MessageCircle,path:'/crm/send-reminders',children:[] as Destination[]},
 {key:'birthdays',label:'Contact birthdays',icon:Home,path:'/crm/birthdays',children:[] as Destination[]},
 {key:'compose',label:'Compose',icon:Mail,path:'/crm/emails',children:[{label:'Email',path:'/crm/emails',section:'emails'},{label:'WhatsApp',path:'/crm/whatsapp',section:'whatsapp-send'}]},
 {key:'templates',label:'Templates',icon:Layers,path:'/crm/email-templates',children:[{label:'Email templates',path:'/crm/email-templates',section:'templates'},{label:'WhatsApp templates',path:'/crm/whatsapp/templates',section:'whatsapp-templates'}]},
 {key:'campaigns',label:'Campaigns',icon:Megaphone,path:'/crm/campaigns',children:[{label:'Email campaigns',path:'/crm/campaigns',section:'campaigns'},{label:'Customer automations',path:'/crm/communication-hub?section=customers&customerTab=automations',section:'automations'}]},
 {key:'settings',label:'Settings & tools',icon:Settings2,path:'/crm/consents',children:[{label:'Consent',path:'/crm/consents',section:'consents'},{label:'Webforms',path:'/crm/webforms',section:'webforms'},{label:'Auto-responses',path:'/crm/auto-responses',section:'auto-responses'},{label:'Delivery workspace',path:'/crm/delivery-logs',section:'delivery-logs'},{label:'Timeline',path:'/crm/communication-timeline',section:'timeline'},{label:'WhatsApp connection',path:'/crm/whatsapp/settings',section:'whatsapp-settings'},{label:'Business profile',path:'/crm/whatsapp/profile',section:'whatsapp-profile'}]}
];
function sectionFor(path:string){if(path.includes('/send-reminders'))return 'reminders';if(path.includes('/birthdays'))return 'birthdays';if(path.includes('/email-templates'))return 'templates';if(path.includes('/emails'))return 'emails';if(path.includes('/webforms'))return 'webforms';if(path.includes('/campaigns'))return 'campaigns';if(path.includes('/consents'))return 'consents';if(path.includes('/whatsapp'))return 'whatsapp';if(path.includes('/auto-responses'))return 'auto-responses';if(path.includes('/delivery-logs'))return 'delivery-logs';if(path.includes('/communication-timeline'))return 'timeline';return 'hub';}
export default function CommunicationHubPage(){
 const location=useLocation(),navigate=useNavigate(),user=useAuthStore(s=>s.user),query=new URLSearchParams(location.search),scope=useCenterScope();
 const aliases:Record<string,string>={'email-templates':'templates',logs:'delivery-logs','delivery-logs':'delivery-logs'};
 const requested=query.get('section')||query.get('tab')||query.get('operation')||'';
 const section=location.pathname.includes('/whatsapp')?'whatsapp':requested?(aliases[requested]||requested):sectionFor(location.pathname);
 const waTab=location.pathname.split('/').pop();
 const active=section==='whatsapp'?`whatsapp-${waTab==='whatsapp'?'send':waTab}`:section;
 const group=['reminders','birthdays'].includes(section)?section:section==='whatsapp'?(waTab==='templates'?'templates':['settings','profile'].includes(waTab||'')?'settings':waTab==='whatsapp'?'compose':'inbox'):['inbox','matching','customers'].includes(section)?query.get('customerTab')==='automations'?'campaigns':'inbox':section==='emails'?'compose':section==='templates'?'templates':section==='campaigns'?'campaigns':section==='hub'?'hub':'settings';
 const current=groups.find(g=>g.key===group)!;
 const accessible=(path:string)=>canAccessRoute(path.split('?')[0],user?.role,user?.is_superuser);
 if(section==='whatsapp')return <div className="cc-center cc-whatsapp-hub" key={scope}><WhatsAppCloudPanel/></div>;
 return <div className={`cc-center${section==='whatsapp'&&waTab==='inbox'?' cc-whatsapp-inbox':''}`} key={scope}><header className="cc-shell-heading"><div className="cc-shell-title"><span><MessageCircle size={23}/></span><h1>Communication Center</h1></div><p>Customer conversations, campaigns and delivery work in one place.</p><nav className="cc-primary-nav" aria-label="Communication sections">{groups.filter(g=>accessible(g.path)||g.children.some(c=>accessible(c.path))).map(({key,label,path,icon:Icon})=><button key={key} aria-current={key===group?'page':undefined} onClick={()=>navigate(path)}><Icon size={16}/>{label}</button>)}</nav>{current.children.length>0&&<nav className="cc-secondary-nav" aria-label="Communication tools">{current.children.filter(c=>accessible(c.path)).map(child=><button key={child.path} aria-current={child.section===active||child.section==='automations'&&query.get('customerTab')==='automations'?'page':undefined} onClick={()=>navigate(child.path)}>{child.label}</button>)}</nav>}</header><div className="cc-shell-content">{section==='reminders'?<SendReminders/>:section==='birthdays'?<BirthdaysPage source="crm"/>:section==='hub'?<CommunicationHome/>:section==='inbox'?<EngagementInbox/>:section==='matching'?<CustomerMatchingReview/>:section==='customers'?<CustomerCommunications/>:section==='templates'?<Templates/>:section==='emails'?<EmailComposer/>:section==='campaigns'?<CampaignWorkspace/>:section==='webforms'?<GuidedTools key="webforms" mode="webforms"/>:section==='auto-responses'?<GuidedTools key="auto-responses" mode="auto-responses"/>:section==='consents'?<GuidedTools key="consents" mode="consents"/>:section==='timeline'?<TimelineExplorer/>:section==='whatsapp'?<WhatsAppCloudPanel/>:['delivery-logs','deliveries'].includes(section)?<DeliveryWorkspace/>:<CommunicationHome/>}</div></div>;
}

function Templates() {
 const [templateOpen,setTemplateOpen]=useState(false);
  const qc = useQueryClient();
  const user = useAuthStore(state => state.user);
  const canManage = Boolean(user?.is_superuser || !user?.access?.managed || Object.values(user?.access?.grants || {}).some(grant => grant.enabled && grant.permissions.includes("communication_templates_manage")));
  const query = useQuery({queryKey:["communication-templates"],queryFn:communicationApi.templates});
  const [id,setId]=useState<number | null>(null);
  const [draft,setDraft]=useState({name:"",subject:"",content:"",module_name:"lead"});
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [search,setSearch]=useState(''),[favoritesOnly,setFavoritesOnly]=useState(false),[favorites,setFavorites]=usePreference<number[]>('favorite-email-templates',[]);
  const mutation=useMutation({mutationFn:async()=>{
    const payload={name:draft.name.trim(),subject:draft.subject.trim(),body_html:draft.content,body_text:richTextPlainText(draft.content),module_name:draft.module_name,template_type:"email",active:true};
    return id ? api.put(`/communication/email-templates/${id}`,payload) : communicationApi.createTemplate(payload);
  },onSuccess:()=>{setNotice("Template saved");setError("");qc.invalidateQueries({queryKey:["communication-templates"]});},onError:(e:any)=>setError(typeof e.response?.data?.detail === "string" ? e.response.data.detail : "Could not save. Your draft is retained.")});
  return <div className="grid gap-5 xl:grid-cols-[18rem_minmax(0,1fr)]">
    <Card><CardContent className="space-y-3 p-4"><h2 className="font-semibold">Email templates</h2><Button available={!!(canManage)} variant="outline" disabled={!canManage} onClick={()=>{setId(null);setTemplateOpen(true);setDraft({name:"",subject:"",content:"",module_name:"lead"});setNotice("");setError("");}}>New template</Button>
      {query.isLoading && <p role="status">Loading templates...</p>}{query.isError && <p role="alert">Could not load templates.</p>}
      <Input aria-label="Search email templates" placeholder="Template name or subject" value={search} onChange={e=>setSearch(e.target.value)}/><label className="flex-row items-center"><input type="checkbox" checked={favoritesOnly} onChange={e=>setFavoritesOnly(e.target.checked)}/>Favourites only</label>
      {query.data?.items.filter(item=>(String(item.name)+' '+String(item.subject)).toLowerCase().includes(search.toLowerCase())&&(!favoritesOnly||favorites.includes(Number(item.id)))).map(item=><button type="button" key={item.id} className={`block w-full rounded-lg border p-3 text-left text-sm ${id===item.id ? "border-primary bg-primary/5" : "hover:bg-muted"}`} onClick={()=>{setId(item.id!);setTemplateOpen(true);setDraft({name:String(item.name||""),subject:String(item.subject||""),content:item.body_html ? String(item.body_html) : RICH_TEXT_PREFIX + contentToHtml(String(item.body_text||""), "plain"),module_name:String(item.module_name||"lead")});setNotice("");setError("");}}><strong>{favorites.includes(Number(item.id))?'★ ':''}{String(item.name)}</strong><span className="block text-xs text-muted-foreground">{String(item.subject||"")}</span></button>)}
    </CardContent></Card>
    <Card><CardContent className="p-5"><SmartCreateSection title={id ? "Edit email template" : "Create email template"} autoOpen={templateOpen} onClose={() => setTemplateOpen(false)} size="large"><CompactForm className="space-y-4" onSubmit={event=>{event.preventDefault();setNotice("");mutation.mutate();}}>
      <h2 className="text-lg font-semibold">{id ? "Edit email template" : "Create email template"}</h2>
      {id&&<Button type="button" variant="ghost" size="sm" onClick={()=>setFavorites(favorites.includes(id)?favorites.filter(value=>value!==id):[...favorites,id])}>{favorites.includes(id)?'Remove from favourites':'Favourite template'}</Button>}
      <p className="text-sm text-muted-foreground">Write a reusable message. Merge fields such as {"{{name}}"} remain available when composing an email.</p>
      <div className="grid gap-4 sm:grid-cols-2"><label className="space-y-1 text-sm">Template name<Input required maxLength={180} minLength={2} value={draft.name} disabled={!canManage || mutation.isPending} onChange={event=>setDraft({...draft,name:event.target.value})}/></label><label className="space-y-1 text-sm">Subject<Input required maxLength={240} value={draft.subject} disabled={!canManage || mutation.isPending} onChange={event=>setDraft({...draft,subject:event.target.value})}/></label></div>
      <RichTextEditor key={id ?? "new"} label="Email template content" legacyFormat="html" variant="document" value={draft.content} onChange={content=>setDraft({...draft,content})} readOnly={!canManage} disabled={mutation.isPending} maxLength={20000}/>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}{notice && <p role="status" className="text-sm text-emerald-700">{notice}</p>}
      <Button available={!!(canManage)} type="submit" disabled={!canManage || mutation.isPending}>{mutation.isPending ? "Saving..." : "Save template"}</Button>
    </CompactForm></SmartCreateSection></CardContent></Card>
  </div>;
}

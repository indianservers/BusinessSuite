import RichTextEditor, { RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import { contentToHtml, RICH_TEXT_PREFIX } from "@/components/rich-text/content";
import { Input } from "@/components/ui/input";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import type React from "react";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Mail, Megaphone, MessageCircle, ScrollText, Send, ShieldCheck, TableProperties, Users } from "lucide-react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { communicationApi, type CommunicationList, type CommunicationRecord } from "./api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { canAccessRoute } from "@/lib/roles";

type SectionKey = "hub" | "templates" | "emails" | "webforms" | "campaigns" | "consents" | "whatsapp" | "auto-responses" | "delivery-logs" | "timeline";

const sections: Array<{ key: SectionKey; label: string; path: string; icon: typeof Mail }> = [
  { key: "hub", label: "Hub", path: "/crm/communication-hub", icon: TableProperties },
  { key: "templates", label: "Templates", path: "/crm/email-templates", icon: FileText },
  { key: "emails", label: "Emails", path: "/crm/emails", icon: Send },
  { key: "webforms", label: "Webforms", path: "/crm/webforms", icon: Users },
  { key: "campaigns", label: "Campaigns", path: "/crm/campaigns", icon: Megaphone },
  { key: "consents", label: "Consent", path: "/crm/consents", icon: ShieldCheck },
  { key: "whatsapp", label: "WhatsApp", path: "/crm/whatsapp", icon: MessageCircle },
  { key: "auto-responses", label: "Auto Responses", path: "/crm/auto-responses", icon: Send },
  { key: "delivery-logs", label: "Delivery Logs", path: "/crm/delivery-logs", icon: ScrollText },
  { key: "timeline", label: "Timeline", path: "/crm/communication-timeline", icon: TableProperties },
];

function activeSection(pathname: string): SectionKey {
  if (pathname.includes("/email-templates")) return "templates";
  if (pathname.includes("/emails")) return "emails";
  if (pathname.includes("/webforms")) return "webforms";
  if (pathname.includes("/campaigns")) return "campaigns";
  if (pathname.includes("/consents")) return "consents";
  if (pathname.includes("/whatsapp")) return "whatsapp";
  if (pathname.includes("/auto-responses")) return "auto-responses";
  if (pathname.includes("/delivery-logs")) return "delivery-logs";
  if (pathname.includes("/communication-timeline")) return "timeline";
  return "hub";
}

function actionError(error: unknown) {
  if (error instanceof Error) return error.message;
  return "Action failed. Please try again.";
}

export default function CommunicationHubPage() {
  const user = useAuthStore(state => state.user);
  const location = useLocation();
  const navigate = useNavigate();
  const params = useParams();
  const query = new URLSearchParams(location.search);
  const requested=query.get("section")||query.get("tab")||query.get("operation")||"";
  const alias:Record<string,SectionKey>={templates:"templates","email-templates":"templates",emails:"emails",campaigns:"campaigns",logs:"delivery-logs","delivery-logs":"delivery-logs",timeline:"timeline"};
  const active = requested?(sections.find(s=>s.path===requested)?.key||alias[requested]||activeSection(location.pathname)):activeSection(location.pathname);
  return (
    <div className="space-y-6">
      <div className="border-b bg-background px-4 py-5 sm:px-6 lg:px-8">
        <p className="text-sm font-medium uppercase text-muted-foreground">CRM</p>
        <h1 className="text-2xl font-semibold">Communication Hub</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">Templates, individual emails, public webforms, auto-responses, campaigns, consent, WhatsApp placeholders, timeline, and delivery analytics.</p>
        <nav aria-label="Communication sections" className="mt-4 flex gap-2 overflow-x-auto pb-1">
          {sections.filter(item => canAccessRoute(item.path, user?.role, user?.is_superuser)).map((item) => {
            const Icon = item.icon;
            return <Button key={item.key} aria-current={active === item.key ? "page" : undefined} variant={active === item.key ? "default" : "outline"} size="sm" onClick={() => navigate(item.path)}><Icon className="h-4 w-4" />{item.label}</Button>;
          })}
        </nav>
      </div>
      <div className="px-4 pb-8 sm:px-6 lg:px-8">
        {active === "hub" ? <Hub /> : null}
        {active === "templates" ? <Templates /> : null}
        {active === "emails" ? <Emails /> : null}
        {active === "webforms" ? <Webforms selectedId={params.id} /> : null}
        {active === "campaigns" ? <Campaigns selectedId={params.id} /> : null}
        {active === "consents" ? <Consents /> : null}
        {active === "whatsapp" ? <WhatsApp /> : null}
        {active === "auto-responses" ? <AutoResponses /> : null}
        {active === "delivery-logs" ? <GenericSection title="Delivery Logs" description="Provider attempts, blocked sends, failures, and stubbed delivery evidence." queryKey="communication-logs" queryFn={communicationApi.deliveryLogs} /> : null}
        {active === "timeline" ? <Timeline /> : null}
      </div>
    </div>
  );
}

function useRefresh(key: string) {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: [key] });
}

function Hub() {
  const info = useQuery({ queryKey: ["communication-info"], queryFn: communicationApi.moduleInfo });
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {["Templates", "Emails", "Webforms", "Campaigns", "Consent", "Timeline"].map((item) => (
        <Card key={item}><CardContent className="p-4"><p className="font-medium">{item}</p><p className="mt-1 text-sm text-muted-foreground">Operational and auditable CRM communication metadata.</p><Badge className="mt-3" variant="outline">{info.data?.module || "communication"}</Badge></CardContent></Card>
      ))}
    </div>
  );
}

function Templates() {
  const qc = useQueryClient();
  const user = useAuthStore(state => state.user);
  const canManage = Boolean(user?.is_superuser || !user?.access?.managed || Object.values(user?.access?.grants || {}).some(grant => grant.enabled && grant.permissions.includes("communication_templates_manage")));
  const query = useQuery({queryKey:["communication-templates"],queryFn:communicationApi.templates});
  const [id,setId]=useState<number | null>(null);
  const [draft,setDraft]=useState({name:"",subject:"",content:"",module_name:"lead"});
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const mutation=useMutation({mutationFn:async()=>{
    const payload={name:draft.name.trim(),subject:draft.subject.trim(),body_html:draft.content,body_text:richTextPlainText(draft.content),module_name:draft.module_name,template_type:"email",active:true};
    return id ? api.put(`/communication/email-templates/${id}`,payload) : communicationApi.createTemplate(payload);
  },onSuccess:()=>{setNotice("Template saved");setError("");qc.invalidateQueries({queryKey:["communication-templates"]});},onError:(e:any)=>setError(typeof e.response?.data?.detail === "string" ? e.response.data.detail : "Could not save. Your draft is retained.")});
  return <div className="grid gap-5 xl:grid-cols-[18rem_minmax(0,1fr)]">
    <Card><CardContent className="space-y-3 p-4"><h2 className="font-semibold">Email templates</h2><Button variant="outline" disabled={!canManage} onClick={()=>{setId(null);setDraft({name:"",subject:"",content:"",module_name:"lead"});setNotice("");setError("");}}>New template</Button>
      {query.isLoading && <p role="status">Loading templates...</p>}{query.isError && <p role="alert">Could not load templates.</p>}
      {query.data?.items.map(item=><button type="button" key={item.id} className={`block w-full rounded-lg border p-3 text-left text-sm ${id===item.id ? "border-primary bg-primary/5" : "hover:bg-muted"}`} onClick={()=>{setId(item.id!);setDraft({name:String(item.name||""),subject:String(item.subject||""),content:item.body_html ? String(item.body_html) : RICH_TEXT_PREFIX + contentToHtml(String(item.body_text||""), "plain"),module_name:String(item.module_name||"lead")});setNotice("");setError("");}}><strong>{String(item.name)}</strong><span className="block text-xs text-muted-foreground">{String(item.subject||"")}</span></button>)}
    </CardContent></Card>
    <Card><CardContent className="p-5"><form className="space-y-4" onSubmit={event=>{event.preventDefault();setNotice("");mutation.mutate();}}>
      <h2 className="text-lg font-semibold">{id ? "Edit email template" : "Create email template"}</h2>
      <p className="text-sm text-muted-foreground">Write a reusable message. Merge fields such as {"{{name}}"} remain available when composing an email.</p>
      <div className="grid gap-4 sm:grid-cols-2"><label className="space-y-1 text-sm">Template name<Input required maxLength={180} minLength={2} value={draft.name} disabled={!canManage || mutation.isPending} onChange={event=>setDraft({...draft,name:event.target.value})}/></label><label className="space-y-1 text-sm">Subject<Input required maxLength={240} value={draft.subject} disabled={!canManage || mutation.isPending} onChange={event=>setDraft({...draft,subject:event.target.value})}/></label></div>
      <RichTextEditor key={id ?? "new"} label="Email template content" legacyFormat="html" variant="document" value={draft.content} onChange={content=>setDraft({...draft,content})} readOnly={!canManage} disabled={mutation.isPending} maxLength={20000}/>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}{notice && <p role="status" className="text-sm text-emerald-700">{notice}</p>}
      <Button type="submit" disabled={!canManage || mutation.isPending}>{mutation.isPending ? "Saving..." : "Save template"}</Button>
    </form></CardContent></Card>
  </div>;
}

function Emails() {
 const [search,setSearch]=useState("");const [matches,setMatches]=useState<any[]>([]);const [record,setRecord]=useState<any>();const [to,setTo]=useState("");const [subject,setSubject]=useState("");const [body,setBody]=useState("");const [variables,setVariables]=useState<Record<string,string>>({});const [review,setReview]=useState(false);const [busy,setBusy]=useState(false);const [error,setError]=useState("");const [notice,setNotice]=useState("");
 const templates=useQuery({queryKey:["communication-templates"],queryFn:communicationApi.templates});const consents=useQuery({queryKey:["communication-consents"],queryFn:communicationApi.consents});
 const timeline=useQuery({queryKey:["communication-compose-timeline",record?.entity,record?.id],enabled:!!record,queryFn:()=>communicationApi.timeline(record.entity==="companies"?"company":record.entity.replace(/s$/,""),record.id)});
 useEffect(()=>{if(search.length<2){setMatches([]);return;}const controller=new AbortController();const t=setTimeout(()=>{void api.get("/crm/productivity/search",{params:{q:search},signal:controller.signal}).then(r=>setMatches(r.data.items.filter((i:any)=>["leads","contacts","companies"].includes(i.entity)))).catch(()=>{});},300);return()=>{clearTimeout(t);controller.abort();};},[search]);
 const names=[...new Set((subject+" "+body).match(/\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/g)||[])].map(v=>v.replace(/[{}\s]/g,""));const missing=names.filter(n=>!variables[n]?.trim());const render=(text:string)=>text.replace(/\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/g,(_,key)=>variables[key]||"");
 const preferences=(consents.data?.items||[]).filter(c=>String(c.email||"").toLowerCase()===to.toLowerCase());const blocked=preferences.some(c=>["opted_out","denied","revoked"].includes(String(c.status)));
 async function send(draft=false){if(!record)return;setBusy(true);setError("");try{const payload={related_record_type:record.entity==="companies"?"company":record.entity.replace(/s$/,""),related_record_id:record.id,to_email:to,subject:render(subject),body:render(body)};const response=await(draft?communicationApi.draftEmail(payload):communicationApi.sendEmail(payload));setNotice(`${draft?"Draft saved":"Provider result"}: ${String(response.status||"recorded")}. Delivered and Replied require provider evidence.`);setReview(false);void timeline.refetch();}catch(e:any){setError(typeof e.response?.data?.detail==="string"?e.response.data.detail:actionError(e));}finally{setBusy(false);}}
 const changed=()=>setReview(false);
 return <div className="space-y-4"><h2 className="text-xl font-semibold">Individual Emails</h2><p className="text-sm text-muted-foreground">Choose a real CRM recipient, compose, then review before sending. Draft → Queued → Sent → Delivered → Replied are distinct states; Failed requires correction or retry.</p><Input aria-label="Find email recipient" placeholder="Find a lead, contact or company…" value={search} onChange={e=>setSearch(e.target.value)}/>{matches.map(i=><button key={`${i.entity}-${i.id}`} className="block w-full rounded border p-2 text-left text-sm" onClick={()=>{setRecord(i);setTo(i.email||"");setVariables(v=>({...v,name:i.name,email:i.email||""}));setMatches([]);setSearch("");changed();}}>{i.name} · {i.email||"No email"} · {i.entity}</button>)}<p className="text-sm">Linked record: {record?`${record.name} (#${record.id})`:"Choose a recipient record"}</p><label className="block text-sm">Recipient email<Input type="email" value={to} onChange={e=>{setTo(e.target.value);changed();}}/></label><label className="block text-sm">Template<select className="block w-full rounded border p-2" onChange={e=>{const t=templates.data?.items.find(t=>Number(t.id)===Number(e.target.value));if(t){setSubject(String(t.subject||""));setBody(String(t.body_text||richTextPlainText(String(t.body_html||""))));changed();}}}><option value="">Write without a template</option>{templates.data?.items.map(t=><option value={t.id} key={t.id}>{t.name}</option>)}</select></label><label className="block text-sm">Subject<Input value={subject} onChange={e=>{setSubject(e.target.value);changed();}}/></label><label className="block text-sm">Message<textarea className="block min-h-36 w-full rounded border p-3" value={body} onChange={e=>{setBody(e.target.value);changed();}}/></label>{names.map(n=><label key={n} className="block text-sm">Template variable: {n}<Input value={variables[n]||""} onChange={e=>{setVariables(v=>({...v,[n]:e.target.value}));changed();}}/></label>)}<p className="text-sm">Email eligibility: {blocked?"Opted out — sending disabled":preferences.length?preferences.map(c=>String(c.status)).join(", "):"No preference record visible; the server checks opt-outs and provider availability when sending."}</p><p className="text-xs">Attachments: none in this composer. Quotations and invoices use their document delivery actions to validate the document version and attachments.</p>{error&&<p role="alert" className="text-destructive">{error} Your draft is preserved.</p>}{notice&&<p role="status">{notice}</p>}<div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy||!record||!to||!subject||missing.length>0} onClick={()=>void send(true)}>Save draft</Button><Button disabled={busy||blocked||!record||!to||!subject||!body||missing.length>0} onClick={()=>setReview(true)}>Preview before sending</Button></div>{review&&<section className="space-y-2 rounded border p-4"><h3 className="font-semibold">Review email</h3><p>To: {to} · Channel: Email · Attachments: none</p><p>Subject: {render(subject)}</p><pre className="whitespace-pre-wrap text-sm">{render(body)}</pre><p className="text-xs">Variables: {names.map(n=>`${n} = ${variables[n]}`).join("; ")||"None"}</p><Button disabled={busy||blocked} onClick={()=>void send()}>Confirm send to reviewed recipient</Button></section>}<h3 className="font-semibold">Communication timeline</h3>{timeline.data?.items.map((i,index)=><article key={String(i.id||index)} className="rounded border p-3 text-sm"><strong>{String(i.subject||i.title||i.channel||"Message")}</strong><p>Status: {String(i.status||"Recorded")}</p></article>)}</div>;
}

function Webforms({ selectedId }: { selectedId?: string }) {
  const { toast } = useToast();
  const query = useQuery({ queryKey: ["communication-webforms"], queryFn: communicationApi.webforms });
  const refresh = useRefresh("communication-webforms");
  const slug = `lead-capture-${selectedId || "phase-6"}`;
  const create = useMutation({
    mutationFn: () => communicationApi.createWebform({ name: "Lead Capture", target_module: "lead", public_slug: slug, fields_json: [{ key: "first_name", label: "First Name", required: true }, { key: "email", label: "Email", required: true }], mapping_json: { first_name: "first_name", email: "email", phone: "phone" }, active: true }),
    onSuccess: () => { toast({ title: "Webform saved" }); refresh(); },
  });
  const submit = useMutation({
    mutationFn: () => communicationApi.submitWebform(slug, { values: { first_name: "Website", last_name: "Lead", email: `website-${Date.now()}@example.com`, phone: "9999999999" }, anti_spam: "" }),
    onSuccess: (data: CommunicationRecord) => toast({ title: `Submission ${String(data.created_record_type)}` }),
    onError: (error) => toast({ title: actionError(error), variant: "destructive" }),
  });
  return <SectionFrame title="Webforms" description="Public slug forms map submissions into CRM records with duplicate detection and timeline evidence." action="Create Webform" onAction={() => create.mutate()} query={query}><Button variant="outline" onClick={() => submit.mutate()}>Submit Demo Lead</Button></SectionFrame>;
}

function Campaigns({ selectedId }: { selectedId?: string }) {
  const { toast } = useToast();
  const query = useQuery({ queryKey: ["communication-campaigns"], queryFn: communicationApi.campaigns });
  const refresh = useRefresh("communication-campaigns");
  const create = useMutation({
    mutationFn: async () => {
      const template = await communicationApi.createTemplate({ name: `Campaign Template ${Date.now()}`, subject: "Campaign {{name}}", body_text: "Hello {{name}}", module_name: "lead", active: true });
      return communicationApi.createCampaign({ name: `Nurture Campaign ${selectedId || "Phase 6"}`, type: "email", template_id: template.id, segment_json: { source: "lead", limit: 10 }, status: "draft" });
    },
    onSuccess: () => { toast({ title: "Campaign saved" }); refresh(); },
  });
  const firstId = Number(query.data?.items?.[0]?.id || 0);
  const preview = useMutation({ mutationFn: () => communicationApi.previewCampaign(firstId), onSuccess: (data: CommunicationRecord) => toast({ title: `Preview ${String(data.total)} recipients` }), onError: (error) => toast({ title: actionError(error), variant: "destructive" }) });
  const send = useMutation({ mutationFn: () => communicationApi.sendCampaign(firstId), onSuccess: (data: CommunicationRecord) => { toast({ title: `Campaign ${String(data.status)}` }); refresh(); }, onError: (error) => toast({ title: actionError(error), variant: "destructive" }) });
  const schedule = useMutation({ mutationFn: () => communicationApi.scheduleCampaign(firstId, { scheduled_at: new Date(Date.now() + 60 * 60 * 1000).toISOString() }), onSuccess: () => { toast({ title: "Campaign scheduled" }); refresh(); }, onError: (error) => toast({ title: actionError(error), variant: "destructive" }) });
  const cancel = useMutation({ mutationFn: () => communicationApi.cancelCampaign(firstId), onSuccess: () => { toast({ title: "Campaign cancelled" }); refresh(); }, onError: (error) => toast({ title: actionError(error), variant: "destructive" }) });
  return <SectionFrame title="Campaigns" description="Segment, preview, consent-check, rate-limit, send, schedule, cancel, and track CRM campaigns." action="Create Campaign" onAction={() => create.mutate()} query={query}><Button variant="outline" disabled={!firstId || preview.isPending} onClick={() => preview.mutate()}>Preview</Button><Button variant="outline" disabled={!firstId || schedule.isPending} onClick={() => schedule.mutate()}>Schedule</Button><Button variant="outline" disabled={!firstId || cancel.isPending} onClick={() => cancel.mutate()}>Cancel</Button><Button variant="outline" disabled={!firstId || send.isPending} onClick={() => send.mutate()}>Send</Button></SectionFrame>;
}

function Consents() {
  const { toast } = useToast();
  return <GenericSection title="Consent and Opt-out" description="Consent status and opt-out records block outbound communication before provider delivery." queryKey="communication-consents" queryFn={communicationApi.consents} action="Opt Out" mutation={() => communicationApi.optOut({ email: "blocked@example.com", channel: "email", reason: "Customer request", source: "CRM" }).then((data) => { toast({ title: "Opt-out saved" }); return data; })} />;
}

function WhatsApp() {
  return <GenericSection title="WhatsApp Placeholder" description="Template management only. Delivery remains placeholder-only until a real WhatsApp provider is configured." queryKey="communication-whatsapp" queryFn={communicationApi.whatsappTemplates} action="Create WhatsApp Template" mutation={() => communicationApi.createWhatsAppTemplate({ name: "Reminder", template_key: "crm_reminder", body_text: "Hello {{name}}, this is a CRM reminder.", active: true })} />;
}

function AutoResponses() {
  return <GenericSection title="Auto Response Rules" description="Webform and campaign events can trigger templated CRM follow-ups with auditable delivery logs." queryKey="communication-auto-responses" queryFn={communicationApi.autoResponseRules} action="Create Auto Response" mutation={() => communicationApi.createAutoResponseRule({ name: "Lead webform acknowledgement", trigger_event: "webform.submitted", template_id: 1, active: true, delay_minutes: 0 })} />;
}

function Timeline() {
  return <GenericSection title="Communication Timeline" description="Unified email, campaign, webform, consent, and WhatsApp records for the selected CRM object." queryKey="communication-timeline-lead-1" queryFn={() => communicationApi.timeline("lead", 1)} />;
}

function GenericSection({ title, description, queryKey, queryFn, action, mutation }: { title: string; description: string; queryKey: string; queryFn: () => Promise<CommunicationList>; action?: string; mutation?: () => Promise<unknown> }) {
  const { toast } = useToast();
  const query = useQuery({ queryKey: [queryKey], queryFn });
  const refresh = useRefresh(queryKey);
  const create = useMutation({ mutationFn: mutation || (() => Promise.resolve()), onSuccess: () => { toast({ title: `${title.split(" ")[0]} saved` }); refresh(); }, onError: (error) => toast({ title: actionError(error), variant: "destructive" }) });
  return <SectionFrame title={title} description={description} action={action} onAction={action ? () => create.mutate() : undefined} query={query} />;
}

function SectionFrame({ title, description, action, onAction, query, children }: { title: string; description: string; action?: string; onAction?: () => void; query: ReturnType<typeof useQuery<CommunicationList>>; children?: React.ReactNode }) {
  const items = useMemo(() => query.data?.items || [], [query.data]);
  return (
    <div className="space-y-4">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div><h2 className="text-lg font-semibold">{title}</h2><p className="text-sm text-muted-foreground">{description}</p></div>
        <div className="flex flex-wrap gap-2">{children}{action ? <Button onClick={onAction}>{action}</Button> : null}</div>
      </div>
      {query.isLoading ? <div className="rounded-md border bg-card px-4 py-3 text-sm text-muted-foreground">Loading communication records...</div> : null}
      {query.isError ? <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">Communication records could not be loaded.</div> : null}
      {!query.isLoading && !items.length ? <div className="rounded-md border bg-card px-4 py-6 text-sm text-muted-foreground">No communication records yet.</div> : null}
      <div className="grid gap-3 md:grid-cols-2">
        {items.map((item) => <Card key={String(item.id)}><CardContent className="flex items-start justify-between gap-3 p-4"><div><p className="font-medium">{String(item.name || item.subject || item.email || item.to_email || `Record ${item.id}`)}</p><p className="mt-1 text-xs text-muted-foreground">{String(item.module_name || item.related_record_type || item.type || item.channel || "communication")}</p></div><Badge variant="outline">{String(item.status || item.active || "ready")}</Badge></CardContent></Card>)}
      </div>
    </div>
  );
}

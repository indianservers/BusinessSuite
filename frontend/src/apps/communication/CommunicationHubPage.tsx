import type React from "react";
import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Mail, Megaphone, MessageCircle, ScrollText, Send, ShieldCheck, TableProperties, Users } from "lucide-react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { communicationApi, type CommunicationList, type CommunicationRecord } from "./api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";

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
  { key: "delivery-logs", label: "Logs", path: "/crm/delivery-logs", icon: ScrollText },
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
  const location = useLocation();
  const navigate = useNavigate();
  const params = useParams();
  const active = activeSection(location.pathname);
  return (
    <div className="space-y-6">
      <div className="border-b bg-background px-4 py-5 sm:px-6 lg:px-8">
        <p className="text-sm font-medium uppercase text-muted-foreground">CRM</p>
        <h1 className="text-2xl font-semibold">Communication Hub</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">Templates, individual emails, public webforms, auto-responses, campaigns, consent, WhatsApp placeholders, timeline, and delivery analytics.</p>
        <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
          {sections.map((item) => {
            const Icon = item.icon;
            return <Button key={item.key} variant={active === item.key ? "default" : "outline"} size="sm" onClick={() => navigate(item.path)}><Icon className="h-4 w-4" />{item.label}</Button>;
          })}
        </div>
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
  return <GenericSection title="Email Templates" description="Merge-ready CRM email templates for leads, contacts, accounts, deals, quotes, and customers." queryKey="communication-templates" queryFn={communicationApi.templates} action="Create Template" mutation={() => communicationApi.createTemplate({ name: "Welcome Lead", subject: "Hello {{name}}", body_text: "Thanks for contacting us, {{name}}.", module_name: "lead", template_type: "email", active: true })} />;
}

function Emails() {
  const { toast } = useToast();
  const query = useQuery({ queryKey: ["communication-timeline"], queryFn: () => communicationApi.timeline("lead", 1) });
  const send = useMutation({
    mutationFn: () => communicationApi.sendEmail({ related_record_type: "lead", related_record_id: 1, to_email: "lead@example.com", subject: "Follow up", body: "Following up from CRM." }),
    onSuccess: (data: CommunicationRecord) => {
      toast({ title: `Email ${String(data.status)}` });
      query.refetch();
    },
    onError: (error) => toast({ title: actionError(error), variant: "destructive" }),
  });
  const draft = useMutation({
    mutationFn: () => communicationApi.draftEmail({ related_record_type: "lead", related_record_id: 1, to_email: "lead@example.com", subject: "Draft follow up", body: "Draft only." }),
    onSuccess: (data: CommunicationRecord) => toast({ title: `Draft ${data.id}` }),
    onError: (error) => toast({ title: actionError(error), variant: "destructive" }),
  });
  return <SectionFrame title="Individual Emails" description="Send or draft one-to-one CRM emails with provider availability and opt-out enforcement." action="Send Email" onAction={() => send.mutate()} query={query}><Button variant="outline" onClick={() => draft.mutate()}>Create Draft</Button></SectionFrame>;
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

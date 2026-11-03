import { PhoneInput } from "@/lib/validation/PhoneInput";
import { contract } from "@/lib/validation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { whatsappBase as base, whatsappError, templateParameters, templateSupported, type Contact, type Message, type Template } from "./types";

type SendPayload = { requestId: string; to: string; body: string; template?: { name: string; language: { code: string }; components?: unknown[] }; entityType?: string; entityId?: number };
type CRMRecord = { id: number; name?: string; fullName?: string; firstName?: string; lastName?: string; title?: string; phone?: string; phoneCountryCode?: string };
export default function Composer({ templates, contact, admin, scope, refresh }: { templates: Template[]; contact?: Contact; admin: boolean; scope: string; refresh: () => Promise<void> }) {
  const [to, setTo] = useState(contact ? "+" + contact.recipient : ""), [body, setBody] = useState("");
  const [countryCode,setCountryCode]=useState(contract.default_calling_code);
  const callingCode=to.startsWith('+') ? ([...contract.countries].sort((a,b)=>b.code.length-a.code.length).find(c=>to.startsWith(c.code))?.code || countryCode) : countryCode;
  const nationalNumber=to.startsWith(callingCode)?to.slice(callingCode.length):to;
  const [mode, setMode] = useState("template"), [chosen, setChosen] = useState("");
  const [parameters, setParameters] = useState<Record<string, string>>({});
  const [entity, setEntity] = useState(contact?.entityType || "lead"), [recordId, setRecordId] = useState(contact?.entityId ? String(contact.entityId) : ""), [search, setSearch] = useState("");
  const [consentSource, setConsentSource] = useState("");
  const [busy, setBusy] = useState(false), [notice, setNotice] = useState("");
  const [pending, setPending] = useState<SendPayload | null>(null);
  const [result, setResult] = useState<Message | null>(null);
  const records = useQuery({ queryKey: ["whatsapp-records", scope, entity, search], enabled: !contact,
    queryFn: async () => (await api.get<{ items: CRMRecord[] }>(`/crm/${entity === "lead" ? "leads" : entity === "contact" ? "contacts" : "deals"}`, { params: { search, per_page: 30 } })).data.items });
  const approved = templates.filter(t => t.status === "APPROVED" && templateSupported(t));
  const template = approved.find(t => t.name + ":" + t.language === chosen);
  const placeholders = templateParameters(template);
  const locked = busy || !!pending || !!result;
  const linked = contact?.entityId || recordId;
  function recordFields() { return linked ? { entityType: contact?.entityType || entity, entityId: Number(linked) } : {}; }
  async function consent(status: string) {
    setBusy(true); setNotice("");
    try { await api.post(base + "/consent", { to, status, source: consentSource, ...recordFields() }); setNotice("Consent updated. Record opt-in only when the recipient has agreed to receive messages."); await refresh(); }
    catch (error) { setNotice(whatsappError(error)); }
    finally { setBusy(false); }
  }
  async function send() {
    const payload = pending || { requestId: crypto.randomUUID(), to, body: mode === "text" ? body : "", ...recordFields(),
      ...(mode === "template" && template ? { template: { name: template.name, language: { code: template.language },
        ...(placeholders.length ? { components: [{ type: "body", parameters: placeholders.map(p => ({ type: "text", text: parameters[p] })) }] } : {}) } } : {}) };
    setPending(payload); setBusy(true); setNotice("");
    try {
      const message = (await api.post<Message>(base + "/messages", payload)).data;
      setResult(message);
      setNotice(`Message ${message.id}: ${message.status.replace(/_/g, " ")}${message.errorCode ? " (Meta code " + message.errorCode + ")" : ""}. Acceptance is followed by delivery updates in the inbox.`);
      // Submitting/uncertain outcomes keep the original request ID for safe reconciliation.
      if (!["submitting", "reconciliation_required", "reserved"].includes(message.status)) setPending(null);
      await refresh();
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status;
      setNotice(whatsappError(error));
      if (status && [400, 403, 404, 409, 422, 429].includes(status)) setPending(null);
    } finally { setBusy(false); }
  }
  return <div className="space-y-4 rounded-xl border p-4">
    <h3 className="font-medium">{contact ? "Reply or send a template" : "Send a WhatsApp message"}</h3>
    {!contact && <div className="grid gap-3 sm:grid-cols-3">
      <label className="text-sm">CRM record type<select disabled={locked} className="h-10 w-full rounded-md border bg-background px-3" value={entity} onChange={e => { setEntity(e.target.value); setRecordId(""); }}><option value="lead">Lead</option><option value="contact">Contact</option><option value="deal">Deal</option></select></label>
      <label className="text-sm">Search CRM<Input disabled={locked} value={search} onChange={e => setSearch(e.target.value)} /></label>
      <label className="text-sm">Link CRM record<select disabled={locked} className="h-10 w-full rounded-md border bg-background px-3" value={recordId} onChange={e => {
        setRecordId(e.target.value); const selected = records.data?.find(r => String(r.id) === e.target.value);
        if (selected?.phone) setTo(selected.phone.startsWith("+") ? selected.phone : (selected.phoneCountryCode || contract.default_calling_code) + selected.phone);
      }}><option value="">{admin ? "No CRM record (administrator)" : "Choose a record"}</option>{records.data?.map(r => <option key={r.id} value={r.id}>{r.fullName || r.name || [r.firstName, r.lastName].filter(Boolean).join(" ") || r.title || `Record ${r.id}`}</option>)}</select></label>
      {records.isError && <p className="text-sm text-destructive">CRM records could not load.</p>}
    </div>}
    <div className="block max-w-sm text-sm"><span>Recipient phone</span><PhoneInput label="Recipient phone" value={nationalNumber} countryCode={callingCode} disabled={locked || !!contact} onChange={value=>setTo(value?callingCode+value:"")} onCountryCodeChange={code=>{setCountryCode(code);setTo(nationalNumber?code+nationalNumber:"");}}/></div>
    <p className="text-sm text-muted-foreground">{contact ? `Consent: ${contact.consent.replace(/_/g, " ")}. ${contact.serviceWindowOpen ? "24-hour reply window is open." : "Reply window is closed; use an approved template with opt-in."}` : "You can message other recipients who opted in. A customer message opens a 24-hour window for free-text replies."}</p>
    <details className="rounded-lg border p-3"><summary className="cursor-pointer text-sm">Record recipient consent</summary>
      <p className="my-2 text-xs text-muted-foreground">Keep evidence of the recipient’s permission, for example the signup form and date. STOP messages automatically opt recipients out.</p>
      <Input disabled={locked} placeholder="Consent evidence or source" value={consentSource} onChange={e => setConsentSource(e.target.value)} />
      <div className="mt-2 flex gap-2"><Button variant="outline" disabled={locked || !to || consentSource.trim().length < 3 || (!admin && !linked)} onClick={() => void consent("opted_in")}>Record opt-in</Button><Button variant="outline" disabled={locked || !to || consentSource.trim().length < 3 || (!admin && !linked)} onClick={() => void consent("opted_out")}>Record opt-out</Button></div>
    </details>
    <div className="flex gap-2"><Button disabled={locked} variant={mode === "template" ? "default" : "outline"} onClick={() => setMode("template")}>Approved template</Button><Button disabled={locked} variant={mode === "text" ? "default" : "outline"} onClick={() => setMode("text")}>Text reply</Button></div>
    {mode === "template" ? <div className="space-y-3">
      <label className="block text-sm">Template<select className="h-10 w-full rounded-md border bg-background px-3" disabled={locked} value={chosen} onChange={e => { setChosen(e.target.value); setParameters({}); }}><option value="">Choose approved template</option>{approved.map(t => <option key={t.name + t.language} value={t.name + ":" + t.language}>{t.name} · {t.language}</option>)}</select></label>
      {template && <p className="whitespace-pre-wrap rounded-lg bg-muted p-3 text-sm">{template.components?.find(c => c.type === "BODY")?.text}</p>}
      {placeholders.map(p => <label key={p} className="block text-sm">Value for {p}<Input disabled={locked} value={parameters[p] || ""} onChange={e => setParameters({ ...parameters, [p]: e.target.value })} /></label>)}
      <p className="text-xs text-muted-foreground">This composer supports text templates with numbered body variables. Media templates require the messaging API.</p>
    </div> : <label className="block text-sm">Message<textarea className="mt-1 min-h-28 w-full rounded-md border bg-background p-3" maxLength={4096} disabled={locked} value={body} onChange={e => setBody(e.target.value)} /></label>}
    <Button disabled={busy || (!!result && !pending) || (!pending && (!to || (!admin && !linked) || (mode === "text" ? !body.trim() : !template || placeholders.some(p => !parameters[p]?.trim()))))} onClick={() => void send()}>{busy ? "Checking…" : pending ? "Check original send outcome" : "Send message"}</Button>
    {pending && <p className="text-sm">The outcome is unresolved. This button checks the same request and does not resend it. Check the inbox or ask your administrator to reconcile the provider result before starting another message.</p>}
    {result && !pending && <Button className="ml-2" variant="outline" onClick={() => { setResult(null); setBody(""); setNotice(""); }}>New message</Button>}
    {notice && <p role="status" className="whitespace-pre-wrap text-sm">{notice}</p>}
  </div>;
}

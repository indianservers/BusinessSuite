import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function WhatsAppCloudPanel() {
  const connection = useQuery({ queryKey: ["whatsapp-cloud-status"], queryFn: async () => (await api.get<{provider:string;configured:boolean;webhookConfigured:boolean}>("/integrations/whatsapp/status")).data });
  const [record, setRecord] = useState("");
  const [entity, setEntity] = useState("lead");
  const [number, setNumber] = useState("");
  const [country, setCountry] = useState("+91");
  const [body, setBody] = useState("");
  const [template, setTemplate] = useState("");
  const [language, setLanguage] = useState("en_US");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");
  async function send() {
    setBusy(true); setResult("");
    try {
      const response = await api.post<{status:string;failureReason?:string;failure_reason?:string}>("/crm/messages/send", {
        channel:"whatsapp", entityType:entity, entityId:Number(record), to:number, country_code:country,
        body:body || `Template: ${template}`, whatsappTemplateName:template || null, whatsappTemplateLanguage:language,
      });
      setResult(`Status: ${response.data.status}. ${response.data.failureReason || response.data.failure_reason || "Provider acceptance does not confirm delivery."}`);
    } catch { setResult("Send failed. Check record access, sender organization, credentials, and recipient number. Avoid retrying an uncertain send until reconciled."); }
    finally { setBusy(false); }
  }
  return <section className="space-y-4 rounded-lg border p-5">
    <h2 className="text-lg font-semibold">WhatsApp Business</h2>
    <p className="text-sm text-muted-foreground">Send to a customer from an accessible CRM record. Use an approved Meta template to start a conversation; free text requires an open customer service window.</p>
    <p role="status" className="text-sm">{connection.isError ? "Connection status unavailable" : !connection.data ? "Checking connection…" : `Provider: ${connection.data.provider} · ${connection.data.configured ? "Credentials configured" : "Setup required"} · Webhook ${connection.data.webhookConfigured ? "configured" : "setup required"}`}</p>
    <fieldset disabled={busy} className="grid gap-3 sm:grid-cols-2">
      <label>Record type<select className="block w-full rounded border p-2" value={entity} onChange={e=>setEntity(e.target.value)}><option value="lead">Lead</option><option value="contact">Contact</option><option value="deal">Deal</option></select></label>
      <label>Record ID<Input type="number" min="1" value={record} onChange={e=>setRecord(e.target.value)}/></label>
      <label>Country code<Input value={country} onChange={e=>setCountry(e.target.value)}/></label>
      <label>Recipient national number<Input type="tel" value={number} onChange={e=>setNumber(e.target.value)}/></label>
      <label>Approved Meta template name (optional)<Input value={template} onChange={e=>setTemplate(e.target.value)} placeholder="hello_world"/></label>
      <label>Template language<Input value={language} onChange={e=>setLanguage(e.target.value)}/></label>
      {!template && <label className="sm:col-span-2">Message<textarea className="block min-h-24 w-full rounded border p-2" maxLength={4096} value={body} onChange={e=>setBody(e.target.value)}/></label>}
    </fieldset>
    <Button disabled={busy || !connection.data?.configured || connection.data.provider !== "meta" || Number(record)<1 || !number || !(template || body.trim())} onClick={()=>void send()}>{busy ? "Sending…" : "Send WhatsApp message"}</Button>
    {result && <p role="status" className="text-sm">{result}</p>}
  </section>;
}

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { NativeSelect } from "@/components/ui/native-select";
import { Input } from "@/components/ui/input";
import { phoneLinks } from "@/components/PhoneActions";
import WhatsAppCloudPanel from "../WhatsAppCloudPanel";
import { errorText, useCenterScope } from "./shared";

type Recipient = { id: number; key: string; entity: string; name: string; phone?: string; phone_country_code?: string; due?: string; status?: string };

export default function SendReminders() {
  const scope = useCenterScope();
  const [entity, setEntity] = useState("contacts"), [bucket, setBucket] = useState("today"), [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Recipient>();
  const records = useQuery({
    queryKey: ["communication-reminders", scope, entity, bucket, search],
    queryFn: async () => (await api.get<{ items: Recipient[]; total: number }>("/crm/growth/records", { params: { entity, bucket, search, active_only: true, per_page: 100, timezone_name: Intl.DateTimeFormat().resolvedOptions().timeZone } })).data,
  });
  const phone = selected ? phoneLinks(selected.phone, selected.phone_country_code)?.call.slice(4) : "";
  return <section className="space-y-5">
    <div><h2 className="text-xl font-semibold">Send reminders</h2><p className="text-sm text-muted-foreground">Choose a follow-up, then send an approved WhatsApp template or write a text message. Text messages require an open 24-hour reply window.</p></div>
    <div className="grid gap-3 sm:grid-cols-3">
      <label>Record type<NativeSelect aria-label="Reminder record type" value={entity} onChange={e => { setEntity(e.target.value); setSelected(undefined); }}><option value="contacts">Contacts</option><option value="leads">Leads</option><option value="deals">Deals</option></NativeSelect></label>
      <label>Follow-up due<NativeSelect aria-label="Reminder due date" value={bucket} onChange={e => { setBucket(e.target.value); setSelected(undefined); }}><option value="today">Today</option><option value="overdue">Overdue</option><option value="upcoming">Upcoming</option><option value="all">All active relationships</option></NativeSelect></label>
      <label>Search<Input aria-label="Search reminder recipients" value={search} onChange={e => setSearch(e.target.value)} placeholder="Name, email or phone"/></label>
    </div>
    {records.isPending && <p role="status">Loading follow-ups…</p>}
    {records.isError && <p role="alert">{errorText(records.error)} <button onClick={() => void records.refetch()}>Retry</button></p>}
    <label>Follow-up recipient<NativeSelect aria-label="Follow-up recipient" value={selected?.key || ""} onChange={e => setSelected(records.data?.items.find(row => row.key === e.target.value))}><option value="">Select a follow-up recipient</option>{records.data?.items.map(row => <option key={row.key} value={row.key} disabled={!phoneLinks(row.phone, row.phone_country_code) || /^(blocked|do not contact|inactive)$/i.test(row.status || "")}>{row.name} · {row.due ? new Date(row.due).toLocaleString() : "No follow-up date"}{!row.phone ? " · No phone" : ""}</option>)}</NativeSelect></label>
    {records.data && !records.data.items.length && <p>No follow-ups match these filters. Choose another due date or <Link className="underline" to="/crm/customer-follow-ups">manage follow-ups</Link>.</p>}
    {records.data && records.data.total > records.data.items.length && <p>Showing the first {records.data.items.length} matches. Narrow your search to find another recipient.</p>}
    {selected && <><p className="rounded-lg border p-3">Reminder for <strong>{selected.name}</strong>{selected.due && <> · Due {new Date(selected.due).toLocaleString()}</>}. Review the message and recipient before sending.</p><WhatsAppCloudPanel key={`${scope}:${selected.key}`} initialDraft={{ key: `reminder:${selected.key}`, to: phone || "", body: `Hello ${selected.name}, this is a reminder about our follow-up${selected.due ? ` on ${new Date(selected.due).toLocaleString()}` : ""}. Please let us know a convenient time to connect.`, entityType: entity === "leads" ? "lead" : entity === "deals" ? "deal" : "contact", entityId: selected.id }}/></>}
  </section>;
}

import { useEffect, useState, type ReactNode } from "react";
import { Mail, Eye, Phone, Maximize2, X, Pencil } from "lucide-react";
import { WhatsAppIcon } from "@/components/actions/BrandIcons";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import "./record-workspace.css";

export type CommunicationRecord = { name: string; email?: string; phone?: string; phone_country_code?: string; phoneCountryCode?: string; status?: string };
export function whatsappNumber(record: CommunicationRecord) {
  const phone = record.phone?.trim() || "";
  const full = phone.startsWith("+") ? phone : `${record.phone_country_code || record.phoneCountryCode || ""}${phone}`;
  const digits = full.replace(/\D/g, "");
  return full.startsWith("+") && /^[1-9]\d{6,14}$/.test(digits) ? digits : "";
}
export function communicationBlocked(record: CommunicationRecord) { return /^(do not contact|blocked|inactive)$/i.test(record.status || ""); }

export function RecordQuickActions({ record, onView, onMessage, onEdit }: { record: CommunicationRecord; onView: () => void; onMessage: (channel: "email" | "whatsapp") => void; onEdit?: () => void }) {
  const blocked = communicationBlocked(record);
  return <div className="record-quick-actions" onClick={event => event.stopPropagation()} onDoubleClick={event => event.stopPropagation()}>
    <button className="record-quick-action email" aria-label={`Email ${record.name}`} title={blocked ? "Communication is blocked for this record" : record.email ? "Compose email" : "No email recorded"} disabled={blocked || !record.email} onClick={() => onMessage("email")}><Mail size={16}/></button>
    <button className="record-quick-action whatsapp" aria-label={`WhatsApp ${record.name}`} title={blocked ? "Communication is blocked for this record" : whatsappNumber(record) ? "Compose WhatsApp message" : "A phone number with country code is required"} disabled={blocked || !whatsappNumber(record)} onClick={() => onMessage("whatsapp")}><WhatsAppIcon width={16} height={16}/></button>
    {record.phone && !blocked && <a className="record-quick-action call" aria-label={`Call ${record.name}`} title="Call" href={`tel:${record.phone.startsWith("+") ? record.phone : `${record.phone_country_code || record.phoneCountryCode || ""}${record.phone}`}`}><Phone size={16}/></a>}
    <button className="record-quick-action view" aria-label={`Open ${record.name} popup`} title="Open record popup" onClick={onView}><Eye size={16}/></button>
    {onEdit && <button className="record-quick-action" aria-label={`Edit ${record.name}`} title="Edit record" onClick={onEdit}><Pencil size={16}/></button>}
  </div>;
}

export function RecordSidePane({ title, close, expand, children }: { title: string; close: () => void; expand: () => void; children: ReactNode }) {
  useEffect(() => { const escape = (event: KeyboardEvent) => { if (event.key === "Escape" && !document.querySelector('[role="dialog"]')) close(); }; window.addEventListener("keydown", escape); return () => window.removeEventListener("keydown", escape); }, [close]);
  return <aside className="record-side-pane" aria-label={`Details: ${title}`}><header><div><small>RECORD DETAILS</small><h2>{title}</h2></div><button title="Open larger popup" aria-label={`Expand ${title}`} onClick={expand}><Maximize2 size={16}/></button><button title="Close details" aria-label="Close record details" onClick={close}><X size={18}/></button></header><div className="record-pane-body">{children}</div></aside>;
}

export function RecordMessageDraft({ record, channel, close }: { record: CommunicationRecord; channel: "email" | "whatsapp"; close: () => void }) {
  const [subject, setSubject] = useState(`Following up with ${record.name}`), [body, setBody] = useState(`Hello ${record.name},\n`);
  const available = !communicationBlocked(record) && (channel === "email" ? !!record.email : !!whatsappNumber(record));
  const href = channel === "email" ? `mailto:${encodeURIComponent(record.email || "")}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}` : `https://wa.me/${whatsappNumber(record)}?text=${encodeURIComponent(body)}`;
  return <Dialog open onOpenChange={open => { if (!open) close(); }}><DialogContent className="record-message-dialog"><DialogTitle>{channel === "email" ? "Email" : "WhatsApp"} · {record.name}</DialogTitle><p className="text-sm text-muted-foreground">To: {channel === "email" ? record.email || "No email recorded" : `${record.phone_country_code || record.phoneCountryCode || ""} ${record.phone || "No phone recorded"}`}</p>{channel === "email" && <label>Subject<Input value={subject} onChange={event => setSubject(event.target.value)} maxLength={240}/></label>}<label>Message<textarea aria-label="Message draft" value={body} onChange={event => setBody(event.target.value)} maxLength={4000} rows={6}/></label>{!available && <p role="alert">Add valid contact details and check communication preferences before contacting this record.</p>}<p className="text-xs text-muted-foreground">Review and send in your messaging app. Opening a draft does not send it.</p><footer><Button variant="outline" onClick={close}>Cancel</Button>{available && body.trim() && <Button asChild><a href={href} target={channel === "whatsapp" ? "_blank" : undefined} rel="noopener noreferrer">Open {channel === "email" ? "email" : "WhatsApp"} draft</a></Button>}</footer></DialogContent></Dialog>;
}

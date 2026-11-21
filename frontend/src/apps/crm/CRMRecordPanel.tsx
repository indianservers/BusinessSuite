import { ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PersonRecordPreview from "@/components/PersonRecordPreview";
import PhoneActions from "@/components/PhoneActions";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import CRMStageDialog from "./CRMStageDialog";
import { crmApi, type CRMApiRecord } from "./api";
import { errorMessage } from "./leads/api";
import type { SalesRecord } from "./CRMSalesHome";
import "./crm-record-detail.css";

type Props = {
  record: SalesRecord;
  close: () => void;
  changed: () => void;
  previous?: () => void;
  next?: () => void;
  onInteraction: () => void;
};

type PreviewData = {
  key: string;
  record?: CRMApiRecord;
  error?: string;
};

function recordList(value: unknown): CRMApiRecord[] {
  return Array.isArray(value) ? value : [];
}

function PreviewTimeline({ items }: { items: CRMApiRecord[] }) {
  return <section className="space-y-2">
    <h3 className="font-semibold">Timeline</h3>
    {items.map((event, index) => {
      const entry = event.record as CRMApiRecord | undefined;
      return <article key={String(event.id ?? index)} className="rounded-md border p-3 text-sm">
        <strong>{String(event.title || event.type || "Activity")}</strong>
        <p className="text-muted-foreground">{String(event.occurredAt || event.occurred_at || "")}</p>
        <p>{String(entry?.body || entry?.description || event.description || "")}</p>
      </article>;
    })}
    {!items.length && <p className="text-sm text-muted-foreground">No recorded interactions yet.</p>}
  </section>;
}

export default function CRMRecordPanel({ record, close, changed, previous, next, onInteraction }: Props) {
  const key = `${record.entity}:${record.id}`;
  const [stageRecord, setStageRecord] = useState<string>();
  const [preview, setPreview] = useState<PreviewData>();
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let current = true;
    void crmApi.get(record.entity, record.id)
      .then(response => { if (current) setPreview({ key, record: response.data }); })
      .catch(error => { if (current) setPreview({ key, error: errorMessage(error) }); });
    return () => { current = false; };
  }, [key, record.entity, record.id, revision]);

  const data = preview?.key === key ? preview.record : undefined;
  const error = preview?.key === key ? preview.error : undefined;
  const timeline = recordList(data?.timeline);
  const fullPath = `/crm/${record.entity}/${record.id}`;
  const navigation = <>
    <Button variant="outline" disabled={!previous} onClick={previous}><ChevronLeft aria-hidden="true" />Previous</Button>
    <Button variant="outline" disabled={!next} onClick={next}>Next<ChevronRight aria-hidden="true" /></Button>
  </>;
  const communicationPreferences = <Link className="text-sm underline" to="/crm/consents" onClick={close}>Review communication preferences</Link>;

  if (record.entity === "contacts" || record.entity === "leads") {
    return <PersonRecordPreview
      key={key}
      record={{ ...record, ...data, name: data?.full_name || data?.name || record.name }}
      loading={!data && !error}
      error={error}
      onClose={close}
      fullProfileHref={fullPath}
      actions={<>{navigation}{record.phone && <Button asChild variant="outline"><a href={`tel:${record.phone_country_code || ""}${record.phone}`}>Call</a></Button>}</>}
      activity={<><PreviewTimeline items={timeline} />{communicationPreferences}</>}
      followUp={<>
        <p>{String(data?.next_follow_up_at || data?.nextFollowUp || "No next follow-up recorded.")}</p>
        {record.no_next_action && <p className="rounded-md border border-amber-300 p-3 text-sm">No next action recorded.</p>}
      </>}
    />;
  }

  return <Dialog open onOpenChange={open => { if (!open) close(); }}>
    <DialogContent className="crm-record-preview" style={{ height: "100dvh" }}>
      <header className="crm-record-preview-header">
        <DialogTitle className="crm-record-title text-lg font-semibold">{record.name}</DialogTitle>
        {(data?.status || record.status) && <p className="text-sm text-muted-foreground">{String(data?.status || record.status)}</p>}
        <nav aria-label="Preview navigation" className="crm-record-preview-nav">
          <Button asChild><Link to={fullPath} onClick={close}><ExternalLink aria-hidden="true" />Open full record</Link></Button>
          {navigation}
        </nav>
      </header>
      <div key={key} className="crm-record-preview-body space-y-4">
        {error && <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <p>{error}</p>
          <Button variant="outline" size="sm" className="mt-2" onClick={() => { setPreview(undefined); setRevision(value => value + 1); }}>Retry</Button>
        </div>}
        {!data && !error && <p role="status">Loading record…</p>}
        {data && <>
          {record.phone && <PhoneActions value={record.phone} record={record} field="phone" />}
          {record.no_next_action && <p className="rounded-md border border-amber-300 p-3 text-sm">No next action recorded.</p>}
          {record.entity === "deals" && <>
            <p className="font-semibold">{String(data.currency || record.currency || "INR")} {Number(data.amount || 0).toLocaleString()}</p>
            <div className="flex flex-wrap gap-2">
              <Button disabled={record.can_edit === false} onClick={onInteraction}>Log call / meeting &amp; next step</Button>
              <Button disabled={record.can_edit === false} variant="outline" onClick={() => setStageRecord(key)}>Review stage move</Button>
            </div>
            <Link className="text-sm underline" to="/crm/lead-to-cash" onClick={close}>View linked quotation, order, invoice and project handover</Link>
          </>}
          {record.entity === "quotations" && <QuotationPreview id={record.id} data={data} close={close} />}
          <PreviewTimeline items={timeline} />
          {communicationPreferences}
        </>}
      </div>
      {stageRecord === key && <CRMStageDialog id={record.id} close={() => setStageRecord(undefined)} saved={() => {
        setRevision(value => value + 1);
        changed();
      }}/>}
    </DialogContent>
  </Dialog>;
}

function QuotationPreview({ id, data, close }: { id: number; data: CRMApiRecord; close: () => void }) {
  const currency = String(data.currency || "INR");
  const totals = [
    ["Subtotal", data.subtotal],
    ["Discount", data.discount_total ?? data.discountTotal],
    ["Tax", data.tax_total ?? data.taxTotal],
    ["Grand total", data.grand_total ?? data.grandTotal],
  ] as const;
  return <section className="space-y-2 rounded-md border p-3 text-sm">
    <h2 className="text-base font-semibold">Quotation review</h2>
    <dl className="space-y-1">{totals.map(([label, value]) => <div key={label} className="flex flex-wrap justify-between gap-1">
      <dt>{label}</dt><dd className="font-medium">{currency} {String(value ?? 0)}</dd>
    </div>)}</dl>
    <p>Version {String(data.version_number || data.versionNumber || 1)} · Approval {String(data.approval_status || data.approvalStatus || "Not recorded")}</p>
    <p>Sent version {String(data.sentVersionNumber || "Not recorded")} · {String(data.sentVersionEvidence || "No version-specific sending evidence")}</p>
    <p>Marked sent {String(data.sent_at || data.sentAt || "Not sent")}</p>
    {recordList(data.lines).map(line => <p key={String(line.id)}>{String(line.name)} · {String(line.quantity)} × {currency} {String(line.unit_price ?? line.unitPrice)} · total {String(line.line_total ?? line.lineTotal ?? line.total_amount)}</p>)}
    <details>
      <summary>Version and approval history</summary>
      {recordList(data.versions).map(version => <p key={String(version.id)}>Version {String(version.version_number || version.versionNumber)} · {String(version.created_at || version.createdAt || "")}</p>)}
      {recordList(data.approvals).map(approval => <p key={String(approval.id)}>{String(approval.status || "")} · {String(approval.comments || "")}</p>)}
    </details>
    <Button asChild variant="outline"><Link to={`/crm/quotes/${id}/builder`} onClick={close}>Open quotation builder</Link></Button>
  </section>;
}

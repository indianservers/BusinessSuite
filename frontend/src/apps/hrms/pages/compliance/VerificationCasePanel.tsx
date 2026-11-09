import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { backgroundVerificationApi as bgv } from "@/services/api";
import { formatDate } from "@/lib/utils";
import type { EmployeeFile, VerificationCase } from "./verificationRecords";

type Props = {record: VerificationCase; documents: EmployeeFile["documents"]; canManage: boolean; busy: boolean; run: (action: () => Promise<unknown>) => Promise<void>};

export default function VerificationCasePanel({record, documents, canManage, busy, run}: Props) {
  const [consentDocument, setConsentDocument] = useState("");
  const [outcome, setOutcome] = useState("Clear");
  const [reviewNotes, setReviewNotes] = useState("");
  const [newCheck, setNewCheck] = useState("");
  const [due, setDue] = useState(record.expected_completion_date || "");
  const [owner, setOwner] = useState(String(record.owner_user_id || ""));
  const [remarks, setRemarks] = useState(record.remarks || "");
  const [progress, setProgress] = useState("In Progress");
  const [reportDocument, setReportDocument] = useState("");
  const [completionDate, setCompletionDate] = useState("");
  const [ownerSearch, setOwnerSearch] = useState("");
  const owners = useQuery({queryKey: ["bgv-owners", ownerSearch], enabled: canManage, queryFn: () => bgv.owners(ownerSearch).then(r => r.data as {id: number; label: string}[])});
  const [showHistory, setShowHistory] = useState(false);
  const events = useQuery({queryKey: ["bgv-events", record.id, record.version], enabled: showHistory, queryFn: () => bgv.events(record.id).then(r => r.data as {id: number; event_type: string; received_at: string; payload_json: Record<string, unknown>}[])});
  const editable = canManage && !record.reviewed_at && record.status !== "Cancelled";
  const docOptions = documents.filter(d => d.file_url);
  return <section className="space-y-4 rounded-lg border p-4" aria-label={`Verification case ${record.id}`}>
    <div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="font-semibold">Case #{record.id} · {record.package_name}</h3><p className="text-sm text-muted-foreground">{record.purpose} · Started {formatDate(record.initiated_at)} · Owner: {record.owner_name || "Unassigned"}</p></div><strong className="text-sm">{record.status}{record.overall_result ? ` · ${record.overall_result}` : ""}</strong></div>
    <p className="text-sm">Consent: {record.consent_status} · Due: {formatDate(record.expected_completion_date)}{record.vendor_reference ? ` · Vendor reference: ${record.vendor_reference}` : ""}</p>
    <div className="flex flex-wrap gap-3 text-sm">{record.consent_url && <a className="underline" href={record.consent_url} target="_blank" rel="noreferrer">Consent evidence</a>}{record.report_url && <a className="underline" href={record.report_url} target="_blank" rel="noreferrer">Final report</a>}</div>
    {editable && record.consent_status !== "Captured" && <form className="flex flex-wrap items-end gap-2" onSubmit={e => {e.preventDefault(); void run(() => bgv.captureConsent(record.id, {consent_status: "Captured", employee_document_id: Number(consentDocument), version: record.version}));}}>
      <label className="min-w-0 flex-1 text-sm">Signed consent document<NativeSelect aria-label="Signed consent document" value={consentDocument} onChange={e => setConsentDocument(e.target.value)} className="mt-1 h-10 w-full rounded border bg-background px-2"><option value="">Select existing employee document</option>{docOptions.map(d => <option key={d.id} value={d.id}>{d.document_name || d.document_type}</option>)}</NativeSelect></label>
      <Button disabled={busy || !consentDocument} type="submit">Record consent</Button>
    </form>}
    {editable && <details><summary className="cursor-pointer text-sm font-medium">Case ownership, deadline and progress</summary><form className="mt-3 grid gap-3 sm:grid-cols-2" onSubmit={e => {e.preventDefault(); void run(() => bgv.updateRequest(record.id, {status: progress, owner_user_id: owner ? Number(owner) : null, expected_completion_date: due || null, remarks, ...(reportDocument ? {report_url: documents.find(d => d.id === Number(reportDocument))?.file_url} : {}), version: record.version}));}}>
      <label className="text-sm">Find case owner by email<Input value={ownerSearch} onChange={e => setOwnerSearch(e.target.value)}/><NativeSelect aria-label="Case owner" loading={owners.isFetching} error={owners.isError} value={owner} onChange={e => setOwner(e.target.value)} className="mt-1 h-10 w-full rounded border bg-background px-2"><option value="">Unassigned</option>{owner && !owners.data?.some(o => String(o.id) === owner) && <option value={owner}>Current owner</option>}{owners.data?.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}</NativeSelect></label>
      <label className="text-sm">Due date<Input type="date" value={due} onChange={e => setDue(e.target.value)}/></label>
      <label className="text-sm">Progress<NativeSelect aria-label="Progress" value={progress} onChange={e => setProgress(e.target.value)} className="h-10 w-full rounded border bg-background px-2">{["In Progress", "On Hold", "Awaiting Review", "Cancelled"].map(s => <option key={s}>{s}</option>)}</NativeSelect></label>
      <label className="text-sm">Final report document<NativeSelect aria-label="Final report document" value={reportDocument} onChange={e => setReportDocument(e.target.value)} className="h-10 w-full rounded border bg-background px-2"><option value="">Keep current report</option>{docOptions.map(d => <option key={d.id} value={d.id}>{d.document_name || d.document_type}</option>)}</NativeSelect></label>
      <label className="text-sm">Notes / reason<Input value={remarks} onChange={e => setRemarks(e.target.value)} /></label><Button disabled={busy} type="submit">Save case details</Button>
    </form></details>}
    <div className="space-y-3">{record.checks.map(check => <CheckEditor key={`${check.id}:${record.version}`} check={check} record={record} documents={docOptions} editable={editable} busy={busy} run={run}/>)}</div>
    {editable && <SmartCreateSection title="Add check" size="compact"><form className="flex flex-wrap gap-2" onSubmit={e => {e.preventDefault(); void run(() => bgv.addCheck(record.id, {check_type: newCheck})).then(() => setNewCheck(""));}}><Input aria-label="Additional check name" placeholder="Additional check, e.g. Previous employer – Acme" value={newCheck} onChange={e => setNewCheck(e.target.value)} className="min-w-0 flex-1" maxLength={80}/><Button variant="outline" disabled={busy || !newCheck.trim()} type="submit">Add check</Button></form></SmartCreateSection>}
    {editable && record.vendor_id && !record.submitted_at && <Button variant="outline" disabled={busy || record.consent_status !== "Captured"} onClick={() => void run(() => bgv.submitToVendor(record.id))}>Record manual vendor submission</Button>}
    {record.submitted_at && <p className="text-xs text-muted-foreground">{record.vendor_status} · {formatDate(record.submitted_at)}. Vendor submission is recorded manually.</p>}
    {editable && <details open={record.status === "Awaiting Review"}><summary className="cursor-pointer font-medium">HR review and closure</summary><form className="mt-3 space-y-3" onSubmit={e => {e.preventDefault(); void run(() => bgv.updateRequest(record.id, {status: "Completed", overall_result: outcome, review_notes: reviewNotes, ...(completionDate ? {completed_at: `${completionDate}T00:00:00Z`} : {}), version: record.version}));}}>
      <label className="block text-sm">Final outcome<NativeSelect aria-label="Final outcome" value={outcome} onChange={e => setOutcome(e.target.value)} className="mt-1 h-10 w-full rounded border bg-background px-2">{["Clear", "Discrepancy", "Unable to Verify", "Amber", "Red"].map(s => <option key={s}>{s}</option>)}</NativeSelect></label>
      <label className="block text-sm">HR decision, employee response and discrepancy resolution<textarea className="mt-1 min-h-20 w-full rounded border bg-background p-2" value={reviewNotes} onChange={e => setReviewNotes(e.target.value)} required minLength={3}/></label>
      <label className="block text-sm">Original report completion date (for historical records)<Input type="date" value={completionDate} onChange={e => setCompletionDate(e.target.value)}/></label>
      <p className="text-xs text-muted-foreground">All checks must be resolved. Closure preserves this round; future verification creates a new round.</p><Button disabled={busy || record.consent_status !== "Captured" || reviewNotes.trim().length < 3} type="submit">Approve review and close case</Button>
    </form></details>}
    {record.reviewed_at && <p className="rounded border p-3 text-sm">Reviewed by {record.reviewer_name || "HR reviewer"} on {formatDate(record.reviewed_at)} · {record.review_notes}</p>}
    <Button size="sm" variant="ghost" onClick={() => setShowHistory(!showHistory)}>{showHistory ? "Hide" : "Show"} case history</Button>
    {showHistory && <div className="space-y-2 text-xs">{events.isPending && <p>Loading history…</p>}{events.isError && <p role="alert">Could not load history. <Button type="submit" variant="outline" className="underline" onClick={() => events.refetch()}>Retry</Button></p>}{events.data?.map(event => <details key={event.id}><summary className="cursor-pointer">{formatDate(event.received_at)} · {event.event_type}</summary><pre className="overflow-auto whitespace-pre-wrap p-2">{JSON.stringify(event.payload_json, null, 2)}</pre></details>)}</div>}
  </section>;
}

function CheckEditor({check, record, documents, editable, busy, run}: {check: VerificationCase["checks"][number]; record: VerificationCase; documents: EmployeeFile["documents"]; editable: boolean; busy: boolean; run: Props["run"]}) {
  const [status, setStatus] = useState(check.status);
  const [result, setResult] = useState(check.result || "Clear");
  const [document, setDocument] = useState(String(check.employee_document_id || ""));
  const [notes, setNotes] = useState(check.remarks || "");
  const [verifiedDate, setVerifiedDate] = useState(check.verified_at?.slice(0,10) || "");
  return <details className="rounded border p-3" open={editable && check.status === "Pending"}><summary className="cursor-pointer text-sm font-medium">{check.check_type} · {check.status}{check.result ? ` · ${check.result}` : ""}</summary>
    {check.document_url && <a className="mt-2 block text-sm underline" href={check.document_url} target="_blank" rel="noreferrer">View supporting evidence</a>}
    <p className="mt-1 text-xs text-muted-foreground">{check.verified_by ? `Verified by ${check.verified_by} · ${formatDate(check.verified_at)}` : "Verification pending"}</p>
    {editable ? <form className="mt-3 grid gap-3 sm:grid-cols-2" onSubmit={e => {e.preventDefault(); void run(() => bgv.updateCheck(check.id, {status, result, employee_document_id: document ? Number(document) : null, remarks: notes, ...(verifiedDate ? {verified_at: `${verifiedDate}T00:00:00Z`} : {}), version: record.version}));}}>
      <label className="text-sm">Check status<NativeSelect aria-label="Check status" value={status} onChange={e => setStatus(e.target.value)} className="h-10 w-full rounded border bg-background px-2">{["Pending", "In Progress", "Verified", "Completed", "Unable to Verify", "Not Applicable"].map(s => <option key={s}>{s}</option>)}</NativeSelect></label>
      <label className="text-sm">Outcome<NativeSelect aria-label="Outcome" value={result} onChange={e => setResult(e.target.value)} className="h-10 w-full rounded border bg-background px-2">{["Clear", "Discrepancy", "Unable to Verify", "Not Applicable"].map(s => <option key={s}>{s}</option>)}</NativeSelect></label>
      <label className="text-sm sm:col-span-2">Existing employee document<NativeSelect aria-label="Existing employee document" value={document} onChange={e => setDocument(e.target.value)} className="h-10 w-full rounded border bg-background px-2"><option value="">Use verification notes / keep attached evidence</option>{documents.map(d => <option key={d.id} value={d.id}>{d.document_name || d.document_type}</option>)}</NativeSelect></label>
      <label className="text-sm sm:col-span-2">Verification findings and employee explanation<textarea value={notes} onChange={e => setNotes(e.target.value)} className="mt-1 min-h-20 w-full rounded border bg-background p-2"/></label>
      <label className="text-sm">Original verification date (optional)<Input type="date" value={verifiedDate} onChange={e => setVerifiedDate(e.target.value)}/></label>
      <Button type="submit" disabled={busy || record.consent_status !== "Captured"}>Save check</Button>
    </form> : <p className="mt-2 whitespace-pre-wrap text-sm">{check.remarks || "No additional findings recorded."}</p>}
  </details>;
}

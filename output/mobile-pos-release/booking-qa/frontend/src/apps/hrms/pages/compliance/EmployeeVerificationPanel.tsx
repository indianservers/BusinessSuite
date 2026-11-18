import { useMobile } from "@/components/mobile/useMobile";
import { MobileDisclosure } from "@/components/mobile/MobilePrimitives";
import "./employee-verification-mobile.css";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { backgroundVerificationApi as bgv, employeeApi } from "@/services/api";
import { formatDate } from "@/lib/utils";
import VerificationCasePanel from "./VerificationCasePanel";
import { useAuthStore } from "@/store/authStore";
import { verificationPhoneScope, verificationError, type EmployeeFile, type Vendor } from "./verificationRecords";

export default function EmployeeVerificationPanel({employeeId}: {employeeId: number}) {
  const phone = useMobile(480);
  useAuthStore(state => state.user);
  const [, refreshContext] = useState(0);
  useEffect(() => {
    if (!phone) return;
    const changed = () => refreshContext(value => value + 1);
    const events = ["suite:tenant-changed", "suite:organization-changed", "suite:branch-changed", "suite:record-access-changed"];
    events.forEach(name => window.addEventListener(name, changed));
    return () => events.forEach(name => window.removeEventListener(name, changed));
  }, [phone]);
  const scope = phone ? verificationPhoneScope(employeeId) : "";
  return <EmployeeVerificationEditor key={phone ? scope : "desktop"} employeeId={employeeId} phone={phone} scope={scope} />;
}
function EmployeeVerificationEditor({employeeId, phone, scope}: {employeeId: number; phone: boolean; scope: string}) {
  const qc = useQueryClient();
  const pendingAction = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const record = useQuery({queryKey: phone ? ["bgv-employee-file", employeeId, scope] : ["bgv-employee-file", employeeId], queryFn: () => bgv.employeeFile(employeeId).then(r => r.data as EmployeeFile & {permissions: {manage: boolean; upload: boolean}})});
  const vendors = useQuery({queryKey: phone ? ["bgv-vendors", scope] : ["bgv-vendors"], enabled: !!record.data?.permissions.manage, queryFn: () => bgv.vendors().then(r => r.data as Vendor[])});
  const [packageName, setPackageName] = useState("Employee background verification");
  const [purpose, setPurpose] = useState("Current employee review");
  const [due, setDue] = useState("");
  const [vendor, setVendor] = useState("");
  const [checks, setChecks] = useState(["Identity", "Education", "Employment", "Address"]);
  const [file, setFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState("Background verification consent");
  async function run(action: () => Promise<unknown>) {
    if (phone && pendingAction.current) return;
    pendingAction.current = true;
    setBusy(true); setError(""); setNotice("");
    try {
      await action();
      await Promise.all([
        qc.invalidateQueries({queryKey: ["bgv-employee-file", employeeId], refetchType: phone && scope !== verificationPhoneScope(employeeId) ? "none" : "active"}),
        qc.invalidateQueries({queryKey: ["bgv-register"], refetchType: phone && scope !== verificationPhoneScope(employeeId) ? "none" : "active"}),
        qc.invalidateQueries({queryKey: ["employee", employeeId], refetchType: phone && scope !== verificationPhoneScope(employeeId) ? "none" : "active"}),
        qc.invalidateQueries({queryKey: ["employee-360"], refetchType: phone && scope !== verificationPhoneScope(employeeId) ? "none" : "active"}),
        qc.invalidateQueries({queryKey: ["bgv-events"], refetchType: phone && scope !== verificationPhoneScope(employeeId) ? "none" : "active"}),
      ]);
      if (!phone || scope === verificationPhoneScope(employeeId)) setNotice("Saved to the existing employee file.");
    } catch (e) {if (!phone || scope === verificationPhoneScope(employeeId)) setError(verificationError(e));} finally {pendingAction.current = false;setBusy(false);}
  }
  if (record.isPending) return <p role="status">Loading employee verification and records…</p>;
  if (record.isError || !record.data) return <p role="alert">{verificationError(record.error)} <Button variant="outline" onClick={() => record.refetch()}>Retry</Button></p>;
  const data = record.data;
  const openCase = data.cases.some(c => c.status !== "Cancelled" && (c.status !== "Completed" || !c.reviewed_at));
  return <div className="hrms-bgv-file space-y-5" aria-label="Employee verification and records">
    <Card><CardHeader><CardTitle className="text-lg">{data.employee.name} · {data.employee.employee_code}</CardTitle></CardHeader><CardContent className="space-y-3">
      <p className="text-sm">{data.employee.status} · Joined {formatDate(data.employee.date_of_joining)} · Exit {formatDate(data.employee.date_of_exit)}</p>
      {data.employee.archived && <p className="text-sm">Archived employee file. The employment record and its evidence are retained here.</p>}
      <MobileDisclosure maxWidth={480} title="Employee record links"><div className="flex flex-wrap gap-3 text-sm">{!data.employee.archived && <><Link className="underline" to={`/hrms/employees/${employeeId}?tab=profile`}>Complete employee profile</Link><Link className="underline" to={`/hrms/documents?employee_id=${employeeId}`}>Documents & certificates</Link><Link className="underline" to={`/hrms/employees/${employeeId}?tab=education`}>Education</Link><Link className="underline" to={`/hrms/employees/${employeeId}?tab=experience`}>Previous employment</Link></>}<Link className="underline" to={`/hrms/exit?employee_id=${employeeId}`}>Exit and handover</Link>{!data.employee.archived && <><Link className="underline" to={`/hrms/fnf-settlements?employee_id=${employeeId}`}>Final settlement</Link><Link className="underline" to={`/hrms/letters-certificates?employee_id=${employeeId}`}>Letters and certificates</Link></>}</div></MobileDisclosure>
      <div className="rounded border p-3 text-sm"><h3 className="font-medium">Records requiring attention</h3>{data.missing.length ? <ul className="mt-2 list-disc space-y-1 pl-5">{data.missing.map(item => <li key={item}>{item}</li>)}</ul> : <p className="mt-1">No gaps found in the checks shown here. Review the file against your HR policy.</p>}
      {(data.restricted.exit || data.restricted.payroll || data.restricted.assets) && <p className="mt-2 text-muted-foreground">Some exit, payroll or asset records are restricted by your permissions; completeness is assessed only for visible records.</p>}</div>
    </CardContent></Card>
    {error && <p role="alert" className="rounded border border-destructive p-3 text-sm text-destructive">{error}</p>}{notice && <p role="status" className="text-sm">{notice}</p>}
    <details className="rounded border p-4"><summary className="cursor-pointer font-medium">Employee background information</summary><div className="mt-3 space-y-3 text-sm">
      <p>{data.background.designation || "Designation not recorded"} · {data.background.department || "Department not recorded"} · {data.background.branch || "Branch not recorded"}</p><p className="break-words">Email: {data.background.email || "Not recorded"} · Phone: {data.background.phone || "Not recorded"}</p><p className="whitespace-pre-wrap">Address: {data.background.address || "Not recorded"}</p>
      <h3 className="font-medium">Education</h3>{data.background.education.map(e => <p key={e.id}>{e.degree} · {e.institution || "Institution not recorded"} · {e.pass_year || "Year not recorded"} {e.document_url && <a className="underline" href={e.document_url} target="_blank" rel="noreferrer">Evidence</a>}</p>)}{!data.background.education.length && <p>No education records recorded.</p>}
      <h3 className="font-medium">Previous employment</h3>{data.background.experience.map(e => <p key={e.id}>{e.company_name} · {e.designation || "Role not recorded"} · {formatDate(e.from_date)} – {formatDate(e.to_date)} {e.relieving_letter_url && <a className="underline" href={e.relieving_letter_url} target="_blank" rel="noreferrer">Relieving letter</a>}</p>)}{!data.background.experience.length && <p>No previous employment recorded. Confirm whether this is applicable.</p>}
    </div></details>
    <MobileDisclosure maxWidth={480} title={`Documents and evidence · ${data.documents.length + data.certificates.length}`}><Card><CardHeader><CardTitle className="text-base">Documents and evidence</CardTitle></CardHeader><CardContent className="space-y-3">
      <p className="text-sm text-muted-foreground">Use the employee’s existing documents as consent and check evidence. Uploading does not mark a document or background check as verified.</p>
      {data.documents.map(d => <div key={d.id} className="flex flex-wrap justify-between gap-2 border-b py-2 text-sm"><span>{d.document_name || d.document_type} · {d.verification_status}</span>{d.file_url && <Button asChild variant="outline"><a className="underline" href={d.file_url} target="_blank" rel="noreferrer">Open document</a></Button>}</div>)}
      {data.certificates.map(c => <div key={c.id} className="flex flex-wrap justify-between gap-2 border-b py-2 text-sm"><span>{c.title} · {c.verification_status}</span><Button asChild variant="outline"><a className="underline" href={c.file_url} target="_blank" rel="noreferrer">Open certificate</a></Button></div>)}
      {!data.documents.length && !data.certificates.length && <p className="text-sm">No supporting documents recorded.</p>}
      {data.permissions.upload && <SmartCreateSection title="Create documents and evidence" mobileSheet={phone} size="compact"><form aria-busy={phone ? busy : undefined} className="hrms-bgv-file-form grid gap-3 sm:grid-cols-2" onSubmit={e => {e.preventDefault(); if (!file || phone && busy) return; const body = new FormData(); body.append("file", file); body.append("document_type", documentType); body.append("document_name", file.name); void run(() => employeeApi.uploadDocument(employeeId, body));}}>
        <label className="text-sm">Document type<Input disabled={phone && busy} value={documentType} onChange={e => setDocumentType(e.target.value)} required maxLength={100}/></label><label className="min-w-0 text-sm">File<Input disabled={phone && busy} type="file" accept=".pdf,.jpg,.jpeg,.png,.doc,.docx" onChange={e => setFile(e.target.files?.[0] || null)} required/></label><Button data-save-action={phone || undefined} disabled={busy || !file || !documentType.trim()} type="submit">{phone ? "Upload evidence" : "Upload to employee documents"}</Button>
      {phone && error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      </form></SmartCreateSection>}
    </CardContent></Card></MobileDisclosure>
    <section className="space-y-4"><h2 className="text-lg font-semibold">Background verification history</h2>
      {data.legacy_verification && data.legacy_verification.status && data.legacy_verification.status !== "Not Started" && <p className="rounded border p-3 text-sm">Existing profile entry: {data.legacy_verification.status} · {formatDate(data.legacy_verification.date)} · {data.legacy_verification.agency || "Agency not recorded"}. Review its evidence when creating the verification case; this entry is preserved in case history.</p>}
      {!data.cases.length && <p className="text-sm">Not assessed. No verification case has been recorded.</p>}
      {data.cases.map(c => <VerificationCasePanel key={phone ? String(c.id) : `${c.id}:${c.version}`} scope={scope} record={c} documents={data.documents} canManage={data.permissions.manage} busy={busy} run={run}/>)}
      {data.permissions.manage && !openCase && <details className="rounded-lg border p-4" open={!data.cases.length}><summary className="cursor-pointer font-medium">{data.cases.length ? "Start another verification round" : "Start verification"}</summary><SmartCreateSection title="Create verification case" mobileSheet={phone} size="standard"><form aria-busy={phone ? busy : undefined} className="hrms-bgv-file-form mt-3 grid gap-3 sm:grid-cols-2" onSubmit={e => {e.preventDefault(); if (phone && busy) return;void run(() => bgv.createRequest({employee_id: employeeId, package_name: packageName, purpose: data.employee.former && purpose === "Current employee review" ? "Historical employee record review" : purpose, vendor_id: vendor ? Number(vendor) : null, expected_completion_date: due || null, checks: checks.map(check_type => ({check_type}))}));}}>
        <label className="text-sm">Package / round name<Input disabled={phone && busy} value={packageName} onChange={e => setPackageName(e.target.value)} required maxLength={120}/></label><label className="text-sm">Purpose<Input disabled={phone && busy} value={purpose} onChange={e => setPurpose(e.target.value)} required maxLength={80}/></label>
        <label className="text-sm">Due date<Input disabled={phone && busy} type="date" value={due} onChange={e => setDue(e.target.value)}/></label><label className="text-sm">Verifier<NativeSelect disabled={phone && busy} aria-label="Verifier" loading={vendors.isFetching} error={vendors.isError} value={vendor} onChange={e => setVendor(e.target.value)} className="h-10 w-full rounded border bg-background px-2"><option value="">Internal HR verification</option>{vendors.data?.filter(v => v.status === "Active").map(v => <option key={v.id} value={v.id}>{v.name}</option>)}</NativeSelect></label>
        {vendors.isError && <p role="alert" className="text-sm">Vendor list could not load. <Button variant="outline" className="underline" type="button" onClick={() => vendors.refetch()}>Retry</Button></p>}
        <fieldset className="sm:col-span-2"><legend className="mb-2 text-sm">Required checks</legend><div className="flex flex-wrap gap-4">{["Identity", "Education", "Employment", "Address", "References"].map(name => <label key={name} className="flex items-center gap-2 text-sm"><input disabled={phone && busy} type="checkbox" checked={checks.includes(name)} onChange={e => setChecks(e.target.checked ? [...checks, name] : checks.filter(c => c !== name))}/>{name}</label>)}</div></fieldset>
        <Button data-save-action={phone || undefined} disabled={busy || !checks.length} type="submit">Create verification case</Button>
      {phone && error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      </form></SmartCreateSection></details>}
    </section>
    <MobileDisclosure maxWidth={480} title="Exit file and issued letters"><Card><CardHeader><CardTitle className="text-base">Exit file and issued letters</CardTitle></CardHeader><CardContent className="space-y-3">
      {data.exits.map(exit => <section key={exit.id} className="space-y-2 border-b pb-3"><h3 className="font-medium">Exit #{exit.id} · {exit.exit_type || "Exit"} · {exit.status}</h3><p className="text-sm">Resignation: {formatDate(exit.resignation_date)} · Last working date: {formatDate(exit.last_working_date)}</p><p className="whitespace-pre-wrap text-sm">{exit.reason}</p><ul className="space-y-1 text-sm">{exit.checklist.map(t => <li key={t.id}>{t.is_completed ? "Complete" : "Pending"}: {t.task_name} · {t.assigned_to_role}{t.remarks ? ` · ${t.remarks}` : ""}</li>)}</ul></section>)}
      {!data.exits.length && <p className="text-sm">{data.restricted.exit ? "Exit records require exit access." : "No exit record recorded."}</p>}
      <p className="text-sm">Login: {data.login_active ? "Active" : "Disabled / no linked account"} · Assigned assets: {data.active_assets === null ? "Restricted" : data.active_assets}</p>
      {data.settlements.map(s => <p key={s.id} className="text-sm">Settlement #{s.id}: {s.status} · {s.paid_at ? `Paid ${formatDate(s.paid_at)}` : "Payment not recorded"}{s.exit_record_id ? ` · Exit #${s.exit_record_id}` : " · Exit linkage missing"}</p>)}
      {data.letters.map(l => <p key={`generated-${l.id}`} className="text-sm">{l.type} · {l.name} {l.file_url && <Button asChild variant="outline"><a className="underline" href={l.file_url} target="_blank" rel="noreferrer">Open letter</a></Button>}</p>)}
      {data.studio_letters.map(l => <p key={`studio-${l.id}`} className="text-sm">{l.type} · {l.name} · {l.status} · {formatDate(l.issue_date)}</p>)}
    </CardContent></Card></MobileDisclosure>
    <details><summary className="cursor-pointer font-medium">Employment lifecycle history</summary><ul className="mt-3 space-y-2 text-sm">{data.history.map(h => <li key={h.id}>{formatDate(h.event_date)} · {h.event_type} · {h.from_status} → {h.to_status} {h.reason && `· ${h.reason}`}</li>)}</ul>{!data.history.length && <p className="mt-2 text-sm">No lifecycle changes recorded.</p>}</details>
  </div>;
}

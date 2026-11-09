import { useMobile } from "@/components/mobile/useMobile";
import { SmartCreateModal } from "@/shared/creation/SmartCreateModal";
import "./background-verification-mobile.css";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import GridTable from "@/shared/data-grid/GridTable";
import { useDeferredValue, useState, useEffect, useRef, useLayoutEffect } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { usePageTitle } from "@/hooks/use-page-title";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { backgroundVerificationApi as bgv } from "@/services/api";
import { formatDate } from "@/lib/utils";
import EmployeeVerificationPanel from "./EmployeeVerificationPanel";
import { verificationError } from "./verificationRecords";


type RegisterRow = {id: number; employee_code: string; name: string; status: string; verification_status: string; overall_result: string | null; due_date: string | null; overdue: boolean; owner_user_id: number | null; owner_name: string | null};
type Register = {permissions: {manage: boolean}; items: RegisterRow[]; total: number; page: number; per_page: number};

export default function BackgroundVerificationPage() {
  usePageTitle("Background Verification & Employee Records");
  const phone = useMobile(480);
  const fileHeading = useRef<HTMLHeadingElement>(null);
  const registerHeading = useRef<HTMLHeadingElement>(null);
  const [params, setParams] = useSearchParams();
  const phoneParams = useRef(new URLSearchParams(params));
  useLayoutEffect(() => { if (phone) phoneParams.current = new URLSearchParams(params); }, [phone, params]);
  // Router navigation commits in a transition. Compose phone inputs against the
  // latest requested URL, including updates that have not rendered yet.
  function changeParams(update: (current: URLSearchParams) => URLSearchParams) {
    if (!phone) { setParams(update); return; }
    const next = update(new URLSearchParams(phoneParams.current));
    phoneParams.current = next;
    setParams(next);
  }
  const [search, setSearch] = useState("");
  const deferred = useDeferredValue(search);
  const population = params.get("population") || "current";
  const verification = params.get("verification") || "all";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const employeeId = Number(params.get("employee_id")) || null;
  const register = useQuery({queryKey: ["bgv-register", population, verification, deferred, page], queryFn: () => bgv.register({population, verification, search: deferred, page, per_page: 25}).then(r => r.data as Register)});
  const qc = useQueryClient();
  const [showVendor, setShowVendor] = useState(false);
  const [vendorName, setVendorName] = useState("");
  const [vendorEmail, setVendorEmail] = useState("");
  const [vendorError, setVendorError] = useState("");
  const [vendorNotice, setVendorNotice] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (!phone || !employeeId) return;
    const frame = requestAnimationFrame(() => { fileHeading.current?.focus(); fileHeading.current?.scrollIntoView({block: "start"}); });
    return () => cancelAnimationFrame(frame);
  }, [phone, employeeId]);
  const canManage = !!register.data?.permissions.manage;
  function filter(key: string, value: string) {changeParams(p => {p.set(key, value); p.delete("page"); p.delete("employee_id"); return p;});}
  const vendorForm = <form aria-busy={saving} className="hrms-bgv-vendor grid gap-3 rounded border p-4 sm:grid-cols-2" onSubmit={async e => {e.preventDefault();if (phone && saving) return;setSaving(true);setVendorError("");setVendorNotice("");try {await bgv.createVendor({name: vendorName, contact_email: vendorEmail || null});await qc.invalidateQueries({queryKey: ["bgv-vendors"]});setVendorName("");setVendorEmail("");setVendorNotice("Verification vendor saved.");if (phone) setShowVendor(false);}catch(err){setVendorError(verificationError(err));}finally{setSaving(false);}}}>
      <label className="text-sm">Vendor name<Input disabled={phone && saving} value={vendorName} onChange={e => setVendorName(e.target.value)} required maxLength={150}/></label><label className="text-sm">Contact email<Input disabled={phone && saving} type="email" value={vendorEmail} onChange={e => setVendorEmail(e.target.value)} maxLength={150}/></label><Button disabled={saving || !vendorName.trim()} data-save-action type="submit">Save vendor</Button>{vendorError && <p role="alert" className="text-sm text-destructive">{vendorError}</p>}{vendorNotice && <p role="status" className="text-sm">{vendorNotice}</p>}
    </form>;
  return <div className="hrms-bgv-register space-y-5">
    <header className="flex flex-wrap items-start justify-between gap-3"><div><h1 ref={registerHeading} tabIndex={phone ? -1 : undefined} className="text-2xl font-semibold">Background verification & employee records</h1><p className="mt-1 text-sm text-muted-foreground">Current and former employee files, verification history, evidence and exit dependencies.</p></div><div className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => {void register.refetch(); void qc.invalidateQueries({queryKey: ["bgv-employee-file"]});}}>Refresh</Button>{canManage && <Button variant="outline" onClick={() => setShowVendor(!showVendor)}>Add verification vendor</Button>}</div></header>
    {phone && vendorNotice && <p role="status" className="text-sm">{vendorNotice}</p>}
    {showVendor && (phone ? <SmartCreateModal definition={{entity: "verification-vendor", title: "Save vendor", presentation: "page", size: "compact"}} mobileSheet busy={saving} onClose={() => setShowVendor(false)}>{vendorForm}</SmartCreateModal> : <SmartCreateSection title="Save vendor" autoOpen onClose={() => setShowVendor(false)} size="compact">{vendorForm}</SmartCreateSection>)}
    <div className="flex flex-wrap gap-2" aria-label="Employee population">{[["current", "Current employees"], ["former", "Former employees"], ["all", "All employees"]].map(([value,label]) => <Button key={value} variant={population === value ? "default" : "outline"} aria-pressed={population === value} onClick={() => filter("population", value)}>{label}</Button>)}</div>
    <div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Find employee<Input placeholder="Name or employee code" value={search} onChange={e => {setSearch(e.target.value);changeParams(p => {p.delete("page");return p;});}}/></label><label className="text-sm">Verification filter<NativeSelect aria-label="Verification filter" className="h-10 w-full rounded border bg-background px-2" value={verification} onChange={e => filter("verification", e.target.value)}>{[["all","All verification states"],["unassessed","Not assessed"],["open","Open cases"],["overdue","Overdue cases"],["reviewed","Reviewed cases"]].map(([value,label]) => <option key={value} value={value}>{label}</option>)}</NativeSelect></label></div>
    {register.isPending && <p role="status">Loading employee register…</p>}
    {register.isError && <p role="alert">{verificationError(register.error)} <Button variant="outline" onClick={() => register.refetch()}>Retry</Button></p>}
    {register.data && <><p className="text-sm text-muted-foreground">{register.data.total} employees match these filters. Missing verification records remain visible as Not Assessed.</p><div className="overflow-x-auto rounded-lg border"><GridTable gridId="BackgroundVerificationPage:collection-1" externalPagination={phone} className="w-full text-left text-sm"><caption className="sr-only">Employee verification register</caption><thead className="border-b bg-muted/40"><tr>{["Employee", "Employment", "Verification", "Due / owner", "Records"].map(h => <th key={h} className="p-3 font-medium">{h}</th>)}</tr></thead><tbody>{register.data.items.map(row => <tr key={row.id} className="border-b last:border-0"><td className="p-3"><p className="font-medium">{row.name}</p><p className="text-xs text-muted-foreground">{row.employee_code}</p></td><td className="p-3">{row.status}</td><td className="p-3">{row.verification_status}{row.overall_result && <p>{row.overall_result}</p>}</td><td className="p-3">{formatDate(row.due_date)}{row.overdue && <p className="font-medium text-destructive">Overdue</p>}<p className="text-xs">{row.owner_name || "Unassigned"}</p></td><td className="p-3"><Button size="sm" variant="outline" aria-label={phone ? `View details for employee ${row.name}` : undefined} onClick={() => {changeParams(p => {p.set("employee_id", String(row.id));return p;});}}>Open file</Button></td></tr>)}</tbody></GridTable>{!register.data.items.length && <p className="p-4 text-sm">No employees match these filters.</p>}</div><div className="flex items-center justify-between gap-2 text-sm"><Button variant="outline" disabled={page <= 1} onClick={() => changeParams(p => {p.set("page", String(page-1));return p;})}>Previous</Button><span>Page {page} of {Math.max(1,Math.ceil(register.data.total / 25))}</span><Button variant="outline" disabled={page*25 >= register.data.total} onClick={() => changeParams(p => {p.set("page",String(page+1));return p;})}>Next</Button></div></>}
    {employeeId && <section className="space-y-3 border-t pt-5"><div className="flex flex-wrap justify-between gap-2"><h2 ref={fileHeading} tabIndex={phone ? -1 : undefined} className="text-xl font-semibold">Employee file</h2>{phone && <Button variant="outline" onClick={() => {requestAnimationFrame(() => {registerHeading.current?.focus();registerHeading.current?.scrollIntoView({block:"start"});});}}>Back to register</Button>}<Button asChild variant="outline"><Link className="text-sm underline" to={`/hrms/employees/${employeeId}?tab=verification`}>Open in employee profile</Link></Button></div><EmployeeVerificationPanel key={employeeId} employeeId={employeeId}/></section>}
  </div>;
}

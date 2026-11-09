import { useMobile } from "@/components/mobile/useMobile";
import { MobileDisclosure } from "@/components/mobile/MobilePrimitives";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import "./ess-mobile.css";
import { useQuery } from "@tanstack/react-query";

import { CalendarDays, Clock, Download, FileText, Inbox, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { employeeApi, leaveApi, reportsApi } from "@/services/api";
import { usePageTitle } from "@/hooks/use-page-title";
import { assetUrl, formatCurrency } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";
import MyAssetsPanel from "../assets/MyAssetsPanel";

export default function ESSPortalPage() {
  usePageTitle("ESS Portal");
  const phone = useMobile(480);
  const [section, setSection] = useState("overview");
  const [fileSection, setFileSection] = useState("payslips");
  const user = useAuthStore((state) => state.user);
  const hasEmployeeProfile = Boolean(user?.employee_id);
  useEffect(() => {if(phone && !hasEmployeeProfile && section==="assets")setSection("overview");}, [phone,hasEmployeeProfile,section]);
  const completeness = useQuery({ queryKey: ["profile-completeness"], queryFn: () => employeeApi.profileCompleteness().then((r) => r.data), retry: false, enabled: hasEmployeeProfile });
  const summary = useQuery({ queryKey: ["ess-summary"], queryFn: () => reportsApi.essSummary().then((r) => r.data), retry: false, enabled: hasEmployeeProfile });
  const leaveBalance = useQuery({ queryKey: ["ess-leave-balance"], queryFn: () => leaveApi.balance(new Date().getFullYear()).then((r) => r.data), retry: false, enabled: hasEmployeeProfile });

  const actions = [
    ["My Profile", "Photo, data completeness, and personal information", UserRound, "/hrms/profile"],
    ["My Attendance", "Monthly view, status, hours, and overtime", Clock, "/hrms/my-attendance"],
    ["My Leave", "Request leave and track approvals", CalendarDays, "/hrms/leave"],
    ["My Requests", "Track submitted HR and payroll requests", Inbox, "/hrms/workflow"],
    ["My Expenses", "Claims, approvals and outstanding reimbursements", FileText, "/hrms/expenses"],
  ];

  return (
    <div className="hrms-ess space-y-4 sm:space-y-5">
      <div className="hrms-ess-header rounded-lg border bg-card p-4 sm:p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Employee Self Service</p>
        <h1 className="mt-2 text-xl font-semibold tracking-tight sm:text-2xl">ESS Portal</h1>
        <p className="mt-1 text-sm text-muted-foreground">Profile, leave, attendance, payslips, documents, and requests.</p>
      </div>

      {phone && !hasEmployeeProfile && <p className="hrms-ess-missing text-sm">No employee profile is linked to this login.</p>}
      {phone && <nav className="hrms-ess-sections" aria-label="ESS sections">{[["overview","Overview"],["files","Files"],...(hasEmployeeProfile?[["assets","Assets"]]:[])].map(([key,label]) => <Button key={key} aria-pressed={section===key} variant={section===key?"default":"outline"} onClick={() => setSection(key)}>{label}</Button>)}</nav>}
      {phone && hasEmployeeProfile && <div className="hrms-ess-feedback">{[{label:"profile completeness",retry:"Retry profile completeness",query:completeness},{label:"ESS files",retry:"Retry ESS files",query:summary},{label:"leave balances",retry:"Retry leave balances",query:leaveBalance}].map(({label,retry,query}) => query.isError?<p key={label} role="alert">Could not load {label}. <Button variant="outline" disabled={query.isFetching} onClick={() => void query.refetch()}>{retry}</Button></p>:null)}</div>}
      <div className="hrms-ess-overview grid gap-3 sm:gap-4 lg:grid-cols-[1.1fr_0.9fr]" style={phone && (section!=="overview" || !hasEmployeeProfile)?{display:"none"}:undefined}>
        <Card>
          <CardContent className="p-4 sm:p-5">
            <div className="mb-2 flex justify-between text-sm"><span>Profile completeness</span><span className="font-semibold">{phone && !completeness.data?"—":`${completeness.data?.percent ?? 0}%`}</span></div>
            <div className="h-2 rounded-full bg-muted"><div className="h-2 rounded-full bg-primary" style={{ width: `${completeness.data?.percent ?? 0}%` }} /></div>
            {phone && hasEmployeeProfile && completeness.isLoading && <p role="status">Loading profile completeness…</p>}
            {!!completeness.data?.missing?.length && (phone ? <MobileDisclosure maxWidth={480} title={`Missing profile details (${completeness.data.missing.length})`}><ul className="text-xs text-muted-foreground">{completeness.data.missing.map((field:string) => <li key={field}>{field}</li>)}</ul></MobileDisclosure> : <p className="mt-3 text-xs text-muted-foreground">Missing: {completeness.data.missing.slice(0, 5).join(", ")}</p>)}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="hrms-ess-balances grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 sm:p-5">
            {(phone ? leaveBalance.data || [] : (leaveBalance.data || []).slice(0,4)).map((item: any) => (
              <div key={item.id} className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">{item.leave_type?.code || item.leave_type_id}</p>
                <p className="text-xl font-semibold">{item.available ?? item.allocated}</p>
              </div>
            ))}
            {phone && hasEmployeeProfile && leaveBalance.isLoading && <p role="status" className="col-span-2">Loading leave balances…</p>}
            {phone && hasEmployeeProfile && leaveBalance.isError && !leaveBalance.data && <p className="col-span-2 text-sm">Leave balances unavailable.</p>}
            {!hasEmployeeProfile ? (
              <p className="col-span-2 text-sm text-muted-foreground">No employee profile is linked to this login.</p>
            ) : !(phone && (leaveBalance.isLoading || leaveBalance.isError)) && !leaveBalance.data?.length && <p className="col-span-2 text-sm text-muted-foreground">No leave balances assigned yet.</p>}
          </CardContent>
        </Card>
      </div>

      <div className="hrms-ess-shortcuts grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {actions.map(([label, detail, Icon, href]) => {
          const content = <><Icon className="mb-4 h-5 w-5 text-primary" /><p className="font-medium">{label as string}</p><p className="mt-1 text-sm text-muted-foreground">{detail as string}</p></>;
          const className="rounded-lg border bg-card p-4 shadow-sm transition hover:border-primary/50 hover:shadow-md sm:p-5";
          return phone ? <Link key={label as string} to={href as string} className={className}>{content}</Link> : <a key={label as string} href={href as string} className={className}>{content}</a>;
        })}
      </div>

      {hasEmployeeProfile && <MyAssetsPanel mobileHidden={phone && section!=="assets"} />}
      <div className="hrms-ess-files grid gap-4 xl:grid-cols-2" style={phone && section!=="files"?{display:"none"}:undefined}>
        {phone && <nav className="hrms-ess-file-types" aria-label="ESS file types">{[["payslips","Payslips"],["documents","Documents"]].map(([key,label]) => <Button key={key} aria-pressed={fileSection===key} variant={fileSection===key?"default":"outline"} onClick={() => setFileSection(key)}>{label}</Button>)}</nav>}
        <Card style={phone && fileSection!=="payslips"?{display:"none"}:undefined}>
          <CardHeader><CardTitle className="text-base">My Payslips</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {phone && hasEmployeeProfile && summary.isLoading && <p role="status">Loading payslips…</p>}
            {phone && !hasEmployeeProfile && <p>Link an employee profile to view payslips.</p>}
            {phone && hasEmployeeProfile && summary.isError && !summary.data && <p>Payslips unavailable.</p>}
            {(phone && !hasEmployeeProfile ? [] : summary.data?.payslips || []).map((item: any) => (
              <div key={item.record_id} className="flex flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-medium">{item.month}/{item.year}</p>
                  <p className="text-xs text-muted-foreground">Net {formatCurrency(Number(item.net_salary || 0))}</p>
                </div>
                {item.pdf_url ? <Button asChild variant="outline" size="sm"><a href={assetUrl(item.pdf_url)} target="_blank" rel="noreferrer"><Download className="h-4 w-4" />PDF</a></Button> : <Button asChild variant="outline" size="sm">{phone?<Link to="/hrms/my-payslips">Open</Link>:<a href="/hrms/my-payslips">Open</a>}</Button>}
              </div>
            ))}
            {!(phone && (!hasEmployeeProfile || summary.isLoading || summary.isError)) && !summary.data?.payslips?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No payslips available yet.</p>}
          </CardContent>
        </Card>

        <Card style={phone && fileSection!=="documents"?{display:"none"}:undefined}>
          <CardHeader><CardTitle className="text-base">My Documents</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {phone && hasEmployeeProfile && summary.isLoading && <p role="status">Loading documents…</p>}
            {phone && !hasEmployeeProfile && <p>Link an employee profile to view documents.</p>}
            {phone && hasEmployeeProfile && summary.isError && !summary.data && <p>Documents unavailable.</p>}
            {(phone && !hasEmployeeProfile ? [] : summary.data?.documents || []).map((item: any) => (
              <div key={item.id} className="flex flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-medium">{item.document_name || item.document_type}</p>
                  <p className="text-xs text-muted-foreground">{item.document_type}</p>
                </div>
                {item.file_url && <Button asChild variant="outline" size="sm"><a href={assetUrl(item.file_url)} target="_blank" rel="noreferrer"><FileText className="h-4 w-4" />Open</a></Button>}
              </div>
            ))}
            {!(phone && (!hasEmployeeProfile || summary.isLoading || summary.isError)) && !summary.data?.documents?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No generated documents yet.</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

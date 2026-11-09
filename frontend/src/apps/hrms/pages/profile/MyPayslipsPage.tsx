import { useMobile } from "@/components/mobile/useMobile";
import { useAuthStore } from "@/store/authStore";
import { selectedBranch } from "@/lib/branch-context";
import { useRecordDraft } from "@/hooks/use-record-autosave";
import { AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogTitle, AlertDialogDescription, AlertDialogCancel, AlertDialogAction } from "@/components/ui/alert-dialog";
import "./my-payslips-mobile.css";
import { NativeSelect } from "@/components/ui/native-select";
import { MobileDisclosure } from "@/components/mobile/MobilePrimitives";
import { useEffect, useRef, useState } from "react";
import { isAxiosError } from "axios";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, FileText, Printer } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { payrollApi } from "@/services/api";
import { formatCurrencyPrecise, statusColor } from "@/lib/utils";
import { usePageTitle } from "@/hooks/use-page-title";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

type PayslipLine = {
  component_name?: string;
  name?: string;
  amount?: number;
};

type Payslip = {
  id?: number;
  payroll_record_id?: number;
  record_id?: number;
  status?: string;
  payroll_status?: string;
  currency?: string;
  financial_year?: string;
  ytd_period_label?: string;
  employee?: { first_name?: string; last_name?: string; employee_id?: string };
  working_days?: number;
  earnings?: PayslipLine[];
  deductions?: PayslipLine[];
  reimbursements?: PayslipLine[];
  employer_contributions?: PayslipLine[];
  gross_salary?: number;
  total_deductions?: number;
  net_salary?: number;
  ytd?: Record<string, number>;
};

function lineLabel(line: PayslipLine) {
  return line.component_name || line.name || "Component";
}

function recordId(payslip?: Payslip | null) {
  return payslip?.payroll_record_id || payslip?.record_id || payslip?.id;
}

function payslipScope() {
  const actor = useAuthStore.getState().user;
  let context: (string | null)[] = [];
  try { context = [sessionStorage.getItem("suite-tenant"), sessionStorage.getItem("suite-organization"), selectedBranch()]; } catch { /* Server authorization remains authoritative. */ }
  return JSON.stringify([actor?.id, actor?.employee_id, actor?.role, actor?.primary_role, actor?.is_superuser, actor?.access, ...context]);
}
export default function MyPayslipsPage() {
  const phone = useMobile(480);
  useAuthStore(state => state.user);
  const [, refreshContext] = useState(0);
  useEffect(() => {
    if (!phone) return;
    const changed = () => refreshContext(value => value + 1);
    const events = ["suite:organization-changed", "suite:branch-changed", "suite:record-access-changed"];
    events.forEach(name => window.addEventListener(name, changed));
    return () => events.forEach(name => window.removeEventListener(name, changed));
  }, [phone]);
  const scope = phone ? payslipScope() : "";
  return <PayslipsContent key={phone ? scope : "desktop"} phone={phone} scope={scope} />;
}
function PayslipsContent({ phone, scope }: { phone: boolean; scope: string }) {
  usePageTitle("My Payslips");
  const { toast } = useToast();
  const today = new Date();
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [year, setYear] = useState(today.getFullYear());
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const [question, setQuestion] = useState("");
  const [historyYear, setHistoryYear] = useState("");
  const history = useQuery({
    queryKey: phone ? ["my-payslip-history", scope] : ["my-payslip-history"],
    queryFn: () => payrollApi.myPayslipHistory().then((r) => r.data as { id: number; month: number; year: number; net_salary: number; currency: string; financial_year?: string }[]),
  });

  const payslipQuery = useQuery({
    queryKey: phone ? ["my-payslip", month, year, scope] : ["my-payslip", month, year],
    queryFn: async () => {
      try {
        return (await payrollApi.payslip(month, year)).data as Payslip;
      } catch (error) {
        if (isAxiosError(error) && error.response?.status === 404) return null;
        throw error;
      }
    },
    enabled: Number.isInteger(year) && year >= 2020 && year <= 2100,
    retry: false,
  });

  const draftStorage = useRecordDraft(`my-payslip-question:${scope}:${month}:${year}`, { question }, saved => setQuestion(typeof saved?.question === "string" ? saved.question.slice(0, 4000) : ""), phone);
  const validYear = Number.isInteger(year) && year >= 2020 && year <= 2100;
  const financialYears = Array.from(new Set(history.data?.map(item => item.financial_year).filter(Boolean)));
  const missingHistoryYear = phone && !!historyYear && !financialYears.includes(historyYear);
  useEffect(() => {
    if (!phone) return;
    let original: { node: HTMLDetailsElement; open: boolean }[] = [];
    const restore = () => { original.forEach(({ node, open }) => { node.open = open; }); original = []; };
    const prepare = () => {
      if (original.length) return;
      original = Array.from(root.current?.querySelectorAll<HTMLDetailsElement>(".payslip-print details") || []).map(node => ({ node, open: node.open }));
      original.forEach(({ node }) => { node.open = true; });
    };
    window.addEventListener("beforeprint", prepare); window.addEventListener("afterprint", restore);
    return () => { restore(); window.removeEventListener("beforeprint", prepare); window.removeEventListener("afterprint", restore); };
  }, [phone]);
  const payslip = payslipQuery.data;
  const slipRecordId = recordId(payslip);
  const currency = payslip?.currency || "INR";
  const formatCurrency = (amount: number) => formatCurrencyPrecise(amount, currency);
  const correction = useMutation({
    mutationFn: () => payrollApi.createPayslipQuery({ payroll_record_id: slipRecordId, subject: `Payslip query: ${MONTHS[month - 1]} ${year}`, description: question.trim(), priority: "Medium" }),
    onSuccess: () => { if (phone) { draftStorage.persist({ question: "" }); if (scope !== payslipScope()) return; } setQuestion(""); toast({ title: "Payslip query sent to Payroll" }); },
    onError: () => { if (phone && scope !== payslipScope()) return; toast({ title: "Could not send query", description: "Please retry.", variant: "destructive" }); },
  });

  const downloadPdf = async () => {
    if (!slipRecordId || downloading) return;
    setDownloading(true);
    if (phone) setDownloadError(false);
    try {
      const response = await payrollApi.downloadPayslipPdf(slipRecordId);
      if (phone && scope !== payslipScope()) return;
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = `payslip-${year}-${String(month).padStart(2, "0")}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast({ title: "Payslip download started" });
    } catch {
      if (phone) { if (scope !== payslipScope()) return; setDownloadError(true); }
      toast({ title: "Could not download payslip", description: "Please retry or contact Payroll if this continues.", variant: "destructive" });
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div ref={root} className="hrms-my-payslips-page space-y-6">
      <div>
        <h1 className="page-title">My Payslips</h1>
        <p className="text-sm text-muted-foreground">View and download payslips from finalized payroll.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Payslip Period</CardTitle>
        </CardHeader>
        <CardContent className="hrms-payslip-period grid gap-3 md:grid-cols-[160px_140px_auto]">
          <NativeSelect disabled={phone && correction.isPending} aria-label="Payslip month" value={month} onChange={(event) => { if (phone && Number(event.target.value) === month) return; setMonth(Number(event.target.value)); setQuestion(""); if (phone) correction.reset(); }} className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm">
            {MONTHS.map((label, index) => <option key={label} value={index + 1}>{label}</option>)}
          </NativeSelect>
          <Input disabled={phone && correction.isPending} aria-invalid={phone && !validYear || undefined} aria-describedby={phone && !validYear ? "payslip-year-error" : undefined} aria-label="Payslip year" type="number" value={year || ""} onChange={(event) => { if (phone && Number(event.target.value) === year) return; setYear(Number(event.target.value)); setQuestion(""); if (phone) correction.reset(); }} min={2020} max={2100} />
          {phone && !validYear && <p id="payslip-year-error" role="alert" className="hrms-payslip-year-error text-sm text-destructive">Enter a whole year from 2020 to 2100.</p>}
          <Button variant="outline" disabled={year < 2020 || year > 2100 || payslipQuery.isFetching || phone && (!validYear || correction.isPending)} onClick={() => phone ? void Promise.all([payslipQuery.refetch(), history.refetch()]) : payslipQuery.refetch()}>Load Payslip</Button>
        </CardContent>
      </Card>

      {phone && history.isError && <p role="alert">Payslip history could not load. <Button variant="outline" onClick={() => void history.refetch()}>Retry payslip history</Button></p>}
      {phone && history.isSuccess && !history.data?.length && <p className="text-sm text-muted-foreground">No published payslips in history.</p>}
      {Boolean(history.data?.length) && <MobileDisclosure title="Available payslips" maxWidth={480}><Card className="hrms-payslip-history"><CardHeader><CardTitle className="text-base">Available payslips</CardTitle>
        <NativeSelect aria-label="Payslip financial year" value={historyYear} onChange={event => setHistoryYear(event.target.value)} className="h-10 rounded border p-2"><option value="">All financial years</option>{missingHistoryYear && <option value={historyYear}>{historyYear} (no matches)</option>}{financialYears.map(fy => <option key={fy} value={fy}>{fy}</option>)}</NativeSelect>
      </CardHeader><CardContent className="hrms-payslip-history-list flex flex-wrap gap-2">
        {history.data?.filter(item => !historyYear || item.financial_year === historyYear).map((item) => <Button key={item.id} disabled={phone && correction.isPending} variant={month === item.month && year === item.year ? "default" : "outline"} onClick={() => { if (phone && item.month === month && item.year === year) return; setMonth(item.month); setYear(item.year); setQuestion(""); if (phone) correction.reset(); }}>
          {MONTHS[item.month - 1]} {item.year} · {formatCurrencyPrecise(Number(item.net_salary), item.currency)}
        </Button>)}
        {missingHistoryYear && <p className="text-sm">No payslips match this financial year. <Button variant="outline" onClick={() => setHistoryYear("")}>Show all financial years</Button></p>}
      </CardContent></Card></MobileDisclosure>}

      {phone && !validYear ? null : payslipQuery.isError ? (
        <Card role="alert"><CardContent className="p-8">Could not load your payslip. Please retry. If this continues, ask HR to check your employee profile.<Button variant="outline" className="ml-3" onClick={() => payslipQuery.refetch()}>Retry</Button></CardContent></Card>
      ) : payslipQuery.isLoading ? (
        <Card><CardContent className="p-8"><div className="h-48 rounded-md bg-muted" /></CardContent></Card>
      ) : !payslip ? (
        <Card>
          <CardContent className="p-12 text-center text-muted-foreground">
            <FileText className="mx-auto mb-3 h-10 w-10 opacity-30" />
            No payslip available for {MONTHS[month - 1]} {year}.
          </CardContent>
        </Card>
      ) : (
        <Card className="payslip-print">
          <CardHeader className="gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <CardTitle>Pay Slip</CardTitle>
              <p className="text-sm text-muted-foreground">{MONTHS[month - 1]} {year}</p>
              <Badge className={`mt-2 ${statusColor(payslip.payroll_status || payslip.status || "Locked")}`}>{payslip.payroll_status || payslip.status || "Locked"}</Badge>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => window.print()}>
                <Printer className="mr-2 h-4 w-4" />
                Print
              </Button>
              {slipRecordId ? (
                <Button size="sm" onClick={downloadPdf} disabled={downloading}>
                  <Download className="mr-2 h-4 w-4" />
                  {downloading ? "Preparing PDF…" : "Download PDF"}
                </Button>
              ) : null}
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {phone && downloadError && <p role="alert" className="text-sm text-destructive">PDF could not download. Use Download PDF to retry.</p>}
            <p className="text-xs text-muted-foreground">Protected PDFs use the last four digits of Aadhaar when available, otherwise date of birth in DDMMYYYY format.</p>
            <div className="mobile-only-panel mobile-net-pay"><p className="text-sm text-muted-foreground">Net pay · {MONTHS[month - 1]} {year}</p><strong>{formatCurrency(Number(payslip.net_salary || 0))}</strong></div>
            <MobileDisclosure title="Earnings, deductions & employee details">
            {payslip.employee ? (
              <div className="hrms-payslip-employee grid gap-3 rounded-lg bg-muted/30 p-4 text-sm md:grid-cols-4">
                <div>
                  <p className="text-muted-foreground">Employee</p>
                  <p className="font-medium">{payslip.employee.first_name} {payslip.employee.last_name}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Employee Code</p>
                  <p className="font-medium">{payslip.employee.employee_id || "-"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Working Days</p>
                  <p className="font-medium">{payslip.working_days ?? "-"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Net Salary</p>
                  <p className="font-medium">{formatCurrency(Number(payslip.net_salary || 0))}</p>
                </div>
              </div>
            ) : null}

            <details className="rounded border p-4 md:col-span-2"><summary className="cursor-pointer font-semibold">Understand this payslip</summary><p className="mt-2 text-sm">Earnings are salary components before deductions. Deductions reduce take-home pay and may include tax, statutory contributions, unpaid leave or recoveries. Reimbursements repay approved business expenses. Adjustments appear as their own calculation lines; employer contributions are shown separately from take-home pay.</p><p className="mt-2 text-sm">Compare the listed earnings, deductions and reimbursements with the net amount below. Working days and unpaid leave can change monthly amounts. Use the query form below if a component or adjustment needs an explanation.</p></details>
            <PayslipSection currency={currency} title="Earnings" lines={payslip.earnings || []} totalLabel="Gross Salary" total={payslip.gross_salary || 0} />
            <PayslipSection currency={currency} title="Deductions" lines={payslip.deductions || []} totalLabel="Total Deductions" total={payslip.total_deductions || 0} danger />
            {(payslip.reimbursements || []).length ? <PayslipSection currency={currency} title="Reimbursements" lines={payslip.reimbursements || []} totalLabel="Total Reimbursements" total={(payslip.reimbursements || []).reduce((sum, line) => sum + Number(line.amount || 0), 0)} /> : null}
            {(payslip.employer_contributions || []).length ? <PayslipSection currency={currency} title="Employer Contributions" lines={payslip.employer_contributions || []} totalLabel="Employer Cost" total={(payslip.employer_contributions || []).reduce((sum, line) => sum + Number(line.amount || 0), 0)} /> : null}

            <div className="hrms-payslip-net flex items-center justify-between rounded-lg bg-primary/10 p-4">
              <span className="font-semibold">Net Salary</span>
              <span className="text-xl font-bold text-primary">{formatCurrency(Number(payslip.net_salary || 0))}</span>
            </div>

            {payslip.ytd ? (
              <div className="hrms-payslip-ytd">
                <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Year to Date · {payslip.ytd_period_label || payslip.financial_year || "Financial year"}</h3>
                <div className="grid gap-3 text-sm md:grid-cols-4">
                  {Object.entries(payslip.ytd).map(([key, value]) => (
                    <div key={key} className="rounded-md border p-3">
                      <p className="capitalize text-muted-foreground">{key.replace(/_/g, " ")}</p>
                      <p className="font-semibold">{formatCurrency(Number(value || 0))}</p>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </MobileDisclosure>
            <div className="space-y-2 border-t pt-4 print:hidden">
              <label htmlFor="payslip-question" className="text-sm font-medium">Question about this payslip?</label>
              <textarea disabled={phone && correction.isPending} id="payslip-question" className="flex min-h-20 w-full rounded-md border border-input bg-background p-3 text-sm" maxLength={4000} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Describe the component or amount Payroll should review" />
              {phone && correction.isError && <p role="alert" className="text-sm text-destructive">Query could not send. Your question is retained.</p>}
              {phone && question && <div className="flex flex-wrap items-center gap-2"><p role={draftStorage.status === "unavailable" ? "alert" : "status"} className="text-sm text-muted-foreground">{draftStorage.status === "unavailable" ? "Question draft could not be stored. Keep this page open." : "Question draft kept for this period in this browser tab."}</p><AlertDialog><AlertDialogTrigger asChild><Button variant="outline" disabled={correction.isPending}>Discard query draft</Button></AlertDialogTrigger><AlertDialogContent><AlertDialogTitle>Discard query draft?</AlertDialogTitle><AlertDialogDescription>Your unsent question will be cleared. The payslip stays unchanged.</AlertDialogDescription><AlertDialogCancel>Continue editing</AlertDialogCancel><AlertDialogAction onClick={() => { draftStorage(); setQuestion(""); correction.reset(); }}>Discard draft</AlertDialogAction></AlertDialogContent></AlertDialog></div>}
              <Button disabled={!slipRecordId || !question.trim() || correction.isPending} onClick={() => correction.mutate()}>{correction.isPending ? "Sending…" : "Send query to Payroll"}</Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function PayslipSection({ currency, title, lines, totalLabel, total, danger = false }: { currency: string; title: string; lines: PayslipLine[]; totalLabel: string; total: number; danger?: boolean }) {
  const formatCurrency = (amount: number) => formatCurrencyPrecise(amount, currency);
  return (
    <div className="hrms-payslip-lines">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      <div className="space-y-2">
        {lines.map((line, index) => (
          <div key={`${lineLabel(line)}-${index}`} className="flex justify-between text-sm">
            <span>{lineLabel(line)}</span>
            <span className={`font-medium ${danger ? "text-red-600" : ""}`}>{formatCurrency(Number(line.amount || 0))}</span>
          </div>
        ))}
        {!lines.length ? <p className="text-sm text-muted-foreground">No component lines.</p> : null}
        <div className="flex justify-between border-t pt-2 text-sm font-semibold">
          <span>{totalLabel}</span>
          <span className={danger ? "text-red-600" : "text-green-600"}>{formatCurrency(Number(total || 0))}</span>
        </div>
      </div>
    </div>
  );
}

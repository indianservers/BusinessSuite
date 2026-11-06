import { NativeSelect } from "@/components/ui/native-select";
import { MobileDisclosure } from "@/components/mobile/MobilePrimitives";
import { useState } from "react";
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

export default function MyPayslipsPage() {
  usePageTitle("My Payslips");
  const { toast } = useToast();
  const today = new Date();
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [year, setYear] = useState(today.getFullYear());
  const [downloading, setDownloading] = useState(false);
  const [question, setQuestion] = useState("");
  const [historyYear, setHistoryYear] = useState("");
  const history = useQuery({
    queryKey: ["my-payslip-history"],
    queryFn: () => payrollApi.myPayslipHistory().then((r) => r.data as { id: number; month: number; year: number; net_salary: number; currency: string; financial_year?: string }[]),
  });

  const payslipQuery = useQuery({
    queryKey: ["my-payslip", month, year],
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

  const payslip = payslipQuery.data;
  const slipRecordId = recordId(payslip);
  const currency = payslip?.currency || "INR";
  const formatCurrency = (amount: number) => formatCurrencyPrecise(amount, currency);
  const correction = useMutation({
    mutationFn: () => payrollApi.createPayslipQuery({ payroll_record_id: slipRecordId, subject: `Payslip query: ${MONTHS[month - 1]} ${year}`, description: question.trim(), priority: "Medium" }),
    onSuccess: () => { setQuestion(""); toast({ title: "Payslip query sent to Payroll" }); },
    onError: () => toast({ title: "Could not send query", description: "Please retry.", variant: "destructive" }),
  });

  const downloadPdf = async () => {
    if (!slipRecordId || downloading) return;
    setDownloading(true);
    try {
      const response = await payrollApi.downloadPayslipPdf(slipRecordId);
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
      toast({ title: "Could not download payslip", description: "Please retry or contact Payroll if this continues.", variant: "destructive" });
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">My Payslips</h1>
        <p className="text-sm text-muted-foreground">View and download payslips from finalized payroll.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Payslip Period</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-[160px_140px_auto]">
          <NativeSelect aria-label="Payslip month" value={month} onChange={(event) => { setMonth(Number(event.target.value)); setQuestion(""); }} className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm">
            {MONTHS.map((label, index) => <option key={label} value={index + 1}>{label}</option>)}
          </NativeSelect>
          <Input aria-label="Payslip year" type="number" value={year || ""} onChange={(event) => { setYear(Number(event.target.value)); setQuestion(""); }} min={2020} max={2100} />
          <Button variant="outline" disabled={year < 2020 || year > 2100 || payslipQuery.isFetching} onClick={() => payslipQuery.refetch()}>Load Payslip</Button>
        </CardContent>
      </Card>

      {Boolean(history.data?.length) && <Card><CardHeader><CardTitle className="text-base">Available payslips</CardTitle>
        <NativeSelect aria-label="Payslip financial year" value={historyYear} onChange={event => setHistoryYear(event.target.value)} className="h-10 rounded border p-2"><option value="">All financial years</option>{Array.from(new Set(history.data?.map(item => item.financial_year).filter(Boolean))).map(fy => <option key={fy} value={fy}>{fy}</option>)}</NativeSelect>
      </CardHeader><CardContent className="flex flex-wrap gap-2">
        {history.data?.filter(item => !historyYear || item.financial_year === historyYear).map((item) => <Button key={item.id} variant={month === item.month && year === item.year ? "default" : "outline"} onClick={() => { setMonth(item.month); setYear(item.year); setQuestion(""); }}>
          {MONTHS[item.month - 1]} {item.year} · {formatCurrencyPrecise(Number(item.net_salary), item.currency)}
        </Button>)}
      </CardContent></Card>}

      {payslipQuery.isError ? (
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
            <p className="text-xs text-muted-foreground">Protected PDFs use the last four digits of Aadhaar when available, otherwise date of birth in DDMMYYYY format.</p>
            <div className="mobile-only-panel mobile-net-pay"><p className="text-sm text-muted-foreground">Net pay · {MONTHS[month - 1]} {year}</p><strong>{formatCurrency(Number(payslip.net_salary || 0))}</strong></div>
            <MobileDisclosure title="Earnings, deductions & employee details">
            {payslip.employee ? (
              <div className="grid gap-3 rounded-lg bg-muted/30 p-4 text-sm md:grid-cols-4">
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

            <div className="flex items-center justify-between rounded-lg bg-primary/10 p-4">
              <span className="font-semibold">Net Salary</span>
              <span className="text-xl font-bold text-primary">{formatCurrency(Number(payslip.net_salary || 0))}</span>
            </div>

            {payslip.ytd ? (
              <div>
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
              <textarea id="payslip-question" className="flex min-h-20 w-full rounded-md border border-input bg-background p-3 text-sm" maxLength={4000} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Describe the component or amount Payroll should review" />
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
    <div>
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

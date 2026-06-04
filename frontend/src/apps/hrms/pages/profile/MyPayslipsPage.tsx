import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, FileText, Printer } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { payrollApi } from "@/services/api";
import { formatCurrency, statusColor } from "@/lib/utils";
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

  const payslipQuery = useQuery({
    queryKey: ["my-payslip", month, year],
    queryFn: () => payrollApi.payslip(month, year).then((r) => r.data as Payslip | null),
    retry: false,
  });

  const payslip = payslipQuery.data;
  const slipRecordId = recordId(payslip);

  const downloadPdf = async () => {
    if (!slipRecordId) return;
    const response = await payrollApi.downloadPayslipPdf(slipRecordId);
    const url = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = `payslip-${year}-${String(month).padStart(2, "0")}.pdf`;
    link.click();
    URL.revokeObjectURL(url);
    toast({ title: "Payslip download started" });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">My Payslips</h1>
        <p className="text-sm text-muted-foreground">View and download your published payslips. Payroll operations are restricted.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Payslip Period</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-[160px_140px_auto]">
          <select value={month} onChange={(event) => setMonth(Number(event.target.value))} className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm">
            {MONTHS.map((label, index) => <option key={label} value={index + 1}>{label}</option>)}
          </select>
          <Input type="number" value={year} onChange={(event) => setYear(Number(event.target.value))} min={2020} max={2100} />
          <Button variant="outline" onClick={() => payslipQuery.refetch()}>Load Payslip</Button>
        </CardContent>
      </Card>

      {payslipQuery.isLoading ? (
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
              <Badge className={`mt-2 ${statusColor(payslip.status || "Published")}`}>{payslip.status || "Published"}</Badge>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => window.print()}>
                <Printer className="mr-2 h-4 w-4" />
                Print
              </Button>
              {slipRecordId ? (
                <Button size="sm" onClick={downloadPdf}>
                  <Download className="mr-2 h-4 w-4" />
                  Download PDF
                </Button>
              ) : null}
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
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

            <PayslipSection title="Earnings" lines={payslip.earnings || []} totalLabel="Gross Salary" total={payslip.gross_salary || 0} />
            <PayslipSection title="Deductions" lines={payslip.deductions || []} totalLabel="Total Deductions" total={payslip.total_deductions || 0} danger />
            {(payslip.reimbursements || []).length ? <PayslipSection title="Reimbursements" lines={payslip.reimbursements || []} totalLabel="Total Reimbursements" total={(payslip.reimbursements || []).reduce((sum, line) => sum + Number(line.amount || 0), 0)} /> : null}
            {(payslip.employer_contributions || []).length ? <PayslipSection title="Employer Contributions" lines={payslip.employer_contributions || []} totalLabel="Employer Cost" total={(payslip.employer_contributions || []).reduce((sum, line) => sum + Number(line.amount || 0), 0)} /> : null}

            <div className="flex items-center justify-between rounded-lg bg-primary/10 p-4">
              <span className="font-semibold">Net Salary</span>
              <span className="text-xl font-bold text-primary">{formatCurrency(Number(payslip.net_salary || 0))}</span>
            </div>

            {payslip.ytd ? (
              <div>
                <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Year to Date</h3>
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
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function PayslipSection({ title, lines, totalLabel, total, danger = false }: { title: string; lines: PayslipLine[]; totalLabel: string; total: number; danger?: boolean }) {
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

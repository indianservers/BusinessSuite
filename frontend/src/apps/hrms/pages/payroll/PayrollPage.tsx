import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  DollarSign, FileText, Play, CheckCircle2, RefreshCw,
  ChevronLeft, ChevronRight, Download, ShieldCheck, Building2,
  ClipboardCheck, Eye, Mail, PauseCircle, Settings2, AlertTriangle
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { employeeApi, leavePayrollApi, payrollApi, statutoryComplianceApi } from "@/services/api";
import { assetUrl, formatCurrency, formatDate, statusColor } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";
import { usePageTitle } from "@/hooks/use-page-title";
import { useAuthStore } from "@/store/authStore";

interface PayrollRun {
  id: number;
  month: number;
  year: number;
  status: string;
  total_gross: number;
  total_net: number;
  total_employees: number;
  created_at: string;
}

interface PayslipRecord {
  id: number;
  employee: { first_name: string; last_name: string; employee_id: string };
  gross_salary: number;
  net_salary: number;
  total_deductions: number;
  status: string;
  earnings?: { component_name: string; amount: number }[];
  deductions?: { component_name: string; amount: number }[];
  employer_contributions?: { component_name: string; amount: number }[];
  reimbursements?: { component_name: string; amount: number }[];
  ytd?: {
    gross_salary: number;
    total_deductions: number;
    net_salary: number;
    reimbursements: number;
    employer_contributions: number;
  };
}

interface PayrollVariance {
  id: number;
  employee_id: number;
  current_gross: number;
  previous_gross: number;
  gross_delta_percent: number;
  current_net: number;
  previous_net: number;
  net_delta_percent: number;
  severity: string;
  reason?: string;
}

interface PayrollPreRunCheck {
  id: number;
  check_name: string;
  check_type: string;
  status: string;
  message?: string;
  blocker: boolean;
}

interface PayrollEmployeeOption {
  id: number;
  employee_id?: string;
  first_name?: string;
  last_name?: string;
  work_email?: string | null;
}

interface PayrollReadinessSummary {
  ready: boolean;
  critical_issue_count: number;
  warning_issue_count: number;
  attendance_locked: boolean;
  issues: Record<string, {
    count: number;
    severity?: string;
    employee_ids?: number[];
    items?: unknown[];
    message?: string;
  }>;
}

interface PayrollWorksheetRow {
  id: number;
  employee_id: number;
  input_status: string;
  calculation_status: string;
  approval_status: string;
  status: string;
  gross_salary: number;
  total_deductions: number;
  net_salary: number;
  variance_status: string;
  hold_reason?: string;
  skip_reason?: string;
}

interface SalaryComponent {
  id: number;
  name: string;
  code: string;
  component_type: string;
  calculation_type: string;
  amount: number;
  payslip_group: string;
}

interface SalaryStructure {
  id: number;
  name: string;
  version: string;
  components?: unknown[];
}

interface LegalEntity {
  id: number;
  legal_name: string;
  state?: string;
  pan?: string;
  tan?: string;
  is_default?: boolean;
}

interface LwpFeedRow {
  employeeId: number;
  employeeName: string;
  employeeCode?: string;
  payrollMonth: string;
  leaveLwpDays: number;
  attendanceLwpDays: number;
  manualLwpDays: number;
  lwpDays: number;
  estimatedDeduction: number;
}

interface LwpEntry {
  id: number;
  employeeName: string;
  employeeCode?: string;
  payrollMonth: string;
  lwpDays: number;
  source: string;
  amountDeducted: number;
  payrollRunId?: number | null;
}

interface BankAdviceRow {
  payrollRecordId?: number;
  payroll_record_id?: number;
  employeeCode?: string;
  employee_code?: string;
  employeeName?: string;
  employee_name?: string;
  bankName?: string;
  bank_name?: string;
  accountNumberMasked?: string;
  account_number_masked?: string;
  ifsc?: string;
  netPayable?: number;
  net_payable?: number;
  validationErrors?: string[];
  validation_errors?: string[];
}

interface BankAdvicePreview {
  payrollRunId?: number;
  payroll_run_id?: number;
  payrollMonth?: string;
  payroll_month?: string;
  status: string;
  companyName?: string;
  company_name?: string;
  bankName?: string;
  bank_name?: string;
  totalEmployees?: number;
  total_employees?: number;
  totalAmount?: number;
  total_amount?: number;
  validationErrors?: string[];
  validation_errors?: string[];
  rows: BankAdviceRow[];
}

interface BankAdviceExport {
  id: number;
  exportType?: string;
  export_type?: string;
  bankName?: string;
  bank_name?: string;
  totalEmployees?: number;
  total_employees?: number;
  totalAmount?: number;
  total_amount?: number;
  filePath?: string;
  file_path?: string;
  generatedAt?: string;
  generated_at?: string;
  downloadCount?: number;
  download_count?: number;
}

const MONTHS = [
  "January","February","March","April","May","June",
  "July","August","September","October","November","December"
];

const normalizeRunStatus = (status?: string) => (status || "draft").toLowerCase().replace(/\s+/g, "_");

type PayrollTab = "wizard" | "run" | "viewer" | "variance" | "inputs" | "setup" | "statutory" | "tax" | "tools" | "casebook";

export default function PayrollPage() {
  usePageTitle("Payroll");
  const qc = useQueryClient();
  const { user } = useAuthStore();
  const isEmployee = user?.role === "employee" && !user?.is_superuser;
  const today = new Date();
  const [activeTab, setActiveTab] = useState<PayrollTab>(isEmployee ? "viewer" : "wizard");
  const [wizardStep, setWizardStep] = useState(0);
  const [slipMonth, setSlipMonth] = useState(today.getMonth() + 1);
  const [slipYear, setSlipYear] = useState(today.getFullYear());
  const [runMonth, setRunMonth] = useState(today.getMonth() + 1);
  const [runYear, setRunYear] = useState(today.getFullYear());
  const [readinessError, setReadinessError] = useState<PayrollReadinessSummary | null>(null);
  const [selectedRun, setSelectedRun] = useState<PayrollRun | null>(null);
  const [payGroupName, setPayGroupName] = useState("India Monthly");
  const [payGroupCode, setPayGroupCode] = useState("IN-MONTHLY");
  const [taxSection, setTaxSection] = useState("80C");
  const [taxAmount, setTaxAmount] = useState("150000");
  const [taxProofUrl, setTaxProofUrl] = useState("");
  const [inputPeriodId, setInputPeriodId] = useState("");
  const [lwpMonth, setLwpMonth] = useState(`${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`);
  const [lopEmployeeId, setLopEmployeeId] = useState("");
  const [lopDays, setLopDays] = useState("1");
  const [otEmployeeId, setOtEmployeeId] = useState("");
  const [otHours, setOtHours] = useState("2");
  const [encashEmployeeId, setEncashEmployeeId] = useState("");
  const [encashDays, setEncashDays] = useState("1");
  const [statutoryState, setStatutoryState] = useState("Telangana");
  const [ruleEffectiveFrom, setRuleEffectiveFrom] = useState(`${today.getFullYear()}-04-01`);
  const [ptAmount, setPtAmount] = useState("200");
  const [lwfEmployeeAmount, setLwfEmployeeAmount] = useState("10");
  const [lwfEmployerAmount, setLwfEmployerAmount] = useState("20");
  const [paymentBatchId, setPaymentBatchId] = useState("");
  const [bankAdviceBankName, setBankAdviceBankName] = useState("Payroll Bank");
  const [templateName, setTemplateName] = useState("Default Salary Template");
  const [templateCode, setTemplateCode] = useState("DEFAULT-SALARY");
  const [toolsMonth, setToolsMonth] = useState(today.getMonth() + 1);
  const [toolsYear, setToolsYear] = useState(today.getFullYear());
  const [toolsEmployeeId, setToolsEmployeeId] = useState("");
  const [simCtc, setSimCtc] = useState("1200000");
  const [simState, setSimState] = useState("Telangana");
  const [simReimbursements, setSimReimbursements] = useState("0");
  const [dispatchChannels, setDispatchChannels] = useState<string[]>(["email"]);
  const [advanceEmployeeId, setAdvanceEmployeeId] = useState("");
  const [advanceAmount, setAdvanceAmount] = useState("10000");
  const [advanceReason, setAdvanceReason] = useState("Salary advance request");
  const [queryRecordId, setQueryRecordId] = useState("");
  const [querySubject, setQuerySubject] = useState("Payslip correction");
  const [queryDescription, setQueryDescription] = useState("");
  const [bankFileName, setBankFileName] = useState("HDFC");
  const [taxEmployeeId, setTaxEmployeeId] = useState("");
  const [taxFinancialYear, setTaxFinancialYear] = useState(`${today.getFullYear()}-${String(today.getFullYear() + 1).slice(-2)}`);
  const [taxIncome, setTaxIncome] = useState("1200000");
  const [taxDeductions, setTaxDeductions] = useState("150000");
  const [tds26EmployeeId, setTds26EmployeeId] = useState("");
  const [tds26Amount, setTds26Amount] = useState("0");
  const [form12EmployeeId, setForm12EmployeeId] = useState("");
  const [form12Value, setForm12Value] = useState("0");
  const [portalFileType, setPortalFileType] = useState("PF_ECR");
  const [portalFileUrl, setPortalFileUrl] = useState("");
  const [budgetAmount, setBudgetAmount] = useState("1000000");
  const [budgetDepartmentId, setBudgetDepartmentId] = useState("");
  const [exchangeFrom, setExchangeFrom] = useState("USD");
  const [exchangeRate, setExchangeRate] = useState("83.00");
  const [convertAmount, setConvertAmount] = useState("1000");
  const [toolResults, setToolResults] = useState<Record<string, unknown>>({});
  const [legalName, setLegalName] = useState("Indian Servers Pvt Ltd");
  const [legalState, setLegalState] = useState("Telangana");
  const [legalPan, setLegalPan] = useState("");
  const [legalTan, setLegalTan] = useState("");
  const [componentName, setComponentName] = useState("Basic Salary");
  const [componentCode, setComponentCode] = useState("BASIC");
  const [componentType, setComponentType] = useState("Earning");
  const [componentAmount, setComponentAmount] = useState("50000");
  const [structureName, setStructureName] = useState("India Monthly Structure");
  const [structureVersion, setStructureVersion] = useState("1.0");
  const [selectedRecordId, setSelectedRecordId] = useState<number | null>(null);
  const [slipEmployeeSearch, setSlipEmployeeSearch] = useState("Recovery");
  const [slipEmployeeId, setSlipEmployeeId] = useState("");
  const visibleTabs: PayrollTab[] = isEmployee
    ? ["viewer"]
    : ["wizard", "run", "viewer", "variance", "inputs", "statutory", "tax", "tools", "casebook"];

  useEffect(() => {
    if (isEmployee && activeTab !== "viewer") setActiveTab("viewer");
  }, [activeTab, isEmployee]);

  const { data: payslip, isLoading: loadingSlip } = useQuery({
    queryKey: ["payslip", slipMonth, slipYear, slipEmployeeId, isEmployee],
    queryFn: () => payrollApi.payslip(slipMonth, slipYear, !isEmployee && slipEmployeeId ? Number(slipEmployeeId) : undefined).then((r) => r.data),
    enabled: isEmployee || Boolean(slipEmployeeId),
    retry: false,
  });

  const { data: payslipEmployeeOptions } = useQuery({
    queryKey: ["payslip-employee-options", slipEmployeeSearch],
    queryFn: () => employeeApi.list({ search: slipEmployeeSearch || undefined, limit: 50 }).then((r) => r.data),
    enabled: !isEmployee,
  });

  const { data: runs, isLoading: loadingRuns, refetch: refetchRuns } = useQuery({
    queryKey: ["payroll-runs"],
    queryFn: () => payrollApi.runs().then((r) => r.data),
    retry: false,
  });

  const { data: runRecords } = useQuery({
    queryKey: ["run-records", selectedRun?.id],
    queryFn: () => payrollApi.runRecords(selectedRun!.id).then((r) => r.data),
    enabled: !!selectedRun,
  });

  const { data: runVariance, refetch: refetchVariance } = useQuery({
    queryKey: ["run-variance", selectedRun?.id],
    queryFn: () => payrollApi.runVariance(selectedRun!.id).then((r) => r.data),
    enabled: !!selectedRun,
  });

  const { data: preRunChecks } = useQuery({
    queryKey: ["payroll-pre-run-checks", selectedRun?.id],
    queryFn: () => payrollApi.preRunChecks(selectedRun!.id).then((r) => r.data),
    enabled: !!selectedRun,
  });

  const { data: payGroups } = useQuery({
    queryKey: ["payroll-pay-groups"],
    queryFn: () => payrollApi.payGroups().then((r) => r.data),
  });

  const { data: legalEntities } = useQuery({
    queryKey: ["payroll-legal-entities"],
    queryFn: () => statutoryComplianceApi.legalEntities().then((r) => r.data),
  });

  const { data: salaryComponents } = useQuery({
    queryKey: ["salary-components"],
    queryFn: () => payrollApi.components().then((r) => r.data),
  });

  const { data: salaryStructures } = useQuery({
    queryKey: ["salary-structures"],
    queryFn: () => payrollApi.structures().then((r) => r.data),
  });

  const { data: setupStatutoryProfiles } = useQuery({
    queryKey: ["payroll-setup-statutory-profiles", (legalEntities as LegalEntity[] | undefined)?.[0]?.id],
    queryFn: () => payrollApi.setupStatutoryProfiles({ legal_entity_id: (legalEntities as LegalEntity[])[0].id }).then((r) => r.data),
    enabled: Boolean((legalEntities as LegalEntity[] | undefined)?.[0]?.id),
  });

  const { data: salaryTemplates } = useQuery({
    queryKey: ["salary-templates"],
    queryFn: () => payrollApi.salaryTemplates().then((r) => r.data),
  });

  const { data: payrollPeriods } = useQuery({
    queryKey: ["payroll-periods", runYear],
    queryFn: () => payrollApi.payrollPeriods({ year: runYear }).then((r) => r.data),
  });

  const selectedInputPeriod = Number(inputPeriodId || ((payrollPeriods as { id: number }[] | undefined)?.[0]?.id || 0));
  const payslipEmployees = Array.isArray(payslipEmployeeOptions?.items)
    ? payslipEmployeeOptions.items as PayrollEmployeeOption[]
    : Array.isArray(payslipEmployeeOptions)
      ? payslipEmployeeOptions as PayrollEmployeeOption[]
      : [];

  const { data: payrollInputs } = useQuery({
    queryKey: ["payroll-inputs", selectedInputPeriod],
    queryFn: () => payrollApi.payrollAttendanceInputs({ period_id: selectedInputPeriod }).then((r) => r.data),
    enabled: !!selectedInputPeriod,
  });

  const { data: lopAdjustments } = useQuery({
    queryKey: ["lop-adjustments", selectedInputPeriod],
    queryFn: () => payrollApi.lopAdjustments({ period_id: selectedInputPeriod }).then((r) => r.data),
    enabled: !!selectedInputPeriod,
  });

  const { data: overtimeLines } = useQuery({
    queryKey: ["overtime-lines", selectedInputPeriod],
    queryFn: () => payrollApi.overtimeLines({ period_id: selectedInputPeriod }).then((r) => r.data),
    enabled: !!selectedInputPeriod,
  });

  const { data: encashmentLines } = useQuery({
    queryKey: ["encashment-lines", selectedInputPeriod],
    queryFn: () => payrollApi.leaveEncashmentLines({ period_id: selectedInputPeriod }).then((r) => r.data),
    enabled: !!selectedInputPeriod,
  });

  const { data: lwpFeed } = useQuery({
    queryKey: ["lwp-feed", lwpMonth],
    queryFn: () => leavePayrollApi.lwpFeed(lwpMonth).then((r) => r.data as { preview: LwpFeedRow[]; entries: LwpEntry[] }),
    enabled: !isEmployee,
  });

  const { data: worksheetRows } = useQuery({
    queryKey: ["payroll-worksheet", selectedRun?.id],
    queryFn: () => payrollApi.runWorksheet(selectedRun!.id).then((r) => r.data),
    enabled: !!selectedRun,
  });

  const { data: paymentBatches } = useQuery({
    queryKey: ["payment-batches", selectedRun?.id],
    queryFn: () => payrollApi.paymentBatches({ payroll_run_id: selectedRun!.id }).then((r) => r.data),
    enabled: !!selectedRun,
  });

  const { data: bankAdvicePreview, isLoading: loadingBankAdvice } = useQuery({
    queryKey: ["bank-advice-preview", selectedRun?.id, bankAdviceBankName],
    queryFn: () => payrollApi.bankAdvicePreview(selectedRun!.id, { bank_name: bankAdviceBankName }).then((r) => r.data as BankAdvicePreview),
    enabled: !!selectedRun && activeTab === "run",
  });

  const { data: bankAdviceExports } = useQuery({
    queryKey: ["bank-advice-exports", selectedRun?.id],
    queryFn: () => payrollApi.bankAdviceExports(selectedRun!.id).then((r) => r.data as BankAdviceExport[]),
    enabled: !!selectedRun && activeTab === "run",
  });

  const { data: accountingJournals } = useQuery({
    queryKey: ["accounting-journals", selectedRun?.id],
    queryFn: () => payrollApi.accountingJournals(selectedRun!.id).then((r) => r.data),
    enabled: !!selectedRun,
  });

  const { data: taxCycles } = useQuery({
    queryKey: ["tax-cycles"],
    queryFn: () => payrollApi.taxCycles().then((r) => r.data),
  });

  const { data: pfRules } = useQuery({
    queryKey: ["payroll-pf-rules"],
    queryFn: () => payrollApi.pfRules().then((r) => r.data),
  });

  const { data: esiRules } = useQuery({
    queryKey: ["payroll-esi-rules"],
    queryFn: () => payrollApi.esiRules().then((r) => r.data),
  });

  const { data: ptSlabs } = useQuery({
    queryKey: ["payroll-pt-slabs"],
    queryFn: () => payrollApi.ptSlabs().then((r) => r.data),
  });

  const { data: lwfSlabs } = useQuery({
    queryKey: ["payroll-lwf-slabs"],
    queryFn: () => payrollApi.lwfSlabs().then((r) => r.data),
  });

  const { data: gratuityRules } = useQuery({
    queryKey: ["payroll-gratuity-rules"],
    queryFn: () => payrollApi.gratuityRules().then((r) => r.data),
  });

  const { data: challans } = useQuery({
    queryKey: ["payroll-statutory-challans"],
    queryFn: () => payrollApi.statutoryChallans().then((r) => r.data),
  });

  const activeTaxCycle = Array.isArray(taxCycles) ? taxCycles[0] : null;

  const { data: taxDeclarations } = useQuery({
    queryKey: ["tax-declarations", activeTaxCycle?.id],
    queryFn: () => payrollApi.taxDeclarations({ cycle_id: activeTaxCycle.id }).then((r) => r.data),
    enabled: !!activeTaxCycle,
  });

  const { data: taxProjection } = useQuery({
    queryKey: ["tax-projection", activeTaxCycle?.id],
    queryFn: () => payrollApi.taxProjection({ cycle_id: activeTaxCycle.id }).then((r) => r.data),
    enabled: !!activeTaxCycle && isEmployee && activeTab === "tax",
    retry: false,
  });

  const { data: payslipQueries } = useQuery({
    queryKey: ["payroll-payslip-queries"],
    queryFn: () => payrollApi.payslipQueries().then((r) => r.data),
    enabled: !isEmployee && activeTab === "tools",
  });

  const { data: salaryAdvances } = useQuery({
    queryKey: ["payroll-salary-advances"],
    queryFn: () => payrollApi.salaryAdvances().then((r) => r.data),
    enabled: !isEmployee && activeTab === "tools",
  });

  const { data: bonusPolicies } = useQuery({
    queryKey: ["payroll-bonus-policies"],
    queryFn: () => payrollApi.bonusPolicies().then((r) => r.data),
    enabled: !isEmployee && activeTab === "tools",
  });

  const runMutation = useMutation<unknown, unknown, boolean>({
    mutationFn: (forceRun: boolean) => payrollApi.runPayroll({ month: runMonth, year: runYear, force_run: forceRun }),
    onSuccess: () => {
      setReadinessError(null);
      toast({ title: "Payroll run initiated!" });
      refetchRuns();
    },
    onError: (e: unknown) => {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      if (detail && typeof detail === "object" && "readiness" in detail) {
        const readiness = (detail as { readiness?: PayrollReadinessSummary }).readiness || null;
        setReadinessError(readiness);
        toast({ title: "Payroll readiness failed", description: "Resolve critical issues or use Force Run if authorized.", variant: "destructive" });
        return;
      }
      const msg = typeof detail === "string" ? detail : "Failed to run payroll";
      toast({ title: "Error", description: msg, variant: "destructive" });
    },
  });

  const runStatusMutation = useMutation({
    mutationFn: ({ id, action, forceApprove }: { id: number; action: "approve" | "lock" | "paid"; forceApprove?: boolean }) =>
      payrollApi.approveRun(id, { action, force_approve: Boolean(forceApprove), remarks: forceApprove ? "Force approved from payroll console" : `${action} from payroll console` }),
    onSuccess: (response, variables) => {
      const title = variables.action === "approve" ? "Payroll run approved" : variables.action === "lock" ? "Payroll run locked" : "Payroll run marked paid";
      toast({ title });
      qc.invalidateQueries({ queryKey: ["payroll-runs"] });
      if (selectedRun?.id === variables.id) {
        setSelectedRun({ ...selectedRun, status: response.data.status });
      }
    },
    onError: (e: unknown) => {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      const msg = typeof detail === "string" ? detail : "Approve blocked until payroll inputs are approved and locked";
      toast({ title: "Payroll approval blocked", description: msg, variant: "destructive" });
    },
  });

  const reconcileMutation = useMutation({
    mutationFn: () => payrollApi.reconcilePayrollAttendance({ period_id: selectedInputPeriod, approve_inputs: true }),
    onSuccess: () => {
      toast({ title: "Attendance inputs reconciled" });
      qc.invalidateQueries({ queryKey: ["payroll-inputs"] });
      qc.invalidateQueries({ queryKey: ["overtime-lines"] });
    },
    onError: () => toast({ title: "Could not reconcile attendance", variant: "destructive" }),
  });

  const lwpSyncMutation = useMutation({
    mutationFn: () => leavePayrollApi.lwpSync({ month: lwpMonth, approveInputs: true, includeAttendanceAbsence: true }),
    onSuccess: () => {
      toast({ title: "LWP feed synced to payroll inputs" });
      qc.invalidateQueries({ queryKey: ["lwp-feed"] });
      qc.invalidateQueries({ queryKey: ["payroll-inputs"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Could not sync LWP feed";
      toast({ title: "LWP sync failed", description: msg, variant: "destructive" });
    },
  });

  const worksheetMutation = useMutation({
    mutationFn: (runId: number) => payrollApi.processRunWorksheet(runId),
    onSuccess: () => {
      toast({ title: "Payroll worksheet processed" });
      qc.invalidateQueries({ queryKey: ["payroll-worksheet"] });
      qc.invalidateQueries({ queryKey: ["payroll-runs"] });
    },
    onError: () => toast({ title: "Could not process worksheet", variant: "destructive" }),
  });

  const worksheetRowMutation = useMutation({
    mutationFn: ({ runId, rowId, action, reason }: { runId: number; rowId: number; action: "hold" | "skip" | "clear" | "approve"; reason?: string }) =>
      payrollApi.updateWorksheetRow(runId, rowId, { action, reason }),
    onSuccess: () => {
      toast({ title: "Worksheet row updated" });
      qc.invalidateQueries({ queryKey: ["payroll-worksheet"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Could not update worksheet row";
      toast({ title: "Worksheet update failed", description: msg, variant: "destructive" });
    },
  });

  const lopMutation = useMutation({
    mutationFn: () => payrollApi.createLopAdjustment({
      period_id: selectedInputPeriod,
      employee_id: Number(lopEmployeeId),
      adjustment_days: lopDays,
      reason: "Payroll input adjustment",
      status: "Approved",
    }),
    onSuccess: () => {
      toast({ title: "LOP adjustment added" });
      qc.invalidateQueries({ queryKey: ["lop-adjustments"] });
    },
  });

  const otMutation = useMutation({
    mutationFn: () => payrollApi.createOvertimeLine({
      period_id: selectedInputPeriod,
      employee_id: Number(otEmployeeId),
      hours: otHours,
      multiplier: "1.5",
      status: "Approved",
    }),
    onSuccess: () => {
      toast({ title: "Overtime line added" });
      qc.invalidateQueries({ queryKey: ["overtime-lines"] });
    },
  });

  const encashMutation = useMutation({
    mutationFn: () => payrollApi.createLeaveEncashmentLine({
      period_id: selectedInputPeriod,
      employee_id: Number(encashEmployeeId),
      days: encashDays,
      status: "Approved",
    }),
    onSuccess: () => {
      toast({ title: "Leave encashment line added" });
      qc.invalidateQueries({ queryKey: ["encashment-lines"] });
    },
  });

  const exportMutation = useMutation({
    mutationFn: (exportType: string) => payrollApi.exportRun(selectedRun!.id, exportType),
    onSuccess: (response) => {
      toast({ title: "Payroll export generated", description: response.data.output_file_url });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Export failed";
      toast({ title: "Error", description: msg, variant: "destructive" });
    },
  });

  const legalEntityMutation = useMutation({
    mutationFn: () =>
      statutoryComplianceApi.createLegalEntity({
        legal_name: legalName,
        state: legalState,
        pan: legalPan || undefined,
        tan: legalTan || undefined,
        registered_address: "Registered office",
        is_default: true,
      }),
    onSuccess: () => {
      toast({ title: "Legal entity created" });
      qc.invalidateQueries({ queryKey: ["payroll-legal-entities"] });
      setWizardStep(1);
    },
    onError: () => toast({ title: "Could not create legal entity", variant: "destructive" }),
  });

  const payGroupMutation = useMutation({
    mutationFn: () =>
      payrollApi.createPayGroup({
        name: payGroupName,
        code: payGroupCode,
        description: "Default payroll group",
        pay_frequency: "Monthly",
        legal_entity_id: (legalEntities as LegalEntity[] | undefined)?.[0]?.id,
        state: legalState,
        is_default: true,
      }),
    onSuccess: () => {
      toast({ title: "Pay group created" });
      qc.invalidateQueries({ queryKey: ["payroll-pay-groups"] });
      setWizardStep(2);
    },
    onError: () => toast({ title: "Could not create pay group", variant: "destructive" }),
  });

  const componentMutation = useMutation({
    mutationFn: () =>
      payrollApi.createComponent({
        name: componentName,
        code: componentCode,
        component_type: componentType,
        calculation_type: "Fixed",
        amount: componentAmount,
        payslip_group: componentType === "Deduction" ? "Deductions" : "Earnings",
        display_sequence: componentType === "Deduction" ? 200 : 100,
        is_taxable: componentType === "Earning",
        appears_in_ctc: true,
        appears_in_payslip: true,
      }),
    onSuccess: () => {
      toast({ title: "Salary component created" });
      qc.invalidateQueries({ queryKey: ["salary-components"] });
      setWizardStep(3);
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Could not create component";
      toast({ title: "Component failed", description: msg, variant: "destructive" });
    },
  });

  const structureMutation = useMutation({
    mutationFn: () =>
      payrollApi.createStructure({
        name: structureName,
        version: structureVersion,
        effective_from: `${today.getFullYear()}-04-01`,
        components: (salaryComponents as SalaryComponent[] | undefined || []).slice(0, 8).map((component, index) => ({
          component_id: component.id,
          amount: component.amount || 0,
          order_sequence: index + 1,
        })),
      }),
    onSuccess: () => {
      toast({ title: "Salary structure created" });
      qc.invalidateQueries({ queryKey: ["salary-structures"] });
      setWizardStep(4);
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Create at least one component first";
      toast({ title: "Structure failed", description: msg, variant: "destructive" });
    },
  });

  const salaryTemplateMutation = useMutation({
    mutationFn: () =>
      payrollApi.createSalaryTemplate({
        name: templateName,
        code: templateCode,
        pay_group_id: (payGroups as { id: number }[] | undefined)?.[0]?.id,
        components: [],
      }),
    onSuccess: () => {
      toast({ title: "Salary template created" });
      qc.invalidateQueries({ queryKey: ["salary-templates"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Could not create salary template";
      toast({ title: "Template failed", description: msg, variant: "destructive" });
    },
  });

  const taxCycleMutation = useMutation({
    mutationFn: () =>
      payrollApi.createTaxCycle({
        name: `FY ${today.getFullYear()}-${String(today.getFullYear() + 1).slice(-2)}`,
        financial_year: `${today.getFullYear()}-${String(today.getFullYear() + 1).slice(-2)}`,
        start_date: `${today.getFullYear()}-04-01`,
        end_date: `${today.getFullYear() + 1}-03-31`,
        proof_due_date: `${today.getFullYear() + 1}-01-31`,
      }),
    onSuccess: () => {
      toast({ title: "Tax cycle opened" });
      qc.invalidateQueries({ queryKey: ["tax-cycles"] });
      setWizardStep(5);
    },
    onError: () => toast({ title: "Could not open tax cycle", variant: "destructive" }),
  });

  const setupStatutoryProfileMutation = useMutation({
    mutationFn: () =>
      payrollApi.createSetupStatutoryProfile({
        legal_entity_id: (legalEntities as LegalEntity[] | undefined)?.[0]?.id,
        pf_establishment_code: "PF-SETUP",
        pf_signatory: "Payroll Manager",
        esi_employer_code: "ESI-SETUP",
        pt_registration_number: "PT-SETUP",
        tan_circle: legalState,
        effective_from: ruleEffectiveFrom,
      }),
    onSuccess: () => {
      toast({ title: "Statutory profile created" });
      qc.invalidateQueries({ queryKey: ["payroll-setup-statutory-profiles"] });
      setWizardStep(5);
    },
    onError: () => toast({ title: "Could not create statutory profile", variant: "destructive" }),
  });

  const taxDeclarationMutation = useMutation({
    mutationFn: () =>
      payrollApi.createTaxDeclaration({
        cycle_id: activeTaxCycle.id,
        section: taxSection,
        declared_amount: taxAmount,
        description: "Employee tax declaration",
      }),
    onSuccess: () => {
      toast({ title: "Tax declaration submitted" });
      qc.invalidateQueries({ queryKey: ["tax-declarations"] });
      qc.invalidateQueries({ queryKey: ["tax-projection"] });
    },
    onError: () => toast({ title: "Could not submit declaration", variant: "destructive" }),
  });

  const taxProofMutation = useMutation({
    mutationFn: (declarationId: number) =>
      payrollApi.submitTaxProof({
        declaration_id: declarationId,
        file_url: taxProofUrl || "/uploads/tax/proof-placeholder.pdf",
        original_filename: taxProofUrl.split("/").pop() || "proof-placeholder.pdf",
      }),
    onSuccess: () => {
      toast({ title: "Tax proof submitted" });
      setTaxProofUrl("");
      qc.invalidateQueries({ queryKey: ["tax-declarations"] });
    },
    onError: () => toast({ title: "Could not submit proof", variant: "destructive" }),
  });

  const seedStatutoryMutation = useMutation({
    mutationFn: async () => {
      await payrollApi.createPfRule({ name: `PF ${today.getFullYear()}`, wage_ceiling: "15000", employee_rate: "12", employer_rate: "12", effective_from: ruleEffectiveFrom });
      await payrollApi.createEsiRule({ name: `ESI ${today.getFullYear()}`, wage_threshold: "21000", employee_rate: "0.75", employer_rate: "3.25", effective_from: ruleEffectiveFrom });
      await payrollApi.createPtSlab({ state: statutoryState, salary_from: "20000", employee_amount: ptAmount, effective_from: ruleEffectiveFrom });
      await payrollApi.createLwfSlab({ state: statutoryState, salary_from: "0", employee_amount: lwfEmployeeAmount, employer_amount: lwfEmployerAmount, deduction_month: 12, effective_from: ruleEffectiveFrom });
      await payrollApi.createGratuityRule({ name: `Gratuity ${today.getFullYear()}`, days_per_year: "15", wage_days_divisor: "26", min_service_years: "5", effective_from: ruleEffectiveFrom });
    },
    onSuccess: () => {
      toast({ title: "Statutory rules created" });
      ["payroll-pf-rules", "payroll-esi-rules", "payroll-pt-slabs", "payroll-lwf-slabs", "payroll-gratuity-rules"].forEach((key) =>
        qc.invalidateQueries({ queryKey: [key] })
      );
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Could not create statutory rules";
      toast({ title: "Rule creation failed", description: msg, variant: "destructive" });
    },
  });

  const paymentBatchMutation = useMutation({
    mutationFn: (runId: number) => payrollApi.createPaymentBatch({ payroll_run_id: runId }),
    onSuccess: () => {
      toast({ title: "Payment batch generated" });
      qc.invalidateQueries({ queryKey: ["payment-batches"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Could not generate payment batch";
      toast({ title: "Payment batch failed", description: msg, variant: "destructive" });
    },
  });

  const paymentStatusMutation = useMutation({
    mutationFn: () => payrollApi.importPaymentStatus(Number(paymentBatchId), { lines: [] }),
    onSuccess: () => {
      toast({ title: "Payment status import checked" });
      qc.invalidateQueries({ queryKey: ["payment-batches"] });
    },
  });

  const bankAdviceMutation = useMutation({
    mutationFn: (exportType: "pdf" | "xlsx" | "txt") =>
      payrollApi.generateBankAdvice(selectedRun!.id, {
        export_type: exportType,
        bank_name: bankAdviceBankName,
      }),
    onSuccess: (response) => {
      toast({ title: "Bank advice generated", description: response.data.file_path });
      qc.invalidateQueries({ queryKey: ["bank-advice-preview"] });
      qc.invalidateQueries({ queryKey: ["bank-advice-exports"] });
    },
    onError: (e: unknown) => {
      const detail = (e as { response?: { data?: { detail?: string | { message?: string; validation_errors?: string[] } } } })?.response?.data?.detail;
      const description = typeof detail === "string" ? detail : detail?.validation_errors?.slice(0, 3).join("; ") || detail?.message || "Could not generate bank advice";
      toast({ title: "Bank advice failed", description, variant: "destructive" });
    },
  });

  const bankAdviceDownloadMutation = useMutation({
    mutationFn: (exportItem: BankAdviceExport) => payrollApi.downloadBankAdviceExport(exportItem.id).then((response) => ({ response, exportItem })),
    onSuccess: ({ response, exportItem }) => {
      const blob = new Blob([response.data]);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const exportType = exportItem.export_type || exportItem.exportType || "txt";
      link.href = url;
      link.download = `bank-advice-${exportItem.id}.${exportType}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      qc.invalidateQueries({ queryKey: ["bank-advice-exports"] });
    },
    onError: () => toast({ title: "Could not download bank advice", variant: "destructive" }),
  });

  const journalMutation = useMutation({
    mutationFn: (runId: number) => payrollApi.generateAccountingJournal(runId),
    onSuccess: () => {
      toast({ title: "Accounting journal generated" });
      qc.invalidateQueries({ queryKey: ["accounting-journals"] });
    },
  });

  const statutoryValidationMutation = useMutation({
    mutationFn: (fileType: string) => payrollApi.validateStatutoryFile({ payroll_run_id: selectedRun!.id, file_type: fileType }),
    onSuccess: (response) => {
      toast({ title: "Statutory validation complete", description: `${response.data.status}: ${response.data.error_count} errors` });
    },
  });

  const statutoryTemplateMutation = useMutation({
    mutationFn: (templateType: string) => payrollApi.generateStatutoryTemplate(templateType),
    onSuccess: (response) => {
      toast({ title: "Template generated", description: response.data.file_url });
    },
  });

  const generatePdfMutation = useMutation({
    mutationFn: (recordId: number) => payrollApi.generatePayslipPdf(recordId),
    onSuccess: (response) => {
      toast({ title: "Payslip PDF generated", description: response.data.payslip_pdf_url });
      qc.invalidateQueries({ queryKey: ["run-records"] });
    },
    onError: () => toast({ title: "Could not generate payslip PDF", variant: "destructive" }),
  });

  const publishPayslipsMutation = useMutation({
    mutationFn: (runId: number) => payrollApi.publishPayslips(runId, { send_email: true }),
    onSuccess: (response) => {
      toast({ title: "Payslips published", description: `${response.data.total_payslips} payslips queued for email` });
    },
    onError: () => toast({ title: "Could not publish payslips", variant: "destructive" }),
  });

  const saveToolResult = (key: string, data: unknown, title: string) => {
    setToolResults((current) => ({ ...current, [key]: data }));
    toast({ title });
  };

  const healthDashboardMutation = useMutation({
    mutationFn: () => payrollApi.healthDashboard({ month: toolsMonth, year: toolsYear }),
    onSuccess: (response) => saveToolResult("health", response.data, "Payroll readiness checked"),
    onError: () => toast({ title: "Could not check payroll readiness", variant: "destructive" }),
  });

  const simulateSalaryMutation = useMutation({
    mutationFn: () => payrollApi.simulateSalary({ ctc: simCtc, state: simState, monthly_reimbursements: simReimbursements, currency: "INR" }),
    onSuccess: (response) => saveToolResult("simulation", response.data, "Salary simulated"),
    onError: () => toast({ title: "Could not simulate salary", variant: "destructive" }),
  });

  const prorationMutation = useMutation({
    mutationFn: () => payrollApi.prorationPreview({ employee_id: Number(toolsEmployeeId), month: toolsMonth, year: toolsYear }),
    onSuccess: (response) => saveToolResult("proration", response.data, "Proration preview ready"),
    onError: () => toast({ title: "Could not preview proration", variant: "destructive" }),
  });

  const dispatchPayslipsMutation = useMutation({
    mutationFn: () => payrollApi.dispatchPayslips(selectedRun!.id, dispatchChannels),
    onSuccess: (response) => saveToolResult("dispatch", response.data, "Payslip dispatch completed"),
    onError: () => toast({ title: "Could not dispatch payslips", variant: "destructive" }),
  });

  const createPayslipQueryMutation = useMutation({
    mutationFn: () => payrollApi.createPayslipQuery({ payroll_record_id: Number(queryRecordId), subject: querySubject, description: queryDescription || querySubject, priority: "Medium" }),
    onSuccess: () => {
      toast({ title: "Payslip query created" });
      setQueryDescription("");
      qc.invalidateQueries({ queryKey: ["payroll-payslip-queries"] });
    },
    onError: () => toast({ title: "Could not create payslip query", variant: "destructive" }),
  });

  const resolvePayslipQueryMutation = useMutation({
    mutationFn: (id: number) => payrollApi.resolvePayslipQuery(id, { status: "Resolved", resolution: "Resolved from payroll tools" }),
    onSuccess: () => {
      toast({ title: "Payslip query resolved" });
      qc.invalidateQueries({ queryKey: ["payroll-payslip-queries"] });
    },
  });

  const createSalaryAdvanceMutation = useMutation({
    mutationFn: () => payrollApi.createSalaryAdvance({ employee_id: advanceEmployeeId ? Number(advanceEmployeeId) : undefined, requested_amount: advanceAmount, reason: advanceReason, requested_deduction_month: toolsMonth, requested_deduction_year: toolsYear }),
    onSuccess: () => {
      toast({ title: "Salary advance requested" });
      qc.invalidateQueries({ queryKey: ["payroll-salary-advances"] });
    },
    onError: () => toast({ title: "Could not create salary advance", variant: "destructive" }),
  });

  const reviewSalaryAdvanceMutation = useMutation({
    mutationFn: ({ id, action, amount }: { id: number; action: "approve" | "reject"; amount?: number }) => payrollApi.reviewSalaryAdvance(id, { action, approved_amount: amount, remarks: `${action} from payroll tools` }),
    onSuccess: () => {
      toast({ title: "Salary advance reviewed" });
      qc.invalidateQueries({ queryKey: ["payroll-salary-advances"] });
    },
  });

  const payrollOperationMutation = useMutation({
    mutationFn: async (action: string) => {
      if (!selectedRun && ["arrears", "gratuity", "expenses", "bank-file", "bonus"].includes(action)) throw new Error("Select a payroll run first");
      if (action === "arrears") return payrollApi.autoCalculateArrears(selectedRun!.id);
      if (action === "gratuity") return payrollApi.generateGratuityAccruals(selectedRun!.id);
      if (action === "expenses") return payrollApi.linkExpenseClaimsToReimbursements(selectedRun!.id);
      if (action === "bank-details") return payrollApi.validateBankDetails({ run_id: selectedRun?.id });
      if (action === "bank-file") return payrollApi.validateBankFile({ run_id: selectedRun!.id, bank_name: bankFileName });
      if (action === "cutoff") return payrollApi.sendCutoffReminders({ month: toolsMonth, year: toolsYear });
      if (action === "periods") return payrollApi.autoGeneratePayrollPeriods({ pay_group_id: (payGroups as { id: number }[] | undefined)?.[0]?.id, year: toolsYear });
      if (action === "bonus-create") return payrollApi.createBonusPolicy({ name: `Festival Bonus ${toolsYear}`, bonus_type: "Festival", amount_type: "Fixed", amount_value: 5000, applicable_month: toolsMonth, description: "Created from payroll tools" });
      if (action === "bonus") return payrollApi.applyBonusPolicy({ payroll_run_id: selectedRun!.id, policy_id: (bonusPolicies as { id: number }[] | undefined)?.[0]?.id });
      throw new Error("Unknown action");
    },
    onSuccess: (response, action) => {
      saveToolResult(`operation_${action}`, response.data, "Payroll operation completed");
      qc.invalidateQueries({ queryKey: ["payroll-bonus-policies"] });
      qc.invalidateQueries({ queryKey: ["run-records"] });
    },
    onError: (error: unknown) => toast({ title: "Payroll operation failed", description: readableApiError(error), variant: "destructive" }),
  });

  const taxOptimizerMutation = useMutation({
    mutationFn: () => payrollApi.taxOptimizer({ employee_id: Number(taxEmployeeId || toolsEmployeeId), financial_year: taxFinancialYear, gross_taxable_income: taxIncome, declared_deductions: taxDeductions, hra_exemption: 0, paid_tds: 0 }),
    onSuccess: (response) => saveToolResult("tax_optimizer", response.data, "Tax optimizer ready"),
    onError: () => toast({ title: "Could not run tax optimizer", variant: "destructive" }),
  });

  const complianceToolMutation = useMutation({
    mutationFn: async (action: string) => {
      if (action === "tds26") return payrollApi.reconcileTds26As({ employee_id: Number(tds26EmployeeId || toolsEmployeeId), financial_year: taxFinancialYear, reported_26as_tds: tds26Amount });
      if (action === "form12ba") return payrollApi.generateForm12BA({ employee_id: Number(form12EmployeeId || toolsEmployeeId), financial_year: taxFinancialYear, perquisites: [{ name: "Perquisites", value: Number(form12Value || 0) }] });
      if (action === "portal") return payrollApi.submitStatutoryPortal({ file_type: portalFileType, file_url: portalFileUrl || "manual-upload", portal: portalFileType.includes("ESI") ? "ESIC" : "EPFO" });
      if (action === "certificate") return payrollApi.generateSalaryCertificate({ employee_id: Number(toolsEmployeeId), purpose: "Official salary certificate" });
      throw new Error("Unknown action");
    },
    onSuccess: (response, action) => saveToolResult(`compliance_${action}`, response.data, "Compliance tool completed"),
    onError: () => toast({ title: "Compliance tool failed", variant: "destructive" }),
  });

  const planningToolMutation = useMutation({
    mutationFn: async (action: string) => {
      if (action === "budget") return payrollApi.createPayrollBudget({ month: toolsMonth, year: toolsYear, budget_amount: budgetAmount, department_id: budgetDepartmentId ? Number(budgetDepartmentId) : undefined, currency: "INR" });
      if (action === "variance") return payrollApi.payrollBudgetVariance({ month: toolsMonth, year: toolsYear });
      if (action === "rate") return payrollApi.createExchangeRate({ from_currency: exchangeFrom, to_currency: "INR", rate: exchangeRate, effective_date: `${toolsYear}-${String(toolsMonth).padStart(2, "0")}-01`, source: "Manual" });
      if (action === "convert") return payrollApi.convertCurrency({ amount: convertAmount, from_currency: exchangeFrom, to_currency: "INR" });
      if (action === "analytics") return payrollApi.payrollAnalytics({ month: toolsMonth, year: toolsYear });
      if (action === "report") return payrollApi.createPayrollReport({ name: `Payroll Summary ${toolsMonth}/${toolsYear}`, report_type: "department_salary_cost", filters_json: { month: toolsMonth, year: toolsYear }, columns_json: ["department_id", "amount"] });
      throw new Error("Unknown action");
    },
    onSuccess: (response, action) => saveToolResult(`planning_${action}`, response.data, "Planning tool completed"),
    onError: () => toast({ title: "Planning tool failed", variant: "destructive" }),
  });

  const prevSlipMonth = () => {
    if (slipMonth === 1) { setSlipMonth(12); setSlipYear((y) => y - 1); }
    else setSlipMonth((m) => m - 1);
  };
  const nextSlipMonth = () => {
    if (slipMonth === 12) { setSlipMonth(1); setSlipYear((y) => y + 1); }
    else setSlipMonth((m) => m + 1);
  };
  const selectedPayslipRecord = (runRecords as PayslipRecord[] | undefined || []).find((record) => record.id === selectedRecordId);
  const selectedRunStatus = normalizeRunStatus(selectedRun?.status);
  const bankAdviceValidationErrors = bankAdvicePreview?.validation_errors || bankAdvicePreview?.validationErrors || [];
  const bankAdviceRows = bankAdvicePreview?.rows || [];
  const canGenerateBankAdvice = !!selectedRun && ["approved", "locked", "paid"].includes(selectedRunStatus) && bankAdviceValidationErrors.length === 0;
  const worksheetAction = (row: PayrollWorksheetRow, action: "hold" | "skip" | "clear" | "approve") => {
    if (!selectedRun) return;
    const needsReason = action === "hold" || action === "skip";
    const reason = needsReason ? window.prompt(`${action === "hold" ? "Hold" : "Skip"} reason for employee #${row.employee_id}`) : undefined;
    if (needsReason && !reason) return;
    worksheetRowMutation.mutate({ runId: selectedRun.id, rowId: row.id, action, reason: reason || undefined });
  };
  const healthResult = toolResults.health as { ready?: boolean; attendance_locked?: boolean; issues?: Record<string, { count?: number }> } | undefined;
  const simulationResult = toolResults.simulation as { gross_salary?: number; estimated_take_home?: number; deductions?: Record<string, number>; components?: { component_name: string; monthly_amount: number }[]; warnings?: string[] } | undefined;
  const prorationResult = toolResults.proration as { payable_days?: number; period_days?: number; proration_factor?: number; prorated_monthly_ctc?: number; prorated_basic?: number; prorated_hra?: number } | undefined;
  const dispatchResult = toolResults.dispatch as { notifications_sent?: number } | undefined;
  const taxOptimizerResult = toolResults.tax_optimizer as { recommended_regime?: { regime_code?: string }; projected_savings?: number; recommendations?: { section?: string; suggested_amount?: number; message?: string }[] } | undefined;
  const budgetVarianceResult = toolResults.planning_variance as { rows?: { budget_amount?: number; actual_amount?: number; variance?: number }[] } | undefined;
  const analyticsResult = toolResults.planning_analytics as { records?: number; total_gross_cost?: number; department_salary_cost?: { department_id: string; amount: number }[] } | undefined;
  const toggleDispatchChannel = (channel: string) => {
    setDispatchChannels((current) => current.includes(channel) ? current.filter((item) => item !== channel) : [...current, channel]);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Payroll</h1>
        <p className="page-description">Configure salary setup, run monthly payroll, publish payslips, and review variance.</p>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2 border-b">
        {visibleTabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-2 px-1 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab === "wizard" ? "Setup Wizard" : tab === "run" ? "Run Payroll" : tab === "viewer" ? "Payslip Viewer" : tab === "variance" ? "Variance" : tab === "inputs" ? "Inputs" : tab === "statutory" ? "Statutory" : tab === "tax" ? "Tax" : tab === "tools" ? "Payroll Tools" : "Real Cases"}
          </button>
        ))}
      </div>

      {activeTab === "viewer" && (
        <div className="space-y-4">
          {/* Month navigator */}
          <div className="flex items-center gap-3">
            <Button variant="outline" size="icon" className="h-8 w-8" onClick={prevSlipMonth}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm font-medium w-40 text-center">
              {MONTHS[slipMonth - 1]} {slipYear}
            </span>
            <Button variant="outline" size="icon" className="h-8 w-8" onClick={nextSlipMonth}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>

          <Card>
            <CardHeader>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <CardTitle className="text-base">Run Payslip Browser</CardTitle>
                  <CardDescription>Select a payroll run to render employee payslips, generate PDFs, and bulk publish by email.</CardDescription>
                </div>
                <Button
                  variant="outline"
                  disabled={!selectedRun || publishPayslipsMutation.isPending}
                  onClick={() => selectedRun && publishPayslipsMutation.mutate(selectedRun.id)}
                >
                  <Mail className="mr-2 h-4 w-4" />
                  Bulk publish
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-2">
                {(runs as PayrollRun[] | undefined || []).slice(0, 8).map((run) => (
                  <Button
                    key={run.id}
                    variant={selectedRun?.id === run.id ? "default" : "outline"}
                    size="sm"
                    onClick={() => setSelectedRun(run)}
                  >
                    {MONTHS[run.month - 1]} {run.year}
                  </Button>
                ))}
              </div>
              {selectedRun && (
                <div className="overflow-x-auto rounded-md border">
                  <table className="w-full min-w-[900px] text-sm">
                    <thead className="border-b bg-muted/50">
                      <tr>
                        {["Employee", "Gross", "Deductions", "Net", "Status", "Actions"].map((h) => (
                          <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(runRecords as PayslipRecord[] | undefined || []).map((record) => (
                        <tr key={record.id} className={`border-b ${selectedRecordId === record.id ? "bg-muted/40" : ""}`}>
                          <td className="px-4 py-3 font-medium">{record.employee?.first_name} {record.employee?.last_name}<p className="text-xs text-muted-foreground">{record.employee?.employee_id}</p></td>
                          <td className="px-4 py-3">{formatCurrency(record.gross_salary)}</td>
                          <td className="px-4 py-3">{formatCurrency(record.total_deductions)}</td>
                          <td className="px-4 py-3 font-medium text-green-600">{formatCurrency(record.net_salary)}</td>
                          <td className="px-4 py-3"><Badge variant="outline">{record.status}</Badge></td>
                          <td className="px-4 py-3">
                            <div className="flex flex-wrap gap-2">
                              <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => {
                                setSelectedRecordId(record.id);
                                const employeeId = (record as PayslipRecord & { employee_id?: number }).employee_id;
                                if (employeeId) setSlipEmployeeId(String(employeeId));
                              }}>
                                <Eye className="mr-1 h-3 w-3" /> Preview
                              </Button>
                              <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => generatePdfMutation.mutate(record.id)}>
                                PDF
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          {selectedPayslipRecord && (
            <Card className="payslip-print">
              <CardHeader>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <CardTitle>Employee Payslip Preview</CardTitle>
                    <CardDescription>{selectedPayslipRecord.employee?.first_name} {selectedPayslipRecord.employee?.last_name} | {selectedRun ? `${MONTHS[selectedRun.month - 1]} ${selectedRun.year}` : "Selected run"}</CardDescription>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => generatePdfMutation.mutate(selectedPayslipRecord.id)}>
                    <Download className="mr-2 h-4 w-4" />
                    Generate PDF
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 rounded-md bg-muted/30 p-4 text-sm sm:grid-cols-3">
                  <div><p className="text-muted-foreground">Employee</p><p className="font-medium">{selectedPayslipRecord.employee?.employee_id}</p></div>
                  <div><p className="text-muted-foreground">Gross</p><p className="font-medium">{formatCurrency(selectedPayslipRecord.gross_salary)}</p></div>
                  <div><p className="text-muted-foreground">Net Pay</p><p className="font-medium text-green-600">{formatCurrency(selectedPayslipRecord.net_salary)}</p></div>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-md border p-4">
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Earnings</h3>
                    {(selectedPayslipRecord.earnings || []).length === 0 ? (
                      <p className="text-sm text-muted-foreground">No earning components</p>
                    ) : (
                      <div className="space-y-2">
                        {(selectedPayslipRecord.earnings || []).map((item, index) => (
                          <div key={`${item.component_name}-${index}`} className="flex justify-between text-sm">
                            <span>{item.component_name}</span>
                            <span>{formatCurrency(item.amount)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="rounded-md border p-4">
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Deductions</h3>
                    {(selectedPayslipRecord.deductions || []).length === 0 ? (
                      <p className="text-sm text-muted-foreground">No deduction components</p>
                    ) : (
                      <div className="space-y-2">
                        {(selectedPayslipRecord.deductions || []).map((item, index) => (
                          <div key={`${item.component_name}-${index}`} className="flex justify-between text-sm">
                            <span>{item.component_name}</span>
                            <span>{formatCurrency(item.amount)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="mt-3 flex justify-between border-t pt-3 text-sm font-medium"><span>Total deductions</span><span>{formatCurrency(selectedPayslipRecord.total_deductions)}</span></div>
                  </div>
                  <div className="rounded-md border p-4">
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Employer Contributions</h3>
                    {(selectedPayslipRecord.employer_contributions || []).length === 0 ? (
                      <p className="text-sm text-muted-foreground">No employer contribution components</p>
                    ) : (
                      <div className="space-y-2">
                        {(selectedPayslipRecord.employer_contributions || []).map((item, index) => (
                          <div key={`${item.component_name}-${index}`} className="flex justify-between text-sm">
                            <span>{item.component_name}</span>
                            <span>{formatCurrency(item.amount)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="rounded-md border p-4">
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">YTD</h3>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div><p className="text-muted-foreground">Gross</p><p className="font-medium">{formatCurrency(selectedPayslipRecord.ytd?.gross_salary || 0)}</p></div>
                      <div><p className="text-muted-foreground">Net</p><p className="font-medium">{formatCurrency(selectedPayslipRecord.ytd?.net_salary || 0)}</p></div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {!isEmployee && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Payslip Filters</CardTitle>
                <CardDescription>Search an employee and load their locked payroll payslip for the selected month.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
                <Input value={slipEmployeeSearch} onChange={(event) => setSlipEmployeeSearch(event.target.value)} placeholder="Search employee code or name" />
                <select value={slipEmployeeId} onChange={(event) => setSlipEmployeeId(event.target.value)} className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm">
                  <option value="">Select employee</option>
                  {payslipEmployees.map((employee) => (
                    <option key={employee.id} value={employee.id}>
                      {employee.employee_id} - {employee.first_name} {employee.last_name}
                    </option>
                  ))}
                </select>
                <Button variant="outline" onClick={() => qc.invalidateQueries({ queryKey: ["payslip"] })}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Load Payslip
                </Button>
              </CardContent>
            </Card>
          )}

          {loadingSlip ? (
            <Card><CardContent className="p-8 text-center"><div className="h-40 skeleton rounded" /></CardContent></Card>
          ) : !payslip ? (
            <Card className="payslip-print">
              <CardContent className="p-12 text-center text-muted-foreground">
                <FileText className="h-10 w-10 mx-auto mb-3 opacity-30" />
                <p>{!isEmployee && !slipEmployeeId ? "Select an employee to view payslip." : `No payslip available for ${MONTHS[slipMonth - 1]} ${slipYear}`}</p>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Pay Slip</CardTitle>
                    <CardDescription>{MONTHS[slipMonth - 1]} {slipYear}</CardDescription>
                  </div>
                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${statusColor(payslip.status || "Draft")}`}>
                    {payslip.status || "Draft"}
                  </span>
                </div>
                <Button variant="outline" size="sm" className="no-print mt-3" onClick={() => window.print()}>
                  Print payslip
                </Button>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Employee info */}
                {payslip.employee && (
                  <div className="grid grid-cols-2 gap-4 p-4 bg-muted/30 rounded-lg text-sm">
                    <div>
                      <p className="text-muted-foreground">Employee</p>
                      <p className="font-medium">{payslip.employee.first_name} {payslip.employee.last_name}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Employee ID</p>
                      <p className="font-medium">{payslip.employee.employee_id}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Month</p>
                      <p className="font-medium">{MONTHS[slipMonth - 1]} {slipYear}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Working Days</p>
                      <p className="font-medium">{payslip.working_days ?? "-"}</p>
                    </div>
                  </div>
                )}

                {/* Earnings */}
                <div>
                  <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Earnings</h3>
                  <div className="space-y-2">
                    {(payslip.earnings as { component_name: string; amount: number }[] || []).map((e, i) => (
                      <div key={i} className="flex justify-between text-sm">
                        <span>{e.component_name}</span>
                        <span className="font-medium">{formatCurrency(e.amount)}</span>
                      </div>
                    ))}
                    <div className="flex justify-between text-sm font-semibold border-t pt-2">
                      <span>Gross Salary</span>
                      <span className="text-green-600">{formatCurrency(payslip.gross_salary)}</span>
                    </div>
                  </div>
                </div>

                {/* Deductions */}
                <div>
                  <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Deductions</h3>
                  <div className="space-y-2">
                    {(payslip.deductions as { component_name: string; amount: number }[] || []).map((d, i) => (
                      <div key={i} className="flex justify-between text-sm">
                        <span>{d.component_name}</span>
                        <span className="font-medium text-red-600">{formatCurrency(d.amount)}</span>
                      </div>
                    ))}
                    <div className="flex justify-between text-sm font-semibold border-t pt-2">
                      <span>Total Deductions</span>
                      <span className="text-red-600">{formatCurrency(payslip.total_deductions)}</span>
                    </div>
                  </div>
                </div>

                {Array.isArray(payslip.employer_contributions) && payslip.employer_contributions.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Employer Contributions</h3>
                    <div className="space-y-2">
                      {(payslip.employer_contributions as { component_name: string; amount: number }[]).map((item, i) => (
                        <div key={i} className="flex justify-between text-sm">
                          <span>{item.component_name}</span>
                          <span className="font-medium">{formatCurrency(item.amount)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {Array.isArray(payslip.reimbursements) && payslip.reimbursements.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Reimbursements</h3>
                    <div className="space-y-2">
                      {(payslip.reimbursements as { component_name: string; amount: number }[]).map((item, i) => (
                        <div key={i} className="flex justify-between text-sm">
                          <span>{item.component_name}</span>
                          <span className="font-medium text-blue-600">{formatCurrency(item.amount)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Net */}
                <div className="flex justify-between items-center p-4 bg-primary/10 rounded-lg">
                  <span className="font-semibold">Net Salary</span>
                  <span className="text-xl font-bold text-primary">{formatCurrency(payslip.net_salary)}</span>
                </div>

                {payslip.ytd && (
                  <div>
                    <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Year to Date</h3>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
                      <div className="rounded-md border p-3">
                        <p className="text-muted-foreground">Gross</p>
                        <p className="font-semibold">{formatCurrency(payslip.ytd.gross_salary)}</p>
                      </div>
                      <div className="rounded-md border p-3">
                        <p className="text-muted-foreground">Deductions</p>
                        <p className="font-semibold">{formatCurrency(payslip.ytd.total_deductions)}</p>
                      </div>
                      <div className="rounded-md border p-3">
                        <p className="text-muted-foreground">Net</p>
                        <p className="font-semibold">{formatCurrency(payslip.ytd.net_salary)}</p>
                      </div>
                      <div className="rounded-md border p-3">
                        <p className="text-muted-foreground">Reimbursements</p>
                        <p className="font-semibold">{formatCurrency(payslip.ytd.reimbursements)}</p>
                      </div>
                      <div className="rounded-md border p-3">
                        <p className="text-muted-foreground">Employer Cost</p>
                        <p className="font-semibold">{formatCurrency(payslip.ytd.employer_contributions)}</p>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {!isEmployee && activeTab === "run" && (
        <div className="space-y-4">
          {/* Run payroll card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Run Payroll</CardTitle>
              <CardDescription>Process payroll for a specific month</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap items-end gap-4">
                <div className="space-y-1.5">
                  <Label>Month</Label>
                  <select
                    value={runMonth}
                    onChange={(e) => setRunMonth(Number(e.target.value))}
                    className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    {MONTHS.map((m, i) => (
                      <option key={i} value={i + 1}>{m}</option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <Label>Year</Label>
                  <Input
                    type="number"
                    value={runYear}
                    onChange={(e) => setRunYear(Number(e.target.value))}
                    className="w-24"
                    min={2020}
                    max={2100}
                  />
                </div>
                <Button
                  onClick={() => runMutation.mutate(false)}
                  disabled={runMutation.isPending}
                  className="bg-green-600 hover:bg-green-700"
                >
                  <Play className="h-4 w-4 mr-2" />
                  {runMutation.isPending ? "Processing..." : "Run Payroll"}
                </Button>
                {readinessError && (
                  <Button
                    variant="outline"
                    onClick={() => runMutation.mutate(true)}
                    disabled={runMutation.isPending}
                    className="border-amber-500 text-amber-700 hover:bg-amber-50"
                  >
                    <AlertTriangle className="h-4 w-4 mr-2" />
                    Force Run
                  </Button>
                )}
              </div>
              {readinessError && (
                <div className="mt-4 rounded-md border border-amber-300 bg-amber-50 p-4 text-sm">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-700" />
                    <div>
                      <p className="font-medium text-amber-900">Payroll readiness checks blocked this run.</p>
                      <p className="text-amber-800">
                        Critical issues: {readinessError.critical_issue_count}. Warnings: {readinessError.warning_issue_count}.
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 grid gap-2 md:grid-cols-2">
                    {Object.entries(readinessError.issues || {})
                      .filter(([, issue]) => issue.count > 0)
                      .map(([key, issue]) => (
                        <div key={key} className="rounded border border-amber-200 bg-white px-3 py-2">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-medium capitalize">{key.replace(/_/g, " ")}</span>
                            <Badge variant={issue.severity === "Critical" ? "destructive" : "secondary"}>{issue.severity || "Info"}</Badge>
                          </div>
                          <p className="mt-1 text-muted-foreground">
                            {issue.count} issue{issue.count === 1 ? "" : "s"}
                            {issue.message ? ` - ${issue.message}` : ""}
                          </p>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-4">
            {[
              ["Selected run", selectedRun ? `${MONTHS[selectedRun.month - 1]} ${selectedRun.year}` : "Choose a run"],
              ["Employees", selectedRun?.total_employees ?? 0],
              ["Gross", formatCurrency(selectedRun?.total_gross || 0)],
              ["Net", formatCurrency(selectedRun?.total_net || 0)],
            ].map(([label, value]) => (
              <Card key={label}>
                <CardContent className="p-4">
                  <p className="text-sm text-muted-foreground">{label}</p>
                  <p className="mt-1 text-xl font-semibold">{value}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {selectedRun && (
            <Card>
              <CardHeader>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <CardTitle className="text-base">Pre-Run Checks Dashboard</CardTitle>
                    <CardDescription>Blockers must be cleared before approval and publish.</CardDescription>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" onClick={() => worksheetMutation.mutate(selectedRun.id)} disabled={worksheetMutation.isPending}>
                      <RefreshCw className="mr-2 h-4 w-4" />
                      Reprocess
                    </Button>
                    <Button size="sm" onClick={() => runStatusMutation.mutate({ id: selectedRun.id, action: "approve" })} disabled={runStatusMutation.isPending || selectedRunStatus !== "calculated"}>
                      <CheckCircle2 className="mr-2 h-4 w-4" />
                      Approve run
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => runStatusMutation.mutate({ id: selectedRun.id, action: "approve", forceApprove: true })} disabled={runStatusMutation.isPending || selectedRunStatus !== "calculated"}>
                      Force approve
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => runStatusMutation.mutate({ id: selectedRun.id, action: "lock" })} disabled={runStatusMutation.isPending || selectedRunStatus !== "approved"}>
                      Lock
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => runStatusMutation.mutate({ id: selectedRun.id, action: "paid" })} disabled={runStatusMutation.isPending || selectedRunStatus !== "locked"}>
                      Mark paid
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-3">
                {(preRunChecks as PayrollPreRunCheck[] | undefined || []).map((check) => (
                  <div key={check.id} className="rounded-md border p-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-medium">{check.check_name}</p>
                      <Badge variant={check.status === "Passed" ? "secondary" : check.blocker ? "destructive" : "outline"}>{check.status}</Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{check.message || check.check_type}</p>
                  </div>
                ))}
                {!(preRunChecks as PayrollPreRunCheck[] | undefined)?.length && (
                  <div className="rounded-md border p-4 text-sm text-muted-foreground md:col-span-3">
                    No pre-run checks generated yet. Run payroll or process the worksheet to populate checks.
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Runs list */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Payroll Runs</CardTitle>
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => refetchRuns()}>
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[900px] text-sm">
                  <thead className="border-b bg-muted/50">
                    <tr>
                      {["Period", "Employees", "Gross", "Net", "Status", "Actions"].map((h) => (
                        <th key={h} className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wide">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {loadingRuns ? (
                      Array.from({ length: 5 }).map((_, i) => (
                        <tr key={i} className="border-b">
                          <td colSpan={6} className="px-4 py-3"><div className="h-4 skeleton rounded" /></td>
                        </tr>
                      ))
                    ) : !runs || (runs as PayrollRun[]).length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">
                          No payroll runs yet
                        </td>
                      </tr>
                    ) : (
                      (runs as PayrollRun[]).map((run) => (
                        <tr
                          key={run.id}
                          className={`border-b hover:bg-muted/30 cursor-pointer ${selectedRun?.id === run.id ? "bg-muted/50" : ""}`}
                          onClick={() => setSelectedRun(selectedRun?.id === run.id ? null : run)}
                        >
                          <td className="px-4 py-3 font-medium">
                            {MONTHS[run.month - 1]} {run.year}
                          </td>
                          <td className="px-4 py-3">{run.total_employees}</td>
                          <td className="px-4 py-3">{formatCurrency(run.total_gross)}</td>
                          <td className="px-4 py-3 font-medium text-green-600">{formatCurrency(run.total_net)}</td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(run.status)}`}>
                              {run.status}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            {normalizeRunStatus(run.status) === "calculated" && (
                              <Button
                                size="sm"
                                className="bg-green-600 hover:bg-green-700 h-7 text-xs"
                                onClick={(e) => { e.stopPropagation(); runStatusMutation.mutate({ id: run.id, action: "approve" }); }}
                                disabled={runStatusMutation.isPending}
                              >
                                <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                                Approve
                              </Button>
                            )}
                            {normalizeRunStatus(run.status) === "approved" && (
                              <Button
                                variant="outline"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={(e) => { e.stopPropagation(); runStatusMutation.mutate({ id: run.id, action: "lock" }); }}
                                disabled={runStatusMutation.isPending}
                              >
                                Lock
                              </Button>
                            )}
                            {normalizeRunStatus(run.status) === "locked" && (
                              <Button
                                variant="outline"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={(e) => { e.stopPropagation(); runStatusMutation.mutate({ id: run.id, action: "paid" }); }}
                                disabled={runStatusMutation.isPending}
                              >
                                Paid
                              </Button>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {selectedRun && (
            <Card>
              <CardHeader>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <CardTitle className="text-base">
                      {MONTHS[selectedRun.month - 1]} {selectedRun.year} Payroll Review
                    </CardTitle>
                    <CardDescription>Variance, audit-ready export batches, and statutory portal-ready files</CardDescription>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => refetchVariance()}>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Refresh Variance
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {[
                    ["pf_ecr", "PF ECR"],
                    ["esi", "ESI"],
                    ["pt", "PT"],
                    ["lwf", "LWF"],
                    ["tds_24q", "TDS 24Q"],
                    ["tds_26q", "TDS 26Q"],
                    ["bank_advice", "Bank Advice"],
                    ["pay_register", "Pay Register"],
                  ].map(([type, label]) => (
                    <Button
                      key={type}
                      variant="outline"
                      size="sm"
                      onClick={() => exportMutation.mutate(type)}
                      disabled={exportMutation.isPending}
                    >
                      <Download className="h-4 w-4 mr-2" />
                      {label}
                    </Button>
                  ))}
                </div>

                <div className="overflow-x-auto border rounded-md">
                  <table className="w-full min-w-[900px] text-sm">
                    <thead className="border-b bg-muted/50">
                      <tr>
                        {["Employee", "Gross Change", "Net Change", "Severity", "Reason"].map((h) => (
                          <th key={h} className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wide">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {!runVariance || (runVariance as PayrollVariance[]).length === 0 ? (
                        <tr>
                          <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                            No variance data available
                          </td>
                        </tr>
                      ) : (
                        (runVariance as PayrollVariance[]).map((item) => (
                          <tr key={item.id} className="border-b hover:bg-muted/30">
                            <td className="px-4 py-3">#{item.employee_id}</td>
                            <td className="px-4 py-3">
                              {formatCurrency(item.previous_gross)} to {formatCurrency(item.current_gross)}
                              <p className="text-xs text-muted-foreground">{Number(item.gross_delta_percent).toFixed(1)}%</p>
                            </td>
                            <td className="px-4 py-3">
                              {formatCurrency(item.previous_net)} to {formatCurrency(item.current_net)}
                              <p className="text-xs text-muted-foreground">{Number(item.net_delta_percent).toFixed(1)}%</p>
                            </td>
                            <td className="px-4 py-3">
                              <Badge variant="outline">{item.severity}</Badge>
                            </td>
                            <td className="px-4 py-3 text-muted-foreground">{item.reason}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Run detail */}
          {selectedRun && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <CardTitle className="text-base">Payroll Worksheet</CardTitle>
                    <CardDescription>Per-employee calculation status, input status, and approval readiness.</CardDescription>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => worksheetMutation.mutate(selectedRun.id)} disabled={worksheetMutation.isPending}>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Process worksheet
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[900px] text-sm">
                    <thead className="border-b bg-muted/50">
                      <tr>
                        {["Employee", "Input", "Calculation", "Approval", "Net", "Worksheet Actions"].map((h) => (
                          <th key={h} className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wide">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(worksheetRows as PayrollWorksheetRow[] | undefined || []).map((row) => (
                        <tr key={row.id} className="border-b">
                          <td className="px-4 py-3">
                            <span className="font-medium">#{row.employee_id}</span>
                            <p className="text-xs text-muted-foreground">{row.status}</p>
                          </td>
                          <td className="px-4 py-3"><Badge variant="outline">{row.input_status}</Badge></td>
                          <td className="px-4 py-3">{row.calculation_status}</td>
                          <td className="px-4 py-3"><Badge variant={row.approval_status === "Approved" ? "secondary" : row.approval_status === "On Hold" || row.approval_status === "Skipped" ? "destructive" : "outline"}>{row.approval_status}</Badge></td>
                          <td className="px-4 py-3">{formatCurrency(row.net_salary)}</td>
                          <td className="px-4 py-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <Button
                                variant="outline"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={() => worksheetAction(row, "approve")}
                                disabled={worksheetRowMutation.isPending || !!row.hold_reason || !!row.skip_reason || row.approval_status === "Approved"}
                              >
                                Approve
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={() => worksheetAction(row, "hold")}
                                disabled={worksheetRowMutation.isPending || row.approval_status === "Approved"}
                              >
                                <PauseCircle className="mr-1 h-3 w-3" />
                                Hold
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={() => worksheetAction(row, "skip")}
                                disabled={worksheetRowMutation.isPending || row.approval_status === "Approved"}
                              >
                                Skip
                              </Button>
                              {(row.hold_reason || row.skip_reason) && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 text-xs"
                                  onClick={() => worksheetAction(row, "clear")}
                                  disabled={worksheetRowMutation.isPending}
                                >
                                  Clear
                                </Button>
                              )}
                              <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => worksheetMutation.mutate(selectedRun.id)} disabled={worksheetMutation.isPending}>
                                Reprocess
                              </Button>
                            </div>
                            {row.hold_reason && <p className="mt-1 text-xs text-muted-foreground">{row.hold_reason}</p>}
                            {row.skip_reason && <p className="mt-1 text-xs text-muted-foreground">{row.skip_reason}</p>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {selectedRun && (
            <div className="grid gap-4 xl:grid-cols-3">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <CardTitle className="text-base">Payments</CardTitle>
                      <CardDescription>Generate bank advice, track UTR status, and failed payouts.</CardDescription>
                    </div>
                    <Button variant="outline" size="sm" onClick={() => paymentBatchMutation.mutate(selectedRun.id)} disabled={paymentBatchMutation.isPending}>
                      Generate batch
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {(paymentBatches as { id: number; total_amount: number; status: string; generated_file_url?: string }[] | undefined || []).map((batch) => (
                    <div key={batch.id} className="flex items-center justify-between rounded-md border p-3 text-sm">
                      <div>
                        <p className="font-medium">Batch #{batch.id} - {formatCurrency(batch.total_amount)}</p>
                        <p className="text-muted-foreground">{batch.generated_file_url || "File pending"}</p>
                      </div>
                      <Badge variant="outline">{batch.status}</Badge>
                    </div>
                  ))}
                  <div className="flex gap-2">
                    <Input placeholder="Batch ID for status import" value={paymentBatchId} onChange={(event) => setPaymentBatchId(event.target.value)} />
                    <Button variant="outline" onClick={() => paymentStatusMutation.mutate()} disabled={!paymentBatchId}>
                      Check import
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <CardTitle className="text-base">Bank Advice</CardTitle>
                      <CardDescription>Preview salary payment lines and export PDF, Excel, or NEFT text files.</CardDescription>
                    </div>
                    <Badge variant={bankAdviceValidationErrors.length ? "destructive" : "outline"}>
                      {loadingBankAdvice ? "Checking" : `${bankAdviceValidationErrors.length} issues`}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
                    <Input placeholder="Bank name" value={bankAdviceBankName} onChange={(event) => setBankAdviceBankName(event.target.value)} />
                    <div className="flex gap-2">
                      {(["pdf", "xlsx", "txt"] as const).map((type) => (
                        <Button
                          key={type}
                          variant="outline"
                          size="sm"
                          onClick={() => bankAdviceMutation.mutate(type)}
                          disabled={!canGenerateBankAdvice || bankAdviceMutation.isPending}
                        >
                          {type.toUpperCase()}
                        </Button>
                      ))}
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div className="rounded-md border p-2">
                      <p className="text-xs text-muted-foreground">Employees</p>
                      <p className="font-semibold">{bankAdvicePreview?.total_employees ?? bankAdvicePreview?.totalEmployees ?? 0}</p>
                    </div>
                    <div className="col-span-2 rounded-md border p-2">
                      <p className="text-xs text-muted-foreground">Total payable</p>
                      <p className="font-semibold">{formatCurrency(bankAdvicePreview?.total_amount ?? bankAdvicePreview?.totalAmount ?? 0)}</p>
                    </div>
                  </div>
                  {bankAdviceValidationErrors.length > 0 && (
                    <div className="max-h-24 overflow-auto rounded-md border border-destructive/30 bg-destructive/5 p-2 text-xs text-destructive">
                      {bankAdviceValidationErrors.slice(0, 6).map((error) => <p key={error}>{error}</p>)}
                    </div>
                  )}
                  <div className="max-h-48 overflow-auto rounded-md border">
                    <table className="w-full min-w-[760px] text-xs">
                      <thead className="bg-muted/50">
                        <tr>
                          {["Employee", "Bank", "Account", "IFSC", "Net"].map((h) => <th key={h} className="px-2 py-2 text-left">{h}</th>)}
                        </tr>
                      </thead>
                      <tbody>
                        {bankAdviceRows.slice(0, 6).map((row) => (
                          <tr key={row.payroll_record_id || row.payrollRecordId} className="border-t">
                            <td className="px-2 py-2">{row.employee_name || row.employeeName}</td>
                            <td className="px-2 py-2">{row.bank_name || row.bankName || "-"}</td>
                            <td className="px-2 py-2">{row.account_number_masked || row.accountNumberMasked || "-"}</td>
                            <td className="px-2 py-2">{row.ifsc || "-"}</td>
                            <td className="px-2 py-2">{formatCurrency(row.net_payable ?? row.netPayable ?? 0)}</td>
                          </tr>
                        ))}
                        {!loadingBankAdvice && bankAdviceRows.length === 0 && (
                          <tr><td className="px-2 py-4 text-center text-muted-foreground" colSpan={5}>No payable payroll records found.</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground">Export history</p>
                    {(bankAdviceExports || []).slice(0, 4).map((item) => (
                      <div key={item.id} className="flex items-center justify-between rounded-md border p-2 text-xs">
                        <div>
                          <p className="font-medium">{(item.export_type || item.exportType || "").toUpperCase()} - {formatCurrency(item.total_amount ?? item.totalAmount ?? 0)}</p>
                          <p className="text-muted-foreground">{formatDate(item.generated_at || item.generatedAt || "")}</p>
                        </div>
                        <Button variant="ghost" size="sm" onClick={() => bankAdviceDownloadMutation.mutate(item)} disabled={bankAdviceDownloadMutation.isPending}>
                          <Download className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                    {(bankAdviceExports || []).length === 0 && <p className="text-xs text-muted-foreground">No bank advice exports generated yet.</p>}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <CardTitle className="text-base">Accounting</CardTitle>
                      <CardDescription>Generate balanced payroll GL journals for finance posting.</CardDescription>
                    </div>
                    <Button variant="outline" size="sm" onClick={() => journalMutation.mutate(selectedRun.id)} disabled={journalMutation.isPending}>
                      Generate journal
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {(accountingJournals as { id: number; total_debit: number; total_credit: number; status: string }[] | undefined || []).map((journal) => (
                    <div key={journal.id} className="flex items-center justify-between rounded-md border p-3 text-sm">
                      <div>
                        <p className="font-medium">Journal #{journal.id}</p>
                        <p className="text-muted-foreground">
                          Dr {formatCurrency(journal.total_debit)} / Cr {formatCurrency(journal.total_credit)}
                        </p>
                      </div>
                      <Badge variant="outline">{journal.status}</Badge>
                    </div>
                  ))}
                  <div className="flex flex-wrap gap-2">
                    {["pf_ecr", "esi", "pt", "tds_24q", "form_16"].map((type) => (
                      <Button key={type} variant="outline" size="sm" onClick={() => statutoryValidationMutation.mutate(type)}>
                        Validate {type}
                      </Button>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {selectedRun && runRecords && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  {MONTHS[selectedRun.month - 1]} {selectedRun.year} - Employee Records
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[900px] text-sm">
                    <thead className="border-b bg-muted/50">
                      <tr>
                        {["Employee", "Gross", "Deductions", "Net", "Status"].map((h) => (
                          <th key={h} className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wide">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(runRecords as PayslipRecord[]).map((r) => (
                        <tr key={r.id} className="border-b hover:bg-muted/30">
                          <td className="px-4 py-3">
                            <p className="font-medium">{r.employee?.first_name} {r.employee?.last_name}</p>
                            <p className="text-xs text-muted-foreground">{r.employee?.employee_id}</p>
                          </td>
                          <td className="px-4 py-3">{formatCurrency(r.gross_salary)}</td>
                          <td className="px-4 py-3 text-red-600">{formatCurrency(r.total_deductions)}</td>
                          <td className="px-4 py-3 font-medium text-green-600">{formatCurrency(r.net_salary)}</td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(r.status)}`}>
                              {r.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {!isEmployee && activeTab === "variance" && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <CardTitle className="text-base">Variance Report</CardTitle>
                  <CardDescription>Compare each payroll run against previous month and flag large deviations.</CardDescription>
                </div>
                <Button variant="outline" size="sm" onClick={() => refetchVariance()} disabled={!selectedRun}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Refresh variance
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {(runs as PayrollRun[] | undefined || []).slice(0, 10).map((run) => (
                  <Button key={run.id} variant={selectedRun?.id === run.id ? "default" : "outline"} size="sm" onClick={() => setSelectedRun(run)}>
                    {MONTHS[run.month - 1]} {run.year}
                  </Button>
                ))}
              </div>
              <div className="grid gap-3 md:grid-cols-4">
                {[
                  ["Rows", (runVariance as unknown[] | undefined)?.length || 0],
                  ["High/Critical", (runVariance as PayrollVariance[] | undefined || []).filter((item) => ["High", "Critical"].includes(item.severity)).length],
                  ["Current gross", formatCurrency(selectedRun?.total_gross || 0)],
                  ["Current net", formatCurrency(selectedRun?.total_net || 0)],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-md border p-3 text-sm">
                    <p className="text-muted-foreground">{label}</p>
                    <p className="mt-1 text-xl font-semibold">{value}</p>
                  </div>
                ))}
              </div>
              <div className="overflow-x-auto rounded-md border">
                <table className="w-full min-w-[900px] text-sm">
                  <thead className="border-b bg-muted/50">
                    <tr>
                      {["Employee", "Gross Previous", "Gross Current", "Net Previous", "Net Current", "Deviation", "Flag"].map((h) => (
                        <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(runVariance as PayrollVariance[] | undefined || []).map((item) => (
                      <tr key={item.id} className="border-b hover:bg-muted/30">
                        <td className="px-4 py-3">#{item.employee_id}</td>
                        <td className="px-4 py-3">{formatCurrency(item.previous_gross)}</td>
                        <td className="px-4 py-3">{formatCurrency(item.current_gross)}</td>
                        <td className="px-4 py-3">{formatCurrency(item.previous_net)}</td>
                        <td className="px-4 py-3">{formatCurrency(item.current_net)}</td>
                        <td className="px-4 py-3">
                          <p>{Number(item.gross_delta_percent).toFixed(1)}% gross</p>
                          <p className="text-xs text-muted-foreground">{Number(item.net_delta_percent).toFixed(1)}% net</p>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={["High", "Critical"].includes(item.severity) ? "destructive" : "outline"}>
                            {item.severity}
                          </Badge>
                          {item.reason && <p className="mt-1 text-xs text-muted-foreground">{item.reason}</p>}
                        </td>
                      </tr>
                    ))}
                    {!(runVariance as PayrollVariance[] | undefined)?.length && (
                      <tr><td colSpan={7} className="px-4 py-10 text-center text-muted-foreground">Select a run to view month-on-month payroll variance.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {!isEmployee && activeTab === "inputs" && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <CardTitle className="text-base">Payroll Inputs</CardTitle>
                  <CardDescription>Reconcile attendance, LOP, overtime, and leave encashment before payroll approval.</CardDescription>
                </div>
                <div className="flex flex-wrap items-end gap-2">
                  <div className="space-y-1.5">
                    <Label>Period</Label>
                    <select
                      className="h-10 rounded-md border bg-background px-3 text-sm"
                      value={inputPeriodId || selectedInputPeriod || ""}
                      onChange={(event) => setInputPeriodId(event.target.value)}
                    >
                      {(payrollPeriods as { id: number; month: number; year: number; status: string }[] | undefined || []).map((period) => (
                        <option key={period.id} value={period.id}>
                          {MONTHS[period.month - 1]} {period.year} - {period.status}
                        </option>
                      ))}
                    </select>
                  </div>
                  <Button onClick={() => reconcileMutation.mutate()} disabled={!selectedInputPeriod || reconcileMutation.isPending}>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Reconcile and lock
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 md:grid-cols-4">
                {[
                  ["Inputs", (payrollInputs as unknown[] | undefined)?.length || 0],
                  ["LOP Adjustments", (lopAdjustments as unknown[] | undefined)?.length || 0],
                  ["OT Lines", (overtimeLines as unknown[] | undefined)?.length || 0],
                  ["Encashment", (encashmentLines as unknown[] | undefined)?.length || 0],
                ].map(([label, count]) => (
                  <div key={label} className="rounded-md border p-3 text-sm">
                    <p className="text-muted-foreground">{label}</p>
                    <p className="text-2xl font-semibold">{count}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <CardTitle className="text-base">LWP Payroll Feed</CardTitle>
                  <CardDescription>Preview approved leave-without-pay and absence deductions before syncing them into payroll inputs.</CardDescription>
                </div>
                <div className="flex flex-wrap items-end gap-2">
                  <div className="space-y-1.5">
                    <Label>Payroll month</Label>
                    <Input type="month" value={lwpMonth} onChange={(event) => setLwpMonth(event.target.value)} />
                  </div>
                  <Button onClick={() => lwpSyncMutation.mutate()} disabled={!lwpMonth || lwpSyncMutation.isPending}>
                    Sync LWP
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 md:grid-cols-3">
                {[
                  ["Preview rows", lwpFeed?.preview?.length || 0],
                  ["Synced entries", lwpFeed?.entries?.length || 0],
                  ["Estimated deduction", formatCurrency((lwpFeed?.preview || []).reduce((sum, row) => sum + Number(row.estimatedDeduction || 0), 0))],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-md border p-3 text-sm">
                    <p className="text-muted-foreground">{label}</p>
                    <p className="mt-1 text-xl font-semibold">{value}</p>
                  </div>
                ))}
              </div>
              <div className="overflow-x-auto rounded-md border">
                <table className="w-full min-w-[900px] text-sm">
                  <thead className="border-b bg-muted/50">
                    <tr>
                      {["Employee", "Leave LWP", "Attendance LWP", "Manual LOP", "Total LWP", "Estimated deduction"].map((h) => (
                        <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {!(lwpFeed?.preview || []).length ? (
                      <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">No LWP found for this month</td></tr>
                    ) : (
                      lwpFeed!.preview.map((row) => (
                        <tr key={row.employeeId} className="border-b">
                          <td className="px-4 py-3">
                            <p className="font-medium">{row.employeeName}</p>
                            <p className="text-xs text-muted-foreground">{row.employeeCode || `#${row.employeeId}`}</p>
                          </td>
                          <td className="px-4 py-3">{Number(row.leaveLwpDays || 0).toFixed(2)}</td>
                          <td className="px-4 py-3">{Number(row.attendanceLwpDays || 0).toFixed(2)}</td>
                          <td className="px-4 py-3">{Number(row.manualLwpDays || 0).toFixed(2)}</td>
                          <td className="px-4 py-3 font-semibold">{Number(row.lwpDays || 0).toFixed(2)}</td>
                          <td className="px-4 py-3">{formatCurrency(row.estimatedDeduction || 0)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">LOP Adjustment</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Input placeholder="Employee ID" value={lopEmployeeId} onChange={(event) => setLopEmployeeId(event.target.value)} />
                <Input placeholder="Days" value={lopDays} onChange={(event) => setLopDays(event.target.value)} />
                <Button onClick={() => lopMutation.mutate()} disabled={!selectedInputPeriod || !lopEmployeeId}>
                  Add LOP
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Overtime Pay</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Input placeholder="Employee ID" value={otEmployeeId} onChange={(event) => setOtEmployeeId(event.target.value)} />
                <Input placeholder="Hours" value={otHours} onChange={(event) => setOtHours(event.target.value)} />
                <Button onClick={() => otMutation.mutate()} disabled={!selectedInputPeriod || !otEmployeeId}>
                  Add OT
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Leave Encashment</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Input placeholder="Employee ID" value={encashEmployeeId} onChange={(event) => setEncashEmployeeId(event.target.value)} />
                <Input placeholder="Days" value={encashDays} onChange={(event) => setEncashDays(event.target.value)} />
                <Button onClick={() => encashMutation.mutate()} disabled={!selectedInputPeriod || !encashEmployeeId}>
                  Add Encashment
                </Button>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Attendance Inputs</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[900px] text-sm">
                  <thead className="border-b bg-muted/50">
                    <tr>
                      {["Employee", "Working", "Payable", "Paid Leave", "LOP", "OT", "Status"].map((h) => (
                        <th key={h} className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wide">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(payrollInputs as { id: number; employee_id: number; working_days: number; payable_days: number; paid_leave_days: number; lop_days: number; ot_hours: number; source_status: string }[] | undefined || []).map((item) => (
                      <tr key={item.id} className="border-b">
                        <td className="px-4 py-3">#{item.employee_id}</td>
                        <td className="px-4 py-3">{item.working_days}</td>
                        <td className="px-4 py-3">{item.payable_days}</td>
                        <td className="px-4 py-3">{item.paid_leave_days}</td>
                        <td className="px-4 py-3">{item.lop_days}</td>
                        <td className="px-4 py-3">{item.ot_hours}</td>
                        <td className="px-4 py-3"><Badge variant="outline">{item.source_status}</Badge></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {!isEmployee && activeTab === "tools" && (
        <div className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Payroll Health</CardTitle>
                <CardDescription>Check readiness before running payroll.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="space-y-1.5"><Label>Month</Label><Input type="number" min={1} max={12} value={toolsMonth} onChange={(event) => setToolsMonth(Number(event.target.value))} /></div>
                  <div className="space-y-1.5"><Label>Year</Label><Input type="number" value={toolsYear} onChange={(event) => setToolsYear(Number(event.target.value))} /></div>
                  <div className="flex items-end"><Button className="w-full" onClick={() => healthDashboardMutation.mutate()} disabled={healthDashboardMutation.isPending}>Check</Button></div>
                </div>
                {healthResult && (
                  <div className="grid gap-2 text-sm sm:grid-cols-2">
                    <Badge variant={healthResult.ready ? "default" : "destructive"}>{healthResult.ready ? "Ready" : "Not ready"}</Badge>
                    <Badge variant="outline">Attendance {healthResult.attendance_locked ? "locked" : "open"}</Badge>
                    {["missing_salary", "missing_bank", "invalid_bank", "missing_pan"].map((key) => (
                      <div key={key} className="rounded-md border p-3">
                        <p className="text-xs uppercase text-muted-foreground">{key.replace(/_/g, " ")}</p>
                        <p className="text-lg font-semibold">{healthResult.issues?.[key]?.count ?? 0}</p>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">CTC Simulator</CardTitle>
                <CardDescription>Estimate monthly take-home for offer discussions.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="space-y-1.5"><Label>Annual CTC</Label><Input value={simCtc} onChange={(event) => setSimCtc(event.target.value)} /></div>
                  <div className="space-y-1.5"><Label>State</Label><Input value={simState} onChange={(event) => setSimState(event.target.value)} /></div>
                  <div className="space-y-1.5"><Label>Reimb.</Label><Input value={simReimbursements} onChange={(event) => setSimReimbursements(event.target.value)} /></div>
                </div>
                <Button onClick={() => simulateSalaryMutation.mutate()} disabled={simulateSalaryMutation.isPending}>Simulate</Button>
                {simulationResult && (
                  <div className="space-y-3 text-sm">
                    <div className="grid gap-2 sm:grid-cols-3">
                      <div className="rounded-md border p-3"><p className="text-muted-foreground">Gross</p><p className="font-semibold">{formatCurrency(simulationResult.gross_salary || 0)}</p></div>
                      <div className="rounded-md border p-3"><p className="text-muted-foreground">Take-home</p><p className="font-semibold text-green-600">{formatCurrency(simulationResult.estimated_take_home || 0)}</p></div>
                      <div className="rounded-md border p-3"><p className="text-muted-foreground">Deductions</p><p className="font-semibold">{formatCurrency(Object.values(simulationResult.deductions || {}).reduce((sum, value) => sum + Number(value || 0), 0))}</p></div>
                    </div>
                    {(simulationResult.components || []).slice(0, 4).map((item) => (
                      <div key={item.component_name} className="flex justify-between rounded-md bg-muted/40 px-3 py-2"><span>{item.component_name}</span><span>{formatCurrency(item.monthly_amount || 0)}</span></div>
                    ))}
                    {(simulationResult.warnings || []).map((warning) => <p key={warning} className="text-xs text-amber-600">{warning}</p>)}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Proration Preview</CardTitle>
                <CardDescription>Preview joiner/exit partial-month pay.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="space-y-1.5"><Label>Employee ID</Label><Input value={toolsEmployeeId} onChange={(event) => setToolsEmployeeId(event.target.value)} /></div>
                  <div className="space-y-1.5"><Label>Month</Label><Input type="number" min={1} max={12} value={toolsMonth} onChange={(event) => setToolsMonth(Number(event.target.value))} /></div>
                  <div className="space-y-1.5"><Label>Year</Label><Input type="number" value={toolsYear} onChange={(event) => setToolsYear(Number(event.target.value))} /></div>
                </div>
                <Button onClick={() => prorationMutation.mutate()} disabled={prorationMutation.isPending || !toolsEmployeeId}>Preview</Button>
                {prorationResult && (
                  <div className="grid gap-2 text-sm sm:grid-cols-2">
                    {[
                      ["Payable days", prorationResult.payable_days],
                      ["Period days", prorationResult.period_days],
                      ["Factor", prorationResult.proration_factor],
                      ["CTC", formatCurrency(prorationResult.prorated_monthly_ctc || 0)],
                      ["Basic", formatCurrency(prorationResult.prorated_basic || 0)],
                      ["HRA", formatCurrency(prorationResult.prorated_hra || 0)],
                    ].map(([label, value]) => <div key={String(label)} className="rounded-md border p-3"><p className="text-muted-foreground">{label}</p><p className="font-semibold">{value}</p></div>)}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Payslip Dispatch</CardTitle>
                <CardDescription>{selectedRun ? `${MONTHS[selectedRun.month - 1]} ${selectedRun.year}` : "Select a payroll run first."}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {["email", "whatsapp", "sms"].map((channel) => (
                    <Button key={channel} type="button" variant={dispatchChannels.includes(channel) ? "default" : "outline"} size="sm" onClick={() => toggleDispatchChannel(channel)}>
                      {channel.toUpperCase()}
                    </Button>
                  ))}
                </div>
                <Button onClick={() => dispatchPayslipsMutation.mutate()} disabled={!selectedRun || !dispatchChannels.length || dispatchPayslipsMutation.isPending}>
                  <Mail className="mr-2 h-4 w-4" />
                  Dispatch Payslips
                </Button>
                {dispatchResult && <p className="text-sm text-muted-foreground">Notifications sent: <span className="font-semibold text-foreground">{dispatchResult.notifications_sent ?? 0}</span></p>}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Payroll Operations</CardTitle>
                <CardDescription>Run selected payroll maintenance actions.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  <Button variant="outline" onClick={() => payrollOperationMutation.mutate("arrears")} disabled={!selectedRun || payrollOperationMutation.isPending}>Auto Arrears</Button>
                  <Button variant="outline" onClick={() => payrollOperationMutation.mutate("gratuity")} disabled={!selectedRun || payrollOperationMutation.isPending}>Gratuity Accrual</Button>
                  <Button variant="outline" onClick={() => payrollOperationMutation.mutate("expenses")} disabled={!selectedRun || payrollOperationMutation.isPending}>Link Expenses</Button>
                  <Button variant="outline" onClick={() => payrollOperationMutation.mutate("bank-details")} disabled={payrollOperationMutation.isPending}>Bank Details</Button>
                  <Button variant="outline" onClick={() => payrollOperationMutation.mutate("cutoff")} disabled={payrollOperationMutation.isPending}>Cutoff Reminder</Button>
                  <Button variant="outline" onClick={() => payrollOperationMutation.mutate("periods")} disabled={payrollOperationMutation.isPending}>Auto Periods</Button>
                </div>
                <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto]">
                  <Input value={bankFileName} onChange={(event) => setBankFileName(event.target.value)} placeholder="Bank name" />
                  <Button variant="outline" onClick={() => payrollOperationMutation.mutate("bank-file")} disabled={!selectedRun || payrollOperationMutation.isPending}>Validate File</Button>
                  <Button variant="outline" onClick={() => payrollOperationMutation.mutate("bonus-create")} disabled={payrollOperationMutation.isPending}>Create Bonus</Button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {(bonusPolicies as { id: number; name: string }[] | undefined || []).slice(0, 3).map((policy) => <Badge key={policy.id} variant="outline">{policy.name}</Badge>)}
                  <Button size="sm" variant="outline" onClick={() => payrollOperationMutation.mutate("bonus")} disabled={!selectedRun || !(bonusPolicies as unknown[] | undefined)?.length || payrollOperationMutation.isPending}>Apply First Bonus</Button>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Employee Actions</CardTitle>
                <CardDescription>Salary advances and payslip disputes.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 md:grid-cols-4">
                  <Input placeholder="Employee ID" value={advanceEmployeeId} onChange={(event) => setAdvanceEmployeeId(event.target.value)} />
                  <Input placeholder="Amount" value={advanceAmount} onChange={(event) => setAdvanceAmount(event.target.value)} />
                  <Input placeholder="Reason" value={advanceReason} onChange={(event) => setAdvanceReason(event.target.value)} />
                  <Button onClick={() => createSalaryAdvanceMutation.mutate()} disabled={createSalaryAdvanceMutation.isPending}>Request Advance</Button>
                </div>
                <div className="space-y-2">
                  {(salaryAdvances as { id: number; employee_id: number; requested_amount: number; approved_amount?: number; status: string }[] | undefined || []).slice(0, 5).map((item) => (
                    <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3 text-sm">
                      <span>#{item.employee_id} - {formatCurrency(item.requested_amount)}</span>
                      <div className="flex gap-2"><Badge variant="outline">{item.status}</Badge><Button size="sm" variant="outline" onClick={() => reviewSalaryAdvanceMutation.mutate({ id: item.id, action: "approve", amount: Number(item.approved_amount || item.requested_amount) })}>Approve</Button><Button size="sm" variant="outline" onClick={() => reviewSalaryAdvanceMutation.mutate({ id: item.id, action: "reject" })}>Reject</Button></div>
                    </div>
                  ))}
                </div>
                <div className="grid gap-3 md:grid-cols-[0.7fr_1fr_1.5fr_auto]">
                  <Input placeholder="Record ID" value={queryRecordId} onChange={(event) => setQueryRecordId(event.target.value)} />
                  <Input placeholder="Subject" value={querySubject} onChange={(event) => setQuerySubject(event.target.value)} />
                  <Input placeholder="Description" value={queryDescription} onChange={(event) => setQueryDescription(event.target.value)} />
                  <Button onClick={() => createPayslipQueryMutation.mutate()} disabled={!queryRecordId || createPayslipQueryMutation.isPending}>Create Query</Button>
                </div>
                <div className="space-y-2">
                  {(payslipQueries as { id: number; subject: string; status: string; priority?: string }[] | undefined || []).slice(0, 5).map((item) => (
                    <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3 text-sm">
                      <span>{item.subject}</span>
                      <div className="flex gap-2"><Badge variant="outline">{item.status}</Badge><Button size="sm" variant="outline" onClick={() => resolvePayslipQueryMutation.mutate(item.id)}>Resolve</Button></div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Compliance / Tax</CardTitle>
                <CardDescription>Optimizer, reconciliation, Form 12BA, certificate, and portal tracking.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 md:grid-cols-4">
                  <Input placeholder="Employee ID" value={taxEmployeeId} onChange={(event) => setTaxEmployeeId(event.target.value)} />
                  <Input placeholder="FY" value={taxFinancialYear} onChange={(event) => setTaxFinancialYear(event.target.value)} />
                  <Input placeholder="Income" value={taxIncome} onChange={(event) => setTaxIncome(event.target.value)} />
                  <Input placeholder="Deductions" value={taxDeductions} onChange={(event) => setTaxDeductions(event.target.value)} />
                </div>
                <Button onClick={() => taxOptimizerMutation.mutate()} disabled={taxOptimizerMutation.isPending || !(taxEmployeeId || toolsEmployeeId)}>Run Optimizer</Button>
                {taxOptimizerResult && (
                  <div className="rounded-md border p-3 text-sm">
                    <p>Recommended: <span className="font-semibold">{taxOptimizerResult.recommended_regime?.regime_code || "-"}</span></p>
                    {(taxOptimizerResult.recommendations || []).slice(0, 3).map((item) => <p key={`${item.section}-${item.message}`} className="text-muted-foreground">{item.section}: {item.suggested_amount ? formatCurrency(item.suggested_amount) : ""} {item.message}</p>)}
                  </div>
                )}
                <div className="grid gap-3 md:grid-cols-3">
                  <Input placeholder="26AS employee ID" value={tds26EmployeeId} onChange={(event) => setTds26EmployeeId(event.target.value)} />
                  <Input placeholder="Reported TDS" value={tds26Amount} onChange={(event) => setTds26Amount(event.target.value)} />
                  <Button variant="outline" onClick={() => complianceToolMutation.mutate("tds26")} disabled={complianceToolMutation.isPending}>Reconcile 26AS</Button>
                  <Input placeholder="12BA employee ID" value={form12EmployeeId} onChange={(event) => setForm12EmployeeId(event.target.value)} />
                  <Input placeholder="Perquisite value" value={form12Value} onChange={(event) => setForm12Value(event.target.value)} />
                  <Button variant="outline" onClick={() => complianceToolMutation.mutate("form12ba")} disabled={complianceToolMutation.isPending}>Generate 12BA</Button>
                  <Input placeholder="Portal file type" value={portalFileType} onChange={(event) => setPortalFileType(event.target.value)} />
                  <Input placeholder="File URL" value={portalFileUrl} onChange={(event) => setPortalFileUrl(event.target.value)} />
                  <Button variant="outline" onClick={() => complianceToolMutation.mutate("portal")} disabled={complianceToolMutation.isPending}>Portal Submit</Button>
                </div>
                <Button variant="outline" onClick={() => complianceToolMutation.mutate("certificate")} disabled={!toolsEmployeeId || complianceToolMutation.isPending}>Generate Salary Certificate</Button>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Planning / Analytics</CardTitle>
              <CardDescription>Budgets, exchange rates, conversion, analytics, and report definitions.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 md:grid-cols-6">
                <Input placeholder="Budget amount" value={budgetAmount} onChange={(event) => setBudgetAmount(event.target.value)} />
                <Input placeholder="Dept ID" value={budgetDepartmentId} onChange={(event) => setBudgetDepartmentId(event.target.value)} />
                <Input placeholder="From currency" value={exchangeFrom} onChange={(event) => setExchangeFrom(event.target.value.toUpperCase())} />
                <Input placeholder="Rate" value={exchangeRate} onChange={(event) => setExchangeRate(event.target.value)} />
                <Input placeholder="Convert amount" value={convertAmount} onChange={(event) => setConvertAmount(event.target.value)} />
                <Button onClick={() => planningToolMutation.mutate("analytics")} disabled={planningToolMutation.isPending}>Load Analytics</Button>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => planningToolMutation.mutate("budget")} disabled={planningToolMutation.isPending}>Create Budget</Button>
                <Button variant="outline" onClick={() => planningToolMutation.mutate("variance")} disabled={planningToolMutation.isPending}>Budget Variance</Button>
                <Button variant="outline" onClick={() => planningToolMutation.mutate("rate")} disabled={planningToolMutation.isPending}>Create Rate</Button>
                <Button variant="outline" onClick={() => planningToolMutation.mutate("convert")} disabled={planningToolMutation.isPending}>Convert</Button>
                <Button variant="outline" onClick={() => planningToolMutation.mutate("report")} disabled={planningToolMutation.isPending}>Create Report</Button>
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-md border p-3 text-sm"><p className="text-muted-foreground">Analytics records</p><p className="font-semibold">{analyticsResult?.records ?? "-"}</p><p>{analyticsResult?.total_gross_cost ? formatCurrency(analyticsResult.total_gross_cost) : ""}</p></div>
                <div className="rounded-md border p-3 text-sm"><p className="text-muted-foreground">Budget rows</p><p className="font-semibold">{budgetVarianceResult?.rows?.length ?? "-"}</p></div>
                <div className="rounded-md border p-3 text-sm"><p className="text-muted-foreground">Last conversion</p><p className="font-semibold">{(toolResults.planning_convert as { converted_amount?: number } | undefined)?.converted_amount ? formatCurrency((toolResults.planning_convert as { converted_amount: number }).converted_amount) : "-"}</p></div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {!isEmployee && activeTab === "wizard" && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Payroll Setup Wizard</CardTitle>
              <CardDescription>Complete the minimum production setup in order: legal entity, pay group, components, structure, tax, statutory profile.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 md:grid-cols-6">
                {[
                  ["Legal Entity", (legalEntities as unknown[] | undefined)?.length || 0],
                  ["Pay Group", (payGroups as unknown[] | undefined)?.length || 0],
                  ["Components", (salaryComponents as unknown[] | undefined)?.length || 0],
                  ["Structures", (salaryStructures as unknown[] | undefined)?.length || 0],
                  ["Tax Config", (taxCycles as unknown[] | undefined)?.length || 0],
                  ["Statutory Profile", (setupStatutoryProfiles as unknown[] | undefined)?.length || 0],
                ].map(([label, count], index) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => setWizardStep(index)}
                    className={`rounded-md border p-3 text-left text-sm transition-colors ${wizardStep === index ? "border-primary bg-primary/5" : "hover:bg-muted/50"}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{label}</span>
                      {Number(count) > 0 ? <CheckCircle2 className="h-4 w-4 text-green-600" /> : <AlertTriangle className="h-4 w-4 text-amber-600" />}
                    </div>
                    <p className="mt-2 text-2xl font-semibold">{count}</p>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
            {wizardStep === 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base"><Building2 className="h-4 w-4" /> Legal Entity</CardTitle>
                  <CardDescription>Required for statutory filings, Form 16, challans, and payroll grouping.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5"><Label>Legal name</Label><Input value={legalName} onChange={(event) => setLegalName(event.target.value)} /></div>
                    <div className="space-y-1.5"><Label>State</Label><Input value={legalState} onChange={(event) => setLegalState(event.target.value)} /></div>
                    <div className="space-y-1.5"><Label>PAN</Label><Input value={legalPan} onChange={(event) => setLegalPan(event.target.value.toUpperCase())} /></div>
                    <div className="space-y-1.5"><Label>TAN</Label><Input value={legalTan} onChange={(event) => setLegalTan(event.target.value.toUpperCase())} /></div>
                  </div>
                  <Button onClick={() => legalEntityMutation.mutate()} disabled={legalEntityMutation.isPending || !legalName}>
                    Create legal entity
                  </Button>
                </CardContent>
              </Card>
            )}
            {wizardStep === 1 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base"><ClipboardCheck className="h-4 w-4" /> Pay Group</CardTitle>
                  <CardDescription>Defines pay frequency, cutoffs, tax regime, and legal entity mapping.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5"><Label>Pay group name</Label><Input value={payGroupName} onChange={(event) => setPayGroupName(event.target.value)} /></div>
                    <div className="space-y-1.5"><Label>Code</Label><Input value={payGroupCode} onChange={(event) => setPayGroupCode(event.target.value.toUpperCase())} /></div>
                  </div>
                  <Button onClick={() => payGroupMutation.mutate()} disabled={payGroupMutation.isPending || !(legalEntities as LegalEntity[] | undefined)?.length}>
                    Create pay group
                  </Button>
                </CardContent>
              </Card>
            )}
            {wizardStep === 2 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base"><DollarSign className="h-4 w-4" /> Salary Components</CardTitle>
                  <CardDescription>Create earnings, deductions, reimbursements, and statutory payslip lines.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5"><Label>Name</Label><Input value={componentName} onChange={(event) => setComponentName(event.target.value)} /></div>
                    <div className="space-y-1.5"><Label>Code</Label><Input value={componentCode} onChange={(event) => setComponentCode(event.target.value.toUpperCase())} /></div>
                    <div className="space-y-1.5">
                      <Label>Type</Label>
                      <select className="h-10 rounded-md border bg-background px-3 text-sm" value={componentType} onChange={(event) => setComponentType(event.target.value)}>
                        {["Earning", "Deduction", "Statutory", "Reimbursement"].map((type) => <option key={type}>{type}</option>)}
                      </select>
                    </div>
                    <div className="space-y-1.5"><Label>Monthly amount</Label><Input value={componentAmount} onChange={(event) => setComponentAmount(event.target.value)} /></div>
                  </div>
                  <Button onClick={() => componentMutation.mutate()} disabled={componentMutation.isPending}>
                    Create component
                  </Button>
                </CardContent>
              </Card>
            )}
            {wizardStep === 3 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base"><Settings2 className="h-4 w-4" /> Salary Structure</CardTitle>
                  <CardDescription>Build a structure from active components. Formula and cap/floor rules remain in backend setup.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5"><Label>Structure name</Label><Input value={structureName} onChange={(event) => setStructureName(event.target.value)} /></div>
                    <div className="space-y-1.5"><Label>Version</Label><Input value={structureVersion} onChange={(event) => setStructureVersion(event.target.value)} /></div>
                  </div>
                  <Button onClick={() => structureMutation.mutate()} disabled={structureMutation.isPending || !(salaryComponents as SalaryComponent[] | undefined)?.length}>
                    Create structure from active components
                  </Button>
                </CardContent>
              </Card>
            )}
            {wizardStep === 4 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base"><FileText className="h-4 w-4" /> Tax Config</CardTitle>
                  <CardDescription>Open the current financial-year declaration/projection cycle.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <Button onClick={() => taxCycleMutation.mutate()} disabled={taxCycleMutation.isPending}>
                    Open current FY tax cycle
                  </Button>
                  {activeTaxCycle && <p className="rounded-md border p-3 text-sm">Active cycle: <span className="font-medium">{activeTaxCycle.name}</span></p>}
                </CardContent>
              </Card>
            )}
            {wizardStep === 5 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base"><ShieldCheck className="h-4 w-4" /> Statutory Profiles</CardTitle>
                  <CardDescription>Bind PF/ESI/PT/TDS registration details to the legal entity.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5"><Label>State / TAN circle</Label><Input value={legalState} onChange={(event) => setLegalState(event.target.value)} /></div>
                    <div className="space-y-1.5"><Label>Effective from</Label><Input type="date" value={ruleEffectiveFrom} onChange={(event) => setRuleEffectiveFrom(event.target.value)} /></div>
                  </div>
                  <Button onClick={() => setupStatutoryProfileMutation.mutate()} disabled={setupStatutoryProfileMutation.isPending || !(legalEntities as LegalEntity[] | undefined)?.length}>
                    Create statutory profile
                  </Button>
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Setup Health</CardTitle>
                <CardDescription>What payroll can use right now.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {[
                  ...(legalEntities as LegalEntity[] | undefined || []).map((item) => ({ id: `le-${item.id}`, title: item.legal_name, detail: `${item.state || "-"} | PAN ${item.pan || "-"}`, type: "Legal Entity" })),
                  ...(payGroups as { id: number; name: string; code: string; pay_frequency: string }[] | undefined || []).map((item) => ({ id: `pg-${item.id}`, title: item.name, detail: `${item.code} | ${item.pay_frequency}`, type: "Pay Group" })),
                  ...(salaryComponents as SalaryComponent[] | undefined || []).slice(0, 6).map((item) => ({ id: `sc-${item.id}`, title: item.name, detail: `${item.code} | ${formatCurrency(item.amount || 0)}`, type: item.component_type })),
                  ...(salaryStructures as SalaryStructure[] | undefined || []).map((item) => ({ id: `ss-${item.id}`, title: item.name, detail: `v${item.version} | ${item.components?.length || 0} components`, type: "Structure" })),
                ].slice(0, 12).map((item) => (
                  <div key={item.id} className="flex items-center justify-between rounded-md border p-3 text-sm">
                    <div><p className="font-medium">{item.title}</p><p className="text-muted-foreground">{item.detail}</p></div>
                    <Badge variant="outline">{item.type}</Badge>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Pay Groups and Calendar</CardTitle>
              <CardDescription>Set up monthly payroll groups before running payroll.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label>Pay group name</Label>
                  <Input value={payGroupName} onChange={(event) => setPayGroupName(event.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>Code</Label>
                  <Input value={payGroupCode} onChange={(event) => setPayGroupCode(event.target.value)} />
                </div>
              </div>
              <Button onClick={() => payGroupMutation.mutate()} disabled={payGroupMutation.isPending}>
                Create pay group
              </Button>
              <div className="space-y-2">
                {(payGroups as { id: number; name: string; code: string; pay_frequency: string }[] | undefined)?.map((item) => (
                  <div key={item.id} className="flex items-center justify-between rounded-md border p-3 text-sm">
                    <span className="font-medium">{item.name}</span>
                    <Badge variant="outline">{item.code} - {item.pay_frequency}</Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Salary Templates</CardTitle>
              <CardDescription>Create salary structure shells and assign components from backend setup.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label>Template name</Label>
                  <Input value={templateName} onChange={(event) => setTemplateName(event.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>Code</Label>
                  <Input value={templateCode} onChange={(event) => setTemplateCode(event.target.value)} />
                </div>
              </div>
              <Button onClick={() => salaryTemplateMutation.mutate()} disabled={salaryTemplateMutation.isPending}>
                Create template
              </Button>
              <div className="space-y-2">
                {(salaryTemplates as { id: number; name: string; code: string; components?: unknown[] }[] | undefined || []).map((item) => (
                  <div key={item.id} className="flex items-center justify-between rounded-md border p-3 text-sm">
                    <span className="font-medium">{item.name}</span>
                    <Badge variant="outline">{item.code} - {item.components?.length || 0} components</Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base">Periods and Accounting Setup</CardTitle>
              <CardDescription>Pay periods, bank advice, payment batches, and GL journals are now available through payroll setup flows.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-4">
              {[
                ["Periods", (payrollPeriods as unknown[] | undefined)?.length || 0],
                ["Pay Groups", (payGroups as unknown[] | undefined)?.length || 0],
                ["Templates", (salaryTemplates as unknown[] | undefined)?.length || 0],
                ["Current Year", runYear],
              ].map(([label, count]) => (
                <div key={label} className="rounded-md border p-3 text-sm">
                  <p className="text-muted-foreground">{label}</p>
                  <p className="text-2xl font-semibold">{count}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
        </div>
      )}

      {!isEmployee && activeTab === "statutory" && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <CardTitle className="text-base">Statutory Engine</CardTitle>
                  <CardDescription>PF, ESI, PT, LWF, gratuity rules, challans, and return validation.</CardDescription>
                </div>
                <Button onClick={() => seedStatutoryMutation.mutate()} disabled={seedStatutoryMutation.isPending}>
                  <ShieldCheck className="h-4 w-4 mr-2" />
                  Create rules
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 md:grid-cols-5">
                {[
                  ["PF Rules", (pfRules as unknown[] | undefined)?.length || 0],
                  ["ESI Rules", (esiRules as unknown[] | undefined)?.length || 0],
                  ["PT Slabs", (ptSlabs as unknown[] | undefined)?.length || 0],
                  ["LWF Slabs", (lwfSlabs as unknown[] | undefined)?.length || 0],
                  ["Gratuity", (gratuityRules as unknown[] | undefined)?.length || 0],
                ].map(([label, count]) => (
                  <div key={label} className="rounded-md border p-3 text-sm">
                    <p className="text-muted-foreground">{label}</p>
                    <p className="text-2xl font-semibold">{count}</p>
                  </div>
                ))}
              </div>
              <div className="grid gap-3 md:grid-cols-5">
                <div className="space-y-1.5">
                  <Label>State</Label>
                  <Input value={statutoryState} onChange={(event) => setStatutoryState(event.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>Effective from</Label>
                  <Input type="date" value={ruleEffectiveFrom} onChange={(event) => setRuleEffectiveFrom(event.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>PT amount</Label>
                  <Input value={ptAmount} onChange={(event) => setPtAmount(event.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>LWF employee</Label>
                  <Input value={lwfEmployeeAmount} onChange={(event) => setLwfEmployeeAmount(event.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>LWF employer</Label>
                  <Input value={lwfEmployerAmount} onChange={(event) => setLwfEmployerAmount(event.target.value)} />
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {["pf_ecr", "esi", "pt", "tds_24q", "form_16"].map((type) => (
                  <Button key={type} variant="outline" size="sm" onClick={() => statutoryTemplateMutation.mutate(type)}>
                    Template {type}
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Active Rules</CardTitle>
                <CardDescription>Current statutory setup used by payroll calculations.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {[
                  ...(pfRules as { id: number; name: string; wage_ceiling?: number; employee_rate?: number }[] | undefined || []).map((item) => ({
                    id: `pf-${item.id}`,
                    title: item.name,
                    detail: `PF ceiling ${formatCurrency(item.wage_ceiling || 0)} at ${item.employee_rate}%`,
                    type: "PF",
                  })),
                  ...(esiRules as { id: number; name: string; wage_threshold?: number; employee_rate?: number }[] | undefined || []).map((item) => ({
                    id: `esi-${item.id}`,
                    title: item.name,
                    detail: `ESI threshold ${formatCurrency(item.wage_threshold || 0)} at ${item.employee_rate}%`,
                    type: "ESI",
                  })),
                  ...(ptSlabs as { id: number; state: string; salary_from?: number; employee_amount?: number }[] | undefined || []).map((item) => ({
                    id: `pt-${item.id}`,
                    title: `${item.state} PT`,
                    detail: `From ${formatCurrency(item.salary_from || 0)} deduct ${formatCurrency(item.employee_amount || 0)}`,
                    type: "PT",
                  })),
                  ...(lwfSlabs as { id: number; state: string; employee_amount?: number; employer_amount?: number }[] | undefined || []).map((item) => ({
                    id: `lwf-${item.id}`,
                    title: `${item.state} LWF`,
                    detail: `Employee ${formatCurrency(item.employee_amount || 0)}, employer ${formatCurrency(item.employer_amount || 0)}`,
                    type: "LWF",
                  })),
                  ...(gratuityRules as { id: number; name: string; days_per_year?: number; min_service_years?: number }[] | undefined || []).map((item) => ({
                    id: `gratuity-${item.id}`,
                    title: item.name,
                    detail: `${item.days_per_year} days after ${item.min_service_years} years`,
                    type: "Gratuity",
                  })),
                ].slice(0, 12).map((item) => (
                  <div key={item.id} className="flex items-center justify-between rounded-md border p-3 text-sm">
                    <div>
                      <p className="font-medium">{item.title}</p>
                      <p className="text-muted-foreground">{item.detail}</p>
                    </div>
                    <Badge variant="outline">{item.type}</Badge>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Challans</CardTitle>
                <CardDescription>Generated statutory payment records and validation status.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {(challans as { id: number; challan_type: string; amount: number; due_date: string; status: string }[] | undefined)?.length ? (
                  (challans as { id: number; challan_type: string; amount: number; due_date: string; status: string }[]).map((item) => (
                    <div key={item.id} className="flex items-center justify-between rounded-md border p-3 text-sm">
                      <div>
                        <p className="font-medium">{item.challan_type} - {formatCurrency(item.amount)}</p>
                        <p className="text-muted-foreground">Due {formatDate(item.due_date)}</p>
                      </div>
                      <Badge variant="outline">{item.status}</Badge>
                    </div>
                  ))
                ) : (
                  <div className="rounded-md border p-6 text-center text-sm text-muted-foreground">
                    No challans generated yet
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {!isEmployee && activeTab === "tax" && (
        <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Tax Declarations</CardTitle>
              <CardDescription>Declare investments and submit proof links for payroll verification.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {!activeTaxCycle ? (
                <Button onClick={() => taxCycleMutation.mutate()} disabled={taxCycleMutation.isPending}>
                  Open current FY cycle
                </Button>
              ) : (
                <>
                  <div className="rounded-md border p-3 text-sm">
                    <p className="font-medium">{activeTaxCycle.name}</p>
                    <p className="text-muted-foreground">Proof due {formatDate(activeTaxCycle.proof_due_date)}</p>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label>Section</Label>
                      <Input value={taxSection} onChange={(event) => setTaxSection(event.target.value)} />
                    </div>
                    <div className="space-y-1.5">
                      <Label>Amount</Label>
                      <Input value={taxAmount} onChange={(event) => setTaxAmount(event.target.value)} />
                    </div>
                  </div>
                  <Button onClick={() => taxDeclarationMutation.mutate()} disabled={taxDeclarationMutation.isPending}>
                    Submit declaration
                  </Button>
                </>
              )}

              {taxProjection && (
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="rounded-md border p-3">
                    <p className="text-muted-foreground">Declared</p>
                    <p className="font-semibold">{formatCurrency(taxProjection.declared_amount)}</p>
                  </div>
                  <div className="rounded-md border p-3">
                    <p className="text-muted-foreground">Projected TDS</p>
                    <p className="font-semibold">{formatCurrency(taxProjection.projected_tds)}</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Proof Workflow</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input
                value={taxProofUrl}
                onChange={(event) => setTaxProofUrl(event.target.value)}
                placeholder="/uploads/tax/80c-proof.pdf"
              />
              {(taxDeclarations as { id: number; section: string; declared_amount: number; status: string; proofs?: unknown[] }[] | undefined)?.map((item) => (
                <div key={item.id} className="flex flex-col gap-3 rounded-md border p-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="font-medium">{item.section} - {formatCurrency(item.declared_amount)}</p>
                    <p className="text-sm text-muted-foreground">{item.status} - {item.proofs?.length || 0} proof(s)</p>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => taxProofMutation.mutate(item.id)}>
                    Submit proof
                  </Button>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}

      {!isEmployee && activeTab === "casebook" && (
        <div className="grid gap-4 lg:grid-cols-2">
          {[
            {
              title: "New Joiner Proration",
              detail: "Employee joins mid-month. Payroll should calculate paid days from joining date, include fixed earnings, and exclude LOP outside employment.",
              checks: ["Joining date within month", "Paid days prorated", "PF/ESI on eligible wages"],
            },
            {
              title: "Loss of Pay and Leave",
              detail: "Approved paid leave should not reduce salary; unpaid or excess leave should create LOP deduction before approval.",
              checks: ["Leave balance consumed", "LOP days visible", "Gross to net reconciliation"],
            },
            {
              title: "Bonus and Reimbursement",
              detail: "One-time bonus should be taxable earning; approved reimbursements should be paid separately or marked non-taxable based on policy.",
              checks: ["Bonus as earning", "Receipt-backed reimbursements", "Approval before payroll lock"],
            },
            {
              title: "Payroll Anomaly",
              detail: "AI anomaly detection should flag unusually high net pay, negative net pay, duplicate components, and large month-on-month variance.",
              checks: ["Variance threshold", "Negative net block", "Audit trail retained"],
            },
          ].map((item) => (
            <Card key={item.title}>
              <CardHeader>
                <CardTitle className="text-base">{item.title}</CardTitle>
                <CardDescription>{item.detail}</CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm">
                  {item.checks.map((check) => (
                    <li key={check} className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-green-600" />
                      {check}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function readableApiError(error: unknown) {
  const detail = (error as { response?: { data?: { detail?: unknown } }; message?: string })?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) return String((item as { msg?: unknown }).msg);
        return "";
      })
      .filter(Boolean)
      .join("; ");
  }
  if (detail && typeof detail === "object") {
    const message = (detail as { message?: unknown; msg?: unknown }).message || (detail as { message?: unknown; msg?: unknown }).msg;
    if (message) return String(message);
  }
  return (error as { message?: string })?.message || "Please check the selected payroll data and try again.";
}

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Plus, CheckCircle2, XCircle, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import AskAiButton from "@/components/ai-agents/AskAiButton";
import { authApi, employeeApi, leaveApi, leavePayrollApi } from "@/services/api";
import { formatDate, statusColor } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";
import { useAuthStore } from "@/store/authStore";
import { usePageTitle } from "@/hooks/use-page-title";
import { getRoleKey } from "@/lib/roles";
import { NOTIF_UNREAD_KEY } from "@/components/layout/Topbar";

interface LeaveType {
  id: number;
  name: string;
  color?: string;
}

interface LeaveBalance {
  leave_type_id: number;
  leave_type: LeaveType;
  allocated: number;
  used: number;
  pending: number;
  available: number;
}

interface LeaveRequest {
  id: number;
  employee_id: number;
  employee?: {
    employee_id: string;
    first_name: string;
    last_name: string;
    personal_email?: string | null;
  };
  leave_type: LeaveType;
  from_date: string;
  to_date: string;
  days_count: number;
  reason?: string;
  status: string;
  applied_at: string;
  review_remarks?: string | null;
}

interface LeaveCalendarDay {
  date: string;
  leave_count: number;
  pending_count: number;
  approved_count: number;
  employees_on_leave: LeaveRequest[];
  holidays: Array<{ id: number; name: string; holiday_date: string; holiday_type: string }>;
}

interface ApplyForm {
  leave_type_id: number;
  from_date: string;
  to_date: string;
  reason: string;
  leave_mode?: string;
}

interface LeaveEncashmentRequest {
  id: number;
  employeeName?: string;
  employeeCode?: string;
  leaveTypeName?: string;
  daysToEncash: number;
  encashmentRate: number;
  amount: number;
  status: string;
  requestedAt?: string;
  remarks?: string | null;
}

interface EmployeeOption {
  id: number;
  employee_id?: string;
  first_name?: string;
  last_name?: string;
  work_email?: string | null;
  personal_email?: string | null;
  user_id?: number | null;
}

interface UserOption {
  id: number;
  email: string;
  role?: string | null;
  employee_id?: number | null;
  employee_code?: string | null;
}

export default function LeavePage() {
  usePageTitle("Leave");
  const qc = useQueryClient();
  const { user } = useAuthStore();
  const roleKey = getRoleKey(user?.role, user?.is_superuser);
  const canApproveLeave = ["admin", "hr", "manager"].includes(roleKey);
  const hasEmployeeProfile = Boolean(user?.employee_id);
  const [showApplyForm, setShowApplyForm] = useState(false);
  const [activeTab, setActiveTab] = useState<"my" | "approvals" | "calendar">("my");
  const [calendarMonth, setCalendarMonth] = useState(() => new Date());
  const [calendarScope, setCalendarScope] = useState<"mine" | "team" | "all">(canApproveLeave ? "team" : "mine");
  const [reviewRemarks, setReviewRemarks] = useState<Record<number, string>>({});
  const [encashLeaveTypeId, setEncashLeaveTypeId] = useState("");
  const [encashDays, setEncashDays] = useState("");
  const [encashRemarks, setEncashRemarks] = useState("");
  const [encashReviewRemarks, setEncashReviewRemarks] = useState<Record<number, string>>({});
  const [accountEmployeeSearch, setAccountEmployeeSearch] = useState("Recovery");
  const [accountUserSearch, setAccountUserSearch] = useState("");
  const [accountEmployeeId, setAccountEmployeeId] = useState("");
  const [accountUserId, setAccountUserId] = useState("");
  const [accountEmail, setAccountEmail] = useState("");
  const [accountPassword, setAccountPassword] = useState("Employee@123456");

  const { data: balances, isLoading: loadingBalance } = useQuery({
    queryKey: ["leave-balance"],
    queryFn: () => leaveApi.balance().then((r) => r.data as LeaveBalance[]),
    enabled: hasEmployeeProfile,
  });

  const { data: myRequests, isLoading: loadingRequests, refetch } = useQuery({
    queryKey: ["my-leave-requests"],
    queryFn: () => leaveApi.myRequests().then((r) => r.data as LeaveRequest[]),
    enabled: hasEmployeeProfile,
  });

  const { data: allRequests, refetch: refetchAll } = useQuery({
    queryKey: ["all-leave-requests", "Pending"],
    queryFn: () => leaveApi.allRequests({ status: "Pending" }).then((r) => r.data as LeaveRequest[]),
    enabled: canApproveLeave,
    retry: false,
  });

  const { data: leaveTypes } = useQuery({
    queryKey: ["leave-types"],
    queryFn: () => leaveApi.types().then((r) => r.data as LeaveType[]),
  });

  const { data: employeeOptions } = useQuery({
    queryKey: ["leave-account-employees", accountEmployeeSearch],
    queryFn: () => employeeApi.list({ search: accountEmployeeSearch || undefined, limit: 50 }).then((r) => r.data),
    enabled: canApproveLeave,
  });

  const { data: userOptions } = useQuery({
    queryKey: ["leave-account-user-options", accountUserSearch, accountEmployeeId],
    queryFn: () => employeeApi.userOptions({ search: accountUserSearch || undefined, include_employee_id: accountEmployeeId || undefined }).then((r) => r.data as UserOption[]),
    enabled: canApproveLeave,
  });

  const { data: roles } = useQuery({
    queryKey: ["leave-account-roles"],
    queryFn: () => authApi.roles().then((r) => r.data as Array<{ id: number; name: string }>),
    enabled: canApproveLeave,
  });

  const { data: encashmentRequests } = useQuery({
    queryKey: ["leave-encashment-requests"],
    queryFn: () => leavePayrollApi.encashmentRequests().then((r) => r.data as LeaveEncashmentRequest[]),
  });

  const { data: pendingEncashmentRequests } = useQuery({
    queryKey: ["leave-encashment-requests", "submitted"],
    queryFn: () => leavePayrollApi.encashmentRequests({ status: "submitted" }).then((r) => r.data as LeaveEncashmentRequest[]),
    enabled: canApproveLeave,
    retry: false,
  });

  const calendarStart = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth(), 1);
  const calendarEnd = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 0);
  const toDateText = (value: Date) => {
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${value.getFullYear()}-${month}-${day}`;
  };
  const calendarStartText = toDateText(calendarStart);
  const calendarEndText = toDateText(calendarEnd);

  const { data: calendarData, isLoading: loadingCalendar } = useQuery({
    queryKey: ["leave-calendar", calendarStartText, calendarEndText, calendarScope],
    queryFn: () =>
      leaveApi.calendar({
        from_date: calendarStartText,
        to_date: calendarEndText,
        scope: calendarScope,
      }).then((r) => r.data as { days: LeaveCalendarDay[]; total_leave_days: number; scope: string }),
  });

  const { register, handleSubmit, reset, formState: { errors } } = useForm<ApplyForm>();

  const applyMutation = useMutation({
    mutationFn: (data: ApplyForm) =>
      leaveApi.apply({ ...data, leave_type_id: Number(data.leave_type_id) }),
    onSuccess: () => {
      toast({ title: "Leave application submitted" });
      reset();
      setShowApplyForm(false);
      qc.invalidateQueries({ queryKey: ["leave-balance"] });
      qc.invalidateQueries({ queryKey: ["my-leave-requests"] });
      qc.invalidateQueries({ queryKey: ["all-leave-requests"] });
      qc.invalidateQueries({ queryKey: NOTIF_UNREAD_KEY });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to apply";
      toast({ title: "Error", description: msg, variant: "destructive" });
    },
  });

  const approveMutation = useMutation({
    mutationFn: ({ id, status, remarks }: { id: number; status: string; remarks: string }) =>
      leaveApi.approve(id, { status, review_remarks: remarks }),
    onSuccess: (_, { status }) => {
      toast({ title: `Leave ${status.toLowerCase()}` });
      setReviewRemarks({});
      qc.invalidateQueries({ queryKey: ["leave-balance"] });
      qc.invalidateQueries({ queryKey: ["my-leave-requests"] });
      qc.invalidateQueries({ queryKey: ["all-leave-requests"] });
      qc.invalidateQueries({ queryKey: NOTIF_UNREAD_KEY });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Action failed";
      toast({ title: "Action failed", description: msg, variant: "destructive" });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (id: number) => leaveApi.cancel(id),
    onSuccess: () => {
      toast({ title: "Leave cancelled" });
      refetch();
      qc.invalidateQueries({ queryKey: ["leave-balance"] });
      qc.invalidateQueries({ queryKey: ["all-leave-requests"] });
    },
  });

  const requestEncashmentMutation = useMutation({
    mutationFn: () =>
      leavePayrollApi.requestEncashment({
        leaveTypeId: Number(encashLeaveTypeId),
        daysToEncash: Number(encashDays),
        remarks: encashRemarks || undefined,
      }),
    onSuccess: () => {
      toast({ title: "Leave encashment requested" });
      setEncashLeaveTypeId("");
      setEncashDays("");
      setEncashRemarks("");
      qc.invalidateQueries({ queryKey: ["leave-encashment-requests"] });
      qc.invalidateQueries({ queryKey: ["leave-balance"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to request leave encashment";
      toast({ title: "Request failed", description: msg, variant: "destructive" });
    },
  });

  const reviewEncashmentMutation = useMutation({
    mutationFn: ({ id, action }: { id: number; action: "approve" | "reject" }) => {
      const payload = { remarks: encashReviewRemarks[id] || undefined };
      return action === "approve" ? leavePayrollApi.approveEncashment(id, payload) : leavePayrollApi.rejectEncashment(id, payload);
    },
    onSuccess: () => {
      toast({ title: "Encashment request updated" });
      setEncashReviewRemarks({});
      qc.invalidateQueries({ queryKey: ["leave-encashment-requests"] });
      qc.invalidateQueries({ queryKey: ["leave-balance"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to update encashment request";
      toast({ title: "Action failed", description: msg, variant: "destructive" });
    },
  });

  const runAccrualsMutation = useMutation({
    mutationFn: () => leaveApi.runAccruals(toDateText(new Date())),
    onSuccess: (response) => {
      const count = (response.data as { processed?: number })?.processed ?? 0;
      toast({ title: "Leave accruals processed", description: `${count} balance row${count === 1 ? "" : "s"} updated.` });
      qc.invalidateQueries({ queryKey: ["leave-balance"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to run leave accruals";
      toast({ title: "Accrual run failed", description: msg, variant: "destructive" });
    },
  });

  const runCarryForwardMutation = useMutation({
    mutationFn: () => {
      const year = new Date().getFullYear();
      return leaveApi.runCarryForward(year - 1, year);
    },
    onSuccess: (response) => {
      const count = (response.data as { processed?: number })?.processed ?? 0;
      toast({ title: "Leave carry-forward processed", description: `${count} balance row${count === 1 ? "" : "s"} updated.` });
      qc.invalidateQueries({ queryKey: ["leave-balance"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to run carry-forward";
      toast({ title: "Carry-forward failed", description: msg, variant: "destructive" });
    },
  });

  const linkEmployeeUserMutation = useMutation({
    mutationFn: () => employeeApi.linkUser(Number(accountEmployeeId), accountUserId ? Number(accountUserId) : null),
    onSuccess: () => {
      toast({ title: "Employee account linked" });
      qc.invalidateQueries({ queryKey: ["leave-account-employees"] });
      qc.invalidateQueries({ queryKey: ["leave-account-user-options"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Could not link employee account";
      toast({ title: "Account link failed", description: msg, variant: "destructive" });
    },
  });

  const createAndLinkUserMutation = useMutation({
    mutationFn: async () => {
      const employeeRole = (roles || []).find((item) => item.name?.toLowerCase().includes("employee"));
      const linkedEmployee = await employeeApi.createUserAccount(Number(accountEmployeeId), {
        email: accountEmail,
        password: accountPassword,
        role_id: employeeRole?.id,
      });
      return linkedEmployee.data;
    },
    onSuccess: () => {
      toast({ title: "Employee login created", description: `${accountEmail} can now apply leave and view payslips.` });
      setAccountUserId("");
      qc.invalidateQueries({ queryKey: ["leave-account-employees"] });
      qc.invalidateQueries({ queryKey: ["leave-account-user-options"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Could not create employee login";
      toast({ title: "Account creation failed", description: msg, variant: "destructive" });
    },
  });

  const tabs: Array<"my" | "approvals" | "calendar"> = canApproveLeave ? ["my", "approvals", "calendar"] : ["my", "calendar"];
  const pendingApprovals = allRequests || [];
  const pendingEncashments = pendingEncashmentRequests || [];
  const calendarDays = calendarData?.days || [];
  const monthLabel = calendarMonth.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  const employees = Array.isArray(employeeOptions?.items) ? employeeOptions.items as EmployeeOption[] : Array.isArray(employeeOptions) ? employeeOptions as EmployeeOption[] : [];
  const selectedAccountEmployee = employees.find((employee) => String(employee.id) === accountEmployeeId);
  const applyLeaveTypes = balances?.length
    ? balances
        .filter((balance) => Number(balance.available) > 0 || Number(balance.allocated) > 0)
        .map((balance) => balance.leave_type)
        .filter((type): type is LeaveType => Boolean(type?.id))
    : leaveTypes || [];

  function submitDecision(id: number, status: "Approved" | "Rejected") {
    const fallback = status === "Approved" ? "Approved by HR" : "Rejected by HR";
    approveMutation.mutate({ id, status, remarks: reviewRemarks[id]?.trim() || fallback });
  }

  function moveMonth(offset: number) {
    setCalendarMonth((current) => new Date(current.getFullYear(), current.getMonth() + offset, 1));
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="page-title">Leave Management</h1>
          <p className="page-description">Employees apply for leave, HR or managers approve or reject with a reason.</p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          {canApproveLeave ? (
            <AskAiButton module="HRMS" defaultAgentCode="hrms_leave_assistant" defaultPrompt="Check leave balance and help with leave request/review." />
          ) : null}
          {canApproveLeave ? (
            <>
              <Button size="sm" variant="outline" className="w-full sm:w-auto" onClick={() => runAccrualsMutation.mutate()} disabled={runAccrualsMutation.isPending}>
                <RefreshCw className="mr-2 h-4 w-4" />
                {runAccrualsMutation.isPending ? "Running..." : "Run Accruals"}
              </Button>
              <Button size="sm" variant="outline" className="w-full sm:w-auto" onClick={() => runCarryForwardMutation.mutate()} disabled={runCarryForwardMutation.isPending}>
                <RefreshCw className="mr-2 h-4 w-4" />
                {runCarryForwardMutation.isPending ? "Running..." : "Carry Forward"}
              </Button>
            </>
          ) : null}
          <Button size="sm" className="w-full sm:w-auto" onClick={() => setShowApplyForm((v) => !v)}>
            <Plus className="mr-2 h-4 w-4" />
            Apply Leave
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-4">
        {loadingBalance
          ? Array.from({ length: 4 }).map((_, i) => (
              <Card key={i}><CardContent className="p-4"><div className="h-12 skeleton rounded" /></CardContent></Card>
            ))
          : !hasEmployeeProfile ? (
              <Card className="sm:col-span-3 lg:col-span-4">
                <CardContent className="p-4 text-sm text-muted-foreground">
                  Link an employee profile to this login to show self-service leave balances.
                </CardContent>
              </Card>
            )
          : balances?.map((b) => {
              const allocated = Number(b.allocated) || 0;
              const available = Number(b.available) || 0;
              const width = allocated > 0 ? Math.min(100, (available / allocated) * 100) : 0;
              return (
                <Card key={b.leave_type_id}>
                  <CardContent className="p-4">
                    <p className="truncate text-xs text-muted-foreground">{b.leave_type?.name}</p>
                    <p className="mt-1 text-2xl font-bold">{available.toFixed(1)}</p>
                    <p className="text-xs text-muted-foreground">of {allocated.toFixed(1)} available</p>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full bg-primary" style={{ width: `${width}%` }} />
                    </div>
                  </CardContent>
                </Card>
              );
            })}
      </div>

      {showApplyForm && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Apply for Leave</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit((data) => applyMutation.mutate(data))} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>Leave Type *</Label>
                <select
                  {...register("leave_type_id", { required: "Required" })}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="">Select leave type</option>
                  {applyLeaveTypes.map((t) => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
                {errors.leave_type_id && <p className="text-xs text-red-500">{errors.leave_type_id.message}</p>}
              </div>

              <div className="space-y-1.5">
                <Label>Mode</Label>
                <select
                  {...register("leave_mode")}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="Full-day">Full Day</option>
                  <option value="Half-day">Half Day</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <Label>From Date *</Label>
                <Input type="date" {...register("from_date", { required: "Required" })} />
                {errors.from_date && <p className="text-xs text-red-500">{errors.from_date.message}</p>}
              </div>

              <div className="space-y-1.5">
                <Label>To Date *</Label>
                <Input type="date" {...register("to_date", { required: "Required" })} />
                {errors.to_date && <p className="text-xs text-red-500">{errors.to_date.message}</p>}
              </div>

              <div className="space-y-1.5 sm:col-span-2">
                <Label>Reason *</Label>
                <textarea
                  {...register("reason", { required: "Required" })}
                  rows={3}
                  className="flex w-full resize-none rounded-md border border-input bg-background px-3 py-2 text-sm"
                  placeholder="Reason for leave..."
                />
                {errors.reason && <p className="text-xs text-red-500">{errors.reason.message}</p>}
              </div>

              <div className="flex gap-3 sm:col-span-2">
                <Button type="submit" disabled={applyMutation.isPending}>
                  {applyMutation.isPending ? "Submitting..." : "Submit Application"}
                </Button>
                <Button type="button" variant="outline" onClick={() => setShowApplyForm(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {canApproveLeave && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Employee Account Wizard</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto]">
              <Input value={accountEmployeeSearch} onChange={(event) => setAccountEmployeeSearch(event.target.value)} placeholder="Search employee code or name" />
              <select value={accountEmployeeId} onChange={(event) => {
                const employeeId = event.target.value;
                setAccountEmployeeId(employeeId);
                const employee = employees.find((item) => String(item.id) === employeeId);
                setAccountEmail(employee?.work_email || employee?.personal_email || "");
              }} className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm">
                <option value="">Select employee</option>
                {employees.map((employee) => (
                  <option key={employee.id} value={employee.id}>
                    {employee.employee_id} - {employee.first_name} {employee.last_name} {employee.user_id ? "(linked)" : ""}
                  </option>
                ))}
              </select>
              <Button variant="outline" onClick={() => qc.invalidateQueries({ queryKey: ["leave-account-employees"] })}>
                Refresh Employees
              </Button>
            </div>

            <div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto]">
              <Input value={accountUserSearch} onChange={(event) => setAccountUserSearch(event.target.value)} placeholder="Search existing user email" />
              <select value={accountUserId} onChange={(event) => setAccountUserId(event.target.value)} className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm">
                <option value="">Select unlinked user</option>
                {(userOptions || []).map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.email} {user.employee_code ? `(${user.employee_code})` : ""}
                  </option>
                ))}
              </select>
              <Button disabled={!accountEmployeeId || !accountUserId || linkEmployeeUserMutation.isPending} onClick={() => linkEmployeeUserMutation.mutate()}>
                Link Existing User
              </Button>
            </div>

            <div className="grid gap-3 lg:grid-cols-[1fr_180px_auto]">
              <Input value={accountEmail} onChange={(event) => setAccountEmail(event.target.value)} placeholder="employee@email.com" />
              <Input value={accountPassword} onChange={(event) => setAccountPassword(event.target.value)} placeholder="Temporary password" type="password" />
              <Button disabled={!accountEmployeeId || !accountEmail || !accountPassword || createAndLinkUserMutation.isPending} onClick={() => createAndLinkUserMutation.mutate()}>
                Create Login
              </Button>
            </div>

            <div className="rounded-md border bg-muted/30 p-3 text-sm">
              <p className="font-medium">Verification path</p>
              <p className="mt-1 text-muted-foreground">
                {selectedAccountEmployee
                  ? `${selectedAccountEmployee.employee_id} will be able to login, apply leave, appear in manager/HR approvals, update leave balance after approval, and feed payroll LOP.`
                  : "Select an employee to link or create their login account."}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Leave Encashment</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_120px_1.4fr_auto]">
            <select
              value={encashLeaveTypeId}
              onChange={(event) => setEncashLeaveTypeId(event.target.value)}
              className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">Select encashable leave</option>
              {leaveTypes?.map((type) => (
                <option key={type.id} value={type.id}>{type.name}</option>
              ))}
            </select>
            <Input value={encashDays} onChange={(event) => setEncashDays(event.target.value)} placeholder="Days" type="number" min="0" step="0.5" />
            <Input value={encashRemarks} onChange={(event) => setEncashRemarks(event.target.value)} placeholder="Remarks" />
            <Button
              onClick={() => requestEncashmentMutation.mutate()}
              disabled={!encashLeaveTypeId || !encashDays || requestEncashmentMutation.isPending}
            >
              Request
            </Button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-sm">
              <thead className="border-b bg-muted/50">
                <tr>
                  {["Leave type", "Days", "Rate", "Amount", "Status", "Requested", "Remarks"].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {!encashmentRequests?.length ? (
                  <tr><td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">No leave encashment requests yet</td></tr>
                ) : (
                  encashmentRequests.slice(0, 5).map((item) => (
                    <tr key={item.id} className="border-b">
                      <td className="px-4 py-3 font-medium">{item.leaveTypeName || "-"}</td>
                      <td className="px-4 py-3">{Number(item.daysToEncash).toFixed(2)}</td>
                      <td className="px-4 py-3">₹{Number(item.encashmentRate || 0).toLocaleString("en-IN")}</td>
                      <td className="px-4 py-3 font-semibold">₹{Number(item.amount || 0).toLocaleString("en-IN")}</td>
                      <td className="px-4 py-3"><span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(item.status)}`}>{item.status}</span></td>
                      <td className="px-4 py-3 text-muted-foreground">{item.requestedAt ? formatDate(item.requestedAt) : "-"}</td>
                      <td className="max-w-[220px] truncate px-4 py-3 text-muted-foreground">{item.remarks || "-"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="flex gap-2 overflow-x-auto border-b">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`border-b-2 px-1 pb-2 text-sm font-medium transition-colors ${
              activeTab === tab ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab === "my" ? "My Requests" : tab === "approvals" ? "Pending Approvals" : "Calendar"}
            {tab === "approvals" && pendingApprovals.length > 0 && (
              <span className="ml-2 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-xs text-primary-foreground">
                {pendingApprovals.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {activeTab === "my" && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">My Leave Requests</CardTitle>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="border-b p-4">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">Pending Leave Encashment</p>
                  <p className="text-xs text-muted-foreground">Approved requests become payroll earnings in the next open pay period.</p>
                </div>
                <span className="rounded-full bg-muted px-2 py-1 text-xs">{pendingEncashments.length}</span>
              </div>
              {pendingEncashments.length === 0 ? (
                <p className="rounded-md border border-dashed px-3 py-4 text-center text-sm text-muted-foreground">No pending encashment approvals</p>
              ) : (
                <div className="space-y-2">
                  {pendingEncashments.map((item) => (
                    <div key={item.id} className="grid gap-2 rounded-md border p-3 lg:grid-cols-[1fr_120px_140px_1fr_auto] lg:items-center">
                      <div>
                        <p className="text-sm font-medium">{item.employeeName || item.employeeCode || "Employee"}</p>
                        <p className="text-xs text-muted-foreground">{item.leaveTypeName} - {Number(item.daysToEncash).toFixed(2)} day(s)</p>
                      </div>
                      <p className="text-sm font-semibold">₹{Number(item.amount || 0).toLocaleString("en-IN")}</p>
                      <p className="text-xs text-muted-foreground">Rate ₹{Number(item.encashmentRate || 0).toLocaleString("en-IN")}</p>
                      <Input
                        value={encashReviewRemarks[item.id] || ""}
                        onChange={(event) => setEncashReviewRemarks((current) => ({ ...current, [item.id]: event.target.value }))}
                        placeholder="Approval remarks"
                      />
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => reviewEncashmentMutation.mutate({ id: item.id, action: "approve" })} disabled={reviewEncashmentMutation.isPending}>Approve</Button>
                        <Button size="sm" variant="outline" onClick={() => reviewEncashmentMutation.mutate({ id: item.id, action: "reject" })} disabled={reviewEncashmentMutation.isPending}>Reject</Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-sm">
                <thead className="border-b bg-muted/50">
                  <tr>
                    {["Type", "From", "To", "Days", "Reason", "Reviewed reason", "Applied On", "Status", ""].map((h) => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loadingRequests ? (
                    Array.from({ length: 5 }).map((_, i) => (
                      <tr key={i} className="border-b">
                        <td colSpan={9} className="px-4 py-3"><div className="h-4 skeleton rounded" /></td>
                      </tr>
                    ))
                  ) : !myRequests || myRequests.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="px-4 py-10 text-center text-muted-foreground">
                        <CalendarDays className="mx-auto mb-2 h-8 w-8 opacity-30" />
                        No leave requests yet
                      </td>
                    </tr>
                  ) : (
                    myRequests.map((r) => (
                      <tr key={r.id} className="border-b hover:bg-muted/30">
                        <td className="px-4 py-3 font-medium">{r.leave_type?.name}</td>
                        <td className="px-4 py-3">{formatDate(r.from_date)}</td>
                        <td className="px-4 py-3">{formatDate(r.to_date)}</td>
                        <td className="px-4 py-3 text-center">{Number(r.days_count).toFixed(1)}</td>
                        <td className="max-w-[160px] truncate px-4 py-3 text-muted-foreground">{r.reason || "-"}</td>
                        <td className="max-w-[180px] truncate px-4 py-3 text-muted-foreground">{r.review_remarks || "-"}</td>
                        <td className="px-4 py-3 text-muted-foreground">{formatDate(r.applied_at)}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(r.status)}`}>
                            {r.status}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {r.status === "Pending" && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 text-xs text-red-500 hover:text-red-700"
                              onClick={() => cancelMutation.mutate(r.id)}
                            >
                              Cancel
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
      )}

      {activeTab === "calendar" && (
        <Card>
          <CardHeader>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <CardTitle className="text-base">Leave Calendar</CardTitle>
                <p className="mt-1 text-sm text-muted-foreground">
                  {calendarData?.total_leave_days || 0} scheduled leave days in {monthLabel}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="outline" size="icon" className="h-9 w-9" onClick={() => moveMonth(-1)}>
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <div className="min-w-[150px] text-center text-sm font-medium">{monthLabel}</div>
                <Button variant="outline" size="icon" className="h-9 w-9" onClick={() => moveMonth(1)}>
                  <ChevronRight className="h-4 w-4" />
                </Button>
                <select
                  value={calendarScope}
                  onChange={(event) => setCalendarScope(event.target.value as "mine" | "team" | "all")}
                  className="flex h-9 rounded-md border border-input bg-background px-3 py-1 text-sm"
                >
                  <option value="mine">My leave</option>
                  {canApproveLeave && <option value="team">Team leave</option>}
                  {["admin", "hr"].includes(roleKey) && <option value="all">All employees</option>}
                </select>
                <Button variant="ghost" size="icon" className="h-9 w-9" onClick={() => qc.invalidateQueries({ queryKey: ["leave-calendar"] })}>
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {loadingCalendar ? (
              <div className="h-64 rounded-lg border bg-muted/30" />
            ) : (
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-7">
                {calendarDays.map((day) => {
                  const date = new Date(`${day.date}T00:00:00`);
                  const isWeekend = [0, 6].includes(date.getDay());
                  return (
                    <div
                      key={day.date}
                      className={`min-h-[150px] rounded-lg border p-3 ${isWeekend ? "bg-muted/30" : "bg-card"}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div>
                          <p className="text-sm font-semibold">{date.getDate()}</p>
                          <p className="text-xs text-muted-foreground">
                            {date.toLocaleDateString(undefined, { weekday: "short" })}
                          </p>
                        </div>
                        {day.leave_count > 0 && (
                          <span className="rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground">
                            {day.leave_count}
                          </span>
                        )}
                      </div>

                      <div className="mt-3 space-y-2">
                        {day.holidays.map((holiday) => (
                          <div key={holiday.id} className="rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-900">
                            {holiday.name}
                          </div>
                        ))}
                        {day.employees_on_leave.slice(0, 3).map((request) => (
                          <div key={request.id} className="rounded-md border px-2 py-1 text-xs">
                            <div className="truncate font-medium">
                              {request.employee
                                ? `${request.employee.first_name} ${request.employee.last_name}`
                                : `Employee #${request.employee_id}`}
                            </div>
                            <div className="mt-0.5 flex items-center justify-between gap-2 text-muted-foreground">
                              <span className="truncate">{request.leave_type?.name || "Leave"}</span>
                              <span className={request.status === "Approved" ? "text-green-700" : "text-amber-700"}>
                                {request.status}
                              </span>
                            </div>
                          </div>
                        ))}
                        {day.employees_on_leave.length > 3 && (
                          <p className="text-xs text-muted-foreground">+{day.employees_on_leave.length - 3} more</p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === "approvals" && canApproveLeave && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Pending Approvals</CardTitle>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => refetchAll()}>
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-sm">
                <thead className="border-b bg-muted/50">
                  <tr>
                    {["Employee", "Type", "From", "To", "Days", "Reason", "Review reason", "Actions"].map((h) => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {pendingApprovals.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-10 text-center text-muted-foreground">
                        <CheckCircle2 className="mx-auto mb-2 h-8 w-8 opacity-30" />
                        No pending approvals
                      </td>
                    </tr>
                  ) : (
                    pendingApprovals.map((r) => (
                      <tr key={r.id} className="border-b hover:bg-muted/30">
                        <td className="px-4 py-3 font-medium">
                          {r.employee ? (
                            <span>
                              <span className="block">{r.employee.first_name} {r.employee.last_name}</span>
                              <span className="block text-xs font-normal text-muted-foreground">{r.employee.employee_id}</span>
                            </span>
                          ) : (
                            <span className="text-muted-foreground">Employee #{r.employee_id}</span>
                          )}
                        </td>
                        <td className="px-4 py-3">{r.leave_type?.name}</td>
                        <td className="px-4 py-3">{formatDate(r.from_date)}</td>
                        <td className="px-4 py-3">{formatDate(r.to_date)}</td>
                        <td className="px-4 py-3 text-center">{Number(r.days_count).toFixed(1)}</td>
                        <td className="max-w-[160px] truncate px-4 py-3 text-muted-foreground">{r.reason || "-"}</td>
                        <td className="min-w-[220px] px-4 py-3">
                          <textarea
                            value={reviewRemarks[r.id] || ""}
                            onChange={(event) =>
                              setReviewRemarks((current) => ({ ...current, [r.id]: event.target.value }))
                            }
                            rows={2}
                            className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-xs"
                            placeholder="Approval or rejection reason"
                          />
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex flex-col gap-2 xl:flex-row">
                            <Button
                              size="sm"
                              className="h-7 bg-green-600 text-xs text-white hover:bg-green-700"
                              onClick={() => submitDecision(r.id, "Approved")}
                              disabled={approveMutation.isPending}
                            >
                              <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 border-red-300 text-xs text-red-500 hover:bg-red-50"
                              onClick={() => submitDecision(r.id, "Rejected")}
                              disabled={approveMutation.isPending}
                            >
                              <XCircle className="mr-1 h-3.5 w-3.5" />
                              Reject
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

import { MobileDisclosure } from "@/components/mobile/MobilePrimitives";
import { useRecordDraft } from "@/hooks/use-record-autosave";
import { announceCreated } from "@/shared/creation/CreationOutcome";
import RequestReviewContext from "../../components/RequestReviewContext";
import "./leave-mobile.css";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import {useDefinitionPermission} from "@/components/RecordDefinitionActions";
import { SmartCreateModal } from "@/shared/creation/SmartCreateModal";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import { standardRecordGroups } from "@/shared/data-grid/record-group-fields";
import { defaultId } from "@/lib/form-defaults";
import GridTable from "@/shared/data-grid/GridTable";
import { NativeSelect } from "@/components/ui/native-select";
import { useMobile } from "@/components/mobile/useMobile";
import CompactForm from "@/components/forms/CompactForm";
import { recordPreviewProps } from "@/components/RecordQuickPreview";
import { RichTextContent } from "@/components/rich-text/RichTextContent";
import { useCreateIntent } from "@/hooks/use-create-intent";
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Plus, CheckCircle2, XCircle, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/state";
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

function LeaveSourceNotice({label,source,hasData}:{label:string;source:{isError:boolean;isFetching:boolean;fetchStatus?:"fetching"|"paused"|"idle";refetch:()=>unknown};hasData:boolean}) {
  const paused=source.fetchStatus==="paused";
  if(!source.isError && !source.isFetching && !paused)return null;
  return <div className="leave-source-feedback" data-leave-source={label}>
    {source.isError && <><ErrorState title={`Could not load ${label}`} description={hasData ? "Showing the last loaded information." : "Please retry to load this information."}/><Button type="button" variant="outline" aria-label={`Retry ${label}`} disabled={source.isFetching || paused} onClick={()=>void source.refetch()}>{source.isFetching ? "Retrying…" : "Retry"}</Button></>}
    {paused ? <><p role="status">Waiting for a connection to {hasData ? "refresh" : "load"} {label}.</p>{hasData && !source.isError && <p>Showing the last loaded information.</p>}</> : source.isFetching && <p role="status">{source.isError ? "Retrying" : hasData ? "Refreshing" : "Loading"} {label}…</p>}
  </div>;
}

export default function LeavePage() {
  usePageTitle("Leave");
  const mobile=useMobile();
  const phone=useMobile(480);
  const leaveTabsId=useId();
  const qc = useQueryClient();
  const { user } = useAuthStore();
  const grant=user?.access?.grants.hrms;
  const canApply=!!user?.is_superuser || !user?.access?.managed || !!grant?.enabled&&grant.actions.includes("create");
  const roleKey = getRoleKey(user?.role, user?.is_superuser);
  const canApproveLeave=useDefinitionPermission(["leave_approve"],"approve");
  const canCreateAccount=!!user?.is_superuser,canLinkAccount=!!user?.is_superuser,canManageAccounts=canCreateAccount||canLinkAccount;
  const canCancel=!!user?.is_superuser||!user?.access?.managed||!!grant?.enabled&&grant.actions.includes("edit");
  const hasEmployeeProfile = Boolean(user?.employee_id);
  const [showApplyForm, setShowApplyForm] = useState(false);
  useCreateIntent(kind => { if (kind === "leave" && hasEmployeeProfile && canApply) setShowApplyForm(true); });
  const [activeTab, setActiveTab] = useState<"my" | "approvals" | "calendar">("my");
  const [calendarMonth, setCalendarMonth] = useState(() => new Date());
  const [calendarScope, setCalendarScope] = useState<"mine" | "team" | "all">(canApproveLeave ? "team" : "mine");
  useEffect(() => {
    if(!phone)return;
    if(activeTab==="approvals" && !canApproveLeave)setActiveTab("my");
    const validScope=calendarScope==="team" ? canApproveLeave : calendarScope==="all" ? ["admin","hr"].includes(roleKey) : true;
    if(!validScope)setCalendarScope(canApproveLeave ? "team" : "mine");
  },[phone,activeTab,calendarScope,canApproveLeave,roleKey]);
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
  const [accountPassword, setAccountPassword] = useState("");

  const balanceSource = useQuery({
    queryKey: ["leave-balance"],
    queryFn: () => leaveApi.balance().then((r) => r.data as LeaveBalance[]),
    enabled: hasEmployeeProfile,
  });
  const { data: balances, isLoading: loadingBalance } = balanceSource;

  const myRequestsSource = useQuery({
    queryKey: ["my-leave-requests"],
    queryFn: () => leaveApi.myRequests().then((r) => r.data as LeaveRequest[]),
    enabled: hasEmployeeProfile,
  });
  const { data: myRequests, isLoading: loadingRequests, refetch } = myRequestsSource;

  const approvalsSource = useQuery({
    queryKey: ["all-leave-requests", "Pending"],
    queryFn: () => leaveApi.allRequests({ status: "Pending" }).then((r) => r.data as LeaveRequest[]),
    enabled: canApproveLeave,
    retry: false,
  });
  const { data: allRequests, refetch: refetchAll } = approvalsSource;

  const leaveTypesSource = useQuery({
    queryKey: ["leave-types"],
    queryFn: () => leaveApi.types().then((r) => r.data as LeaveType[]),
  });
  const { data: leaveTypes } = leaveTypesSource;

  const accountEmployeeSource = useQuery({
    queryKey: ["leave-account-employees", accountEmployeeSearch],
    queryFn: () => employeeApi.list({ search: accountEmployeeSearch || undefined, limit: 50 }).then((r) => r.data),
    enabled: canManageAccounts,
  });
  const { data: employeeOptions } = accountEmployeeSource;

  const accountUserSource = useQuery({
    queryKey: ["leave-account-user-options", accountUserSearch, accountEmployeeId],
    queryFn: () => employeeApi.userOptions({ search: accountUserSearch || undefined, include_employee_id: accountEmployeeId || undefined }).then((r) => r.data as UserOption[]),
    enabled: canManageAccounts,
  });
  const { data: userOptions } = accountUserSource;

  const accountRolesSource = useQuery({
    queryKey: ["leave-account-roles"],
    queryFn: () => authApi.roles().then((r) => r.data as Array<{ id: number; name: string }>),
    enabled: canManageAccounts,
  });
  const { data: roles } = accountRolesSource;

  const encashmentSource = useQuery({
    queryKey: ["leave-encashment-requests"],
    queryFn: () => leavePayrollApi.encashmentRequests().then((r) => r.data as LeaveEncashmentRequest[]),
  });
  const { data: encashmentRequests } = encashmentSource;

  const encashmentApprovalsSource = useQuery({
    queryKey: ["leave-encashment-requests", "submitted"],
    queryFn: () => leavePayrollApi.encashmentRequests({ status: "submitted" }).then((r) => r.data as LeaveEncashmentRequest[]),
    enabled: canApproveLeave,
    retry: false,
  });
  const { data: pendingEncashmentRequests } = encashmentApprovalsSource;

  const calendarStart = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth(), 1);
  const calendarEnd = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 0);
  const toDateText = (value: Date) => {
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${value.getFullYear()}-${month}-${day}`;
  };
  const calendarStartText = toDateText(calendarStart);
  const calendarEndText = toDateText(calendarEnd);

  const calendarSource = useQuery({
    queryKey: ["leave-calendar", calendarStartText, calendarEndText, calendarScope],
    queryFn: () =>
      leaveApi.calendar({
        from_date: calendarStartText,
        to_date: calendarEndText,
        scope: calendarScope,
      }).then((r) => r.data as { days: LeaveCalendarDay[]; total_leave_days: number; scope: string }),
  });
  const { data: calendarData, isLoading: loadingCalendar } = calendarSource;

  const { register, handleSubmit, reset, watch, formState: { errors } } = useForm<ApplyForm>({ defaultValues: { leave_type_id: defaultId("leave_type_id", "hrms") } });

  const applyFieldId = useId();
  const applySubmitting = useRef(false);
  const applyOpener = useRef<HTMLButtonElement>(null);
  const [applyCloseRevision, setApplyCloseRevision] = useState(0);
  const requestedFrom=watch("from_date"),requestedTo=watch("to_date"),requestedType=watch("leave_type_id"),requestedMode=watch("leave_mode");
  const leaveDraft = useRecordDraft("hrms:leave:application", watch(), reset, hasEmployeeProfile);
  const applicationCalendar = useQuery({ queryKey: ["leave-application-calendar", user?.id, requestedFrom, requestedTo], enabled: showApplyForm && !!requestedFrom && !!requestedTo && requestedTo >= requestedFrom && Date.parse(requestedTo) - Date.parse(requestedFrom) <= 366 * 86400000, queryFn: () => leaveApi.calendar({ from_date: requestedFrom, to_date: requestedTo, scope: "mine" }).then(response => response.data as { days: LeaveCalendarDay[] }) });
  const applicationHolidays = applicationCalendar.data?.days.flatMap(day => day.holidays) || [];
  const applicationOverlaps = [...new Map((applicationCalendar.data?.days.flatMap(day => day.employees_on_leave) || []).filter(request => ["Pending", "Approved"].includes(request.status)).map(request => [request.id, request])).values()];
  const requestedDays=requestedFrom&&requestedTo&&requestedTo>=requestedFrom?(requestedMode==="Half-day"?0.5:Math.round((Date.parse(requestedTo)-Date.parse(requestedFrom))/86400000)+1):0;
  const selectedBalance=balances?.find(b=>b.leave_type_id===Number(requestedType));
  const applyMutation = useMutation({
    onSettled: () => { applySubmitting.current = false; },
    mutationFn: (data: ApplyForm) =>
      leaveApi.apply({ ...data, leave_type_id: Number(data.leave_type_id) }),
    onSuccess: () => {
      toast({ title: "Leave application submitted" });
      leaveDraft();
      announceCreated({ title: "Leave application submitted", status: "Pending", href: "/hrms/leave", next: [{ label: "Track request", href: "/hrms/leave" }] });
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

  const reviewSubmitting = useRef(false);
  const approveMutation = useMutation({
    onSettled: () => { reviewSubmitting.current = false; },
    mutationFn: ({ id, status, remarks }: { id: number; status: string; remarks: string }) =>
      leaveApi.approve(id, { status, review_remarks: remarks }),
    onSuccess: (_, { status }) => {
      toast({ title: `Leave ${status.toLowerCase()}` });
      void qc.invalidateQueries({queryKey:["mobile-action-badges"]});
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

  const cancelSubmitting = useRef(false);
  const cancelMutation = useMutation({
    onSettled: () => { cancelSubmitting.current=false; },
    mutationFn: (id: number) => leaveApi.cancel(id),
    onSuccess: () => {
      toast({ title: "Leave cancelled" });
      refetch();
      qc.invalidateQueries({ queryKey: ["leave-balance"] });
      qc.invalidateQueries({ queryKey: ["all-leave-requests"] });
    },
  });

  const encashSubmitting = useRef(false);
  const [encashCompletion, setEncashCompletion] = useState(0);
  const requestEncashmentMutation = useMutation({
    onSettled: () => { encashSubmitting.current = false; },
    mutationFn: () =>
      leavePayrollApi.requestEncashment({
        leaveTypeId: Number(encashLeaveTypeId),
        daysToEncash: Number(encashDays),
        remarks: encashRemarks || undefined,
      }),
    onSuccess: () => {
      toast({ title: "Leave encashment requested" });
      if(phone) setEncashCompletion(v => v + 1);
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

  const encashReviewSubmitting = useRef(false);
  const reviewEncashmentMutation = useMutation({
    onSettled: () => { encashReviewSubmitting.current=false; },
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

  function submitEncashDecision(id:number,action:"approve"|"reject") {
    if(phone) { if(!canApproveLeave || reviewEncashmentMutation.isPending || encashReviewSubmitting.current) return; encashReviewSubmitting.current=true; }
    reviewEncashmentMutation.mutate({id,action});
  }

  const maintenanceSubmitting=useRef(false);
  const [maintenanceKind,setMaintenanceKind]=useState<"accruals"|"carry-forward">("accruals");
  const runAccrualsMutation = useMutation({
    onSettled: () => { maintenanceSubmitting.current=false; },
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
    onSettled: () => { maintenanceSubmitting.current=false; },
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

  const maintenanceBusy=runAccrualsMutation.isPending || runCarryForwardMutation.isPending;
  const activeMaintenance=maintenanceKind==="accruals" ? runAccrualsMutation : runCarryForwardMutation;
  function runMaintenance(kind:"accruals"|"carry-forward") {
    if(phone) { if(!canApproveLeave || maintenanceBusy || maintenanceSubmitting.current) return; maintenanceSubmitting.current=true;setMaintenanceKind(kind); }
    if(kind==="accruals") runAccrualsMutation.mutate(); else runCarryForwardMutation.mutate();
  }

  const accountSubmitting = useRef(false);
  const [accountCompletion,setAccountCompletion] = useState(0);
  const linkEmployeeUserMutation = useMutation({
    onSettled: () => { accountSubmitting.current=false; },
    mutationFn: () => employeeApi.linkUser(Number(accountEmployeeId), accountUserId ? Number(accountUserId) : null),
    onSuccess: () => {
      toast({ title: "Employee account linked" });
      if(phone) setAccountCompletion(v=>v+1);
      qc.invalidateQueries({ queryKey: ["leave-account-employees"] });
      qc.invalidateQueries({ queryKey: ["leave-account-user-options"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Could not link employee account";
      toast({ title: "Account link failed", description: msg, variant: "destructive" });
    },
  });

  const createAndLinkUserMutation = useMutation({
    onSettled: () => { accountSubmitting.current=false; },
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
      if(phone) setAccountCompletion(v=>v+1);
      setAccountUserId("");
      qc.invalidateQueries({ queryKey: ["leave-account-employees"] });
      qc.invalidateQueries({ queryKey: ["leave-account-user-options"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Could not create employee login";
      toast({ title: "Account creation failed", description: msg, variant: "destructive" });
    },
  });

  const accountBusy=linkEmployeeUserMutation.isPending || createAndLinkUserMutation.isPending;
  function saveAccount(kind:"link"|"create") {
    if(phone) { if(accountBusy || accountSubmitting.current || !accountEmployeeId || (kind==="link" ? !canLinkAccount || !accountUserId : !canCreateAccount || !accountEmail || !accountPassword)) return; accountSubmitting.current=true; }
    if(kind==="link") linkEmployeeUserMutation.mutate(); else createAndLinkUserMutation.mutate();
  }

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
    if(phone) { if(!canApproveLeave || approveMutation.isPending || reviewSubmitting.current) return; reviewSubmitting.current=true; }
    const fallback = status === "Approved" ? "Approved by HR" : "Rejected by HR";
    approveMutation.mutate({ id, status, remarks: reviewRemarks[id]?.trim() || fallback });
  }

  function moveMonth(offset: number) {
    setCalendarMonth((current) => new Date(current.getFullYear(), current.getMonth() + offset, 1));
  }
  function mobileTabKeys(event: KeyboardEvent<HTMLDivElement>) {
    const index=tabs.indexOf(activeTab);
    const next=event.key==="ArrowRight" ? (index+1)%tabs.length : event.key==="ArrowLeft" ? (index+tabs.length-1)%tabs.length : event.key==="Home" ? 0 : event.key==="End" ? tabs.length-1 : -1;
    if(next<0)return;
    event.preventDefault();setActiveTab(tabs[next]);
    event.currentTarget.querySelector<HTMLButtonElement>(`[data-leave-tab="${tabs[next]}"]`)?.focus();
  }

  return (
    <div className="leave-page space-y-4 sm:space-y-6">
      <div className="leave-page-header flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="page-title">Leave Management</h1>
          <p className="page-description">Employees apply for leave, HR or managers approve or reject with a reason.</p>
        </div>
        <div className="leave-header-actions flex flex-col gap-2 sm:flex-row">
          {canApproveLeave ? (
            <AskAiButton module="HRMS" defaultAgentCode="hrms_leave_assistant" defaultPrompt="Check leave balance and help with leave request/review." />
          ) : null}
          {canApproveLeave ? (
            <>
              <Button size="sm" variant="outline" className="w-full sm:w-auto" onClick={() => runMaintenance("accruals")} disabled={phone ? maintenanceBusy : runAccrualsMutation.isPending}>
                <RefreshCw className="mr-2 h-4 w-4" />
                {runAccrualsMutation.isPending ? "Running..." : "Run Accruals"}
              </Button>
              <Button size="sm" variant="outline" className="w-full sm:w-auto" onClick={() => runMaintenance("carry-forward")} disabled={phone ? maintenanceBusy : runCarryForwardMutation.isPending}>
                <RefreshCw className="mr-2 h-4 w-4" />
                {runCarryForwardMutation.isPending ? "Running..." : "Carry Forward"}
              </Button>
            </>
          ) : null}
          <Button ref={applyOpener} size="sm" className="w-full sm:w-auto" disabled={!canApply} onClick={() => { if (!phone || !applyMutation.isPending) setShowApplyForm((v) => !v); }}>
            <Plus className="mr-2 h-4 w-4" />
            Apply Leave
          </Button>
        </div>
      </div>

      <div className="leave-balances grid grid-cols-1 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-4">
        {phone && hasEmployeeProfile && <LeaveSourceNotice label="leave balances" source={balanceSource} hasData={balances!==undefined}/>}
        {phone && hasEmployeeProfile && !balanceSource.isError && balances?.length===0 && <p className="leave-balance-note" role="status">No leave balances available.</p>}
        {loadingBalance
          ? Array.from({ length: 4 }).map((_, i) => (
              <Card key={i}><CardContent className="p-4"><div className="h-12 skeleton rounded" /></CardContent></Card>
            ))
          : !hasEmployeeProfile ? (
              <Card className="leave-balance-note sm:col-span-3 lg:col-span-4">
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

      {phone && canApproveLeave && (activeMaintenance.isPending || activeMaintenance.isError || activeMaintenance.isSuccess) && <div className="leave-maintenance-feedback rounded-md border p-3 text-sm" role={activeMaintenance.isError ? "alert" : "status"}>
        <p>{maintenanceKind==="accruals" ? "Leave accruals" : "Leave carry-forward"}: {activeMaintenance.isPending ? "processing…" : activeMaintenance.isError ? String((activeMaintenance.error as {response?:{data?:{detail?:string}}})?.response?.data?.detail || "Could not complete this run. Please retry.") : `${(activeMaintenance.data?.data as {processed?:number})?.processed ?? 0} balance rows updated.`}</p>
      </div>}
      {showApplyForm && (
        <SmartCreateModal definition={{ entity: "leave", title: "Apply for leave", presentation: "page", size: "standard" }} mobileSheet={phone} returnFocus={phone ? applyOpener.current : undefined} closeRequestRevision={applyCloseRevision} busy={applyMutation.isPending} onClose={() => { setShowApplyForm(false); }}>
        <Card className="leave-apply-card">
          <CardHeader className="leave-apply-heading">
            <CardTitle className="text-base">Apply for Leave</CardTitle>
          </CardHeader>
          <CardContent>
            <RequestReviewContext kind="leave" employeeId={user?.employee_id || undefined}/>
            <p role="status" className="my-2 text-xs text-muted-foreground">{leaveDraft.status === "restored" ? "Restored your unfinished leave application." : leaveDraft.status === "unavailable" ? "Draft storage unavailable; keep this window open." : "Your application draft is saved in this browser session."}</p>
            {phone && <div className="leave-apply-sources">
              <LeaveSourceNotice label="application balances" source={balanceSource} hasData={balances !== undefined}/>
              {!balances?.length && <LeaveSourceNotice label="application leave types" source={leaveTypesSource} hasData={leaveTypes !== undefined}/>}
              {!applyLeaveTypes.length && balanceSource.isSuccess && !balanceSource.isFetching && (Boolean(balances?.length) || leaveTypesSource.isSuccess && !leaveTypesSource.isFetching) && <p role="status">No leave types are available for this application.</p>}
            </div>}

            <CompactForm compactTabs={!phone} aria-busy={phone ? applyMutation.isPending : undefined} onSubmit={handleSubmit((data) => {if(canApply&&!applyMutation.isPending&&(!phone||!applySubmitting.current)){if(phone)applySubmitting.current=true;applyMutation.mutate(data);}})} className="leave-apply-form grid grid-cols-1 gap-4 sm:grid-cols-2">
              {phone && applyMutation.isError && <p role="alert" className="text-sm text-red-500">{String((applyMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to apply. Your entries are retained; please retry.")}</p>}
              <div className="space-y-1.5">
                <Label htmlFor={phone ? `${applyFieldId}-leave_type_id` : undefined}>Leave Type *</Label>
                <NativeSelect
                  loading={phone && !balances?.length && leaveTypesSource.isFetching && !leaveTypes?.length}
                  id={phone ? `${applyFieldId}-leave_type_id` : undefined} disabled={phone && applyMutation.isPending} aria-invalid={phone ? Boolean(errors.leave_type_id) : undefined} aria-describedby={phone && errors.leave_type_id ? `${applyFieldId}-leave_type_id-error` : undefined} {...register("leave_type_id", { required: "Required" })}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="">Select leave type</option>
                  {applyLeaveTypes.map((t) => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </NativeSelect>
                {errors.leave_type_id && <div id={phone ? `${applyFieldId}-leave_type_id-error` : undefined} role={phone ? "alert" : undefined} className="text-xs text-red-500"><RichTextContent legacyFormat="plain" value={errors.leave_type_id.message}/></div>}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor={phone ? `${applyFieldId}-leave_mode` : undefined}>Mode</Label>
                <NativeSelect
                  id={phone ? `${applyFieldId}-leave_mode` : undefined} disabled={phone && applyMutation.isPending} {...register("leave_mode")}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="Full-day">Full Day</option>
                  <option value="Half-day">Half Day</option>
                </NativeSelect>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor={phone ? `${applyFieldId}-from_date` : undefined}>From Date *</Label>
                <Input type="date" id={phone ? `${applyFieldId}-from_date` : undefined} disabled={phone && applyMutation.isPending} aria-invalid={phone ? Boolean(errors.from_date) : undefined} aria-describedby={phone && errors.from_date ? `${applyFieldId}-from_date-error` : undefined} {...register("from_date", { required: "Required" })} />
                {errors.from_date && <div id={phone ? `${applyFieldId}-from_date-error` : undefined} role={phone ? "alert" : undefined} className="text-xs text-red-500"><RichTextContent legacyFormat="plain" value={errors.from_date.message}/></div>}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor={phone ? `${applyFieldId}-to_date` : undefined}>To Date *</Label>
                <Input type="date" id={phone ? `${applyFieldId}-to_date` : undefined} disabled={phone && applyMutation.isPending} aria-invalid={phone ? Boolean(errors.to_date) : undefined} aria-describedby={phone && errors.to_date ? `${applyFieldId}-to_date-error` : undefined} {...register("to_date", { required: "Required" })} />
                {errors.to_date && <div id={phone ? `${applyFieldId}-to_date-error` : undefined} role={phone ? "alert" : undefined} className="text-xs text-red-500"><RichTextContent legacyFormat="plain" value={errors.to_date.message}/></div>}
              </div>

              <div className={`rounded border bg-muted/30 p-3 text-sm sm:col-span-2 ${mobile ? "mobile-leave-balance" : ""}`} role="status"><p>Estimated request: {requestedDays} day(s) · Available: {selectedBalance?Number(selectedBalance.available).toFixed(1):"Select leave type"} · Estimated balance after request: {selectedBalance?(Number(selectedBalance.available)-requestedDays).toFixed(1):"—"}</p><p className="mt-1 text-xs">Current leave policy counts all calendar days in the inclusive date range, including weekends and holidays. Half-day requests count as 0.5 day. The server validates overlap and available balance before saving.</p></div>
              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor={phone ? `${applyFieldId}-reason` : undefined}>Reason *</Label>
                <textarea aria-label="Reason"
                  id={phone ? `${applyFieldId}-reason` : undefined} disabled={phone && applyMutation.isPending} aria-invalid={phone ? Boolean(errors.reason) : undefined} aria-describedby={phone && errors.reason ? `${applyFieldId}-reason-error` : undefined} {...register("reason", { required: "Required" })}
                  rows={3}
                  className="flex w-full resize-none rounded-md border border-input bg-background px-3 py-2 text-sm"
                  placeholder="Reason for leave..."
                />
                {errors.reason && <div id={phone ? `${applyFieldId}-reason-error` : undefined} role={phone ? "alert" : undefined} className="text-xs text-red-500"><RichTextContent legacyFormat="plain" value={errors.reason.message}/></div>}
              </div>

              <aside className="rounded border p-3 text-sm sm:col-span-2" aria-label="Leave date context">
                <p><strong>Holidays and overlapping requests</strong></p>
                {!requestedFrom || !requestedTo ? <p>Choose a date range to check your calendar.</p> : applicationCalendar.isFetching ? <p role="status">Checking selected dates…</p> : applicationCalendar.isError ? <p role="alert">Calendar could not load. <button type="button" onClick={() => void applicationCalendar.refetch()}>Retry date check</button></p> : applicationCalendar.data ? <><p>{applicationHolidays.length ? applicationHolidays.map(holiday => `${holiday.name} (${holiday.holiday_date})`).join(" · ") : "No applicable holidays in this range."}</p>{applicationOverlaps.length ? <p role="alert">Existing requests: {applicationOverlaps.map(request => `#${request.id}: ${request.from_date}–${request.to_date} (${request.status})`).join("; ")}. Review the dates before submitting.</p> : <p>No pending or approved requests overlap.</p>}</> : <p>Choose a valid date range of up to one year for this preview.</p>}
              </aside>
              <div className="leave-apply-actions flex gap-3 sm:col-span-2">
                <Button data-save-action={phone ? "" : undefined} type="submit" disabled={!canApply||applyMutation.isPending}>
                  {applyMutation.isPending ? "Submitting..." : "Submit Application"}
                </Button>
                <Button type="button" variant="outline" onClick={() => setApplyCloseRevision(v => v + 1)}>
                  Cancel
                </Button>
              </div>
            </CompactForm>
          </CardContent>
        </Card>
        </SmartCreateModal>
      )}

      {canManageAccounts && (
        <MobileDisclosure title="Employee account wizard" maxWidth={480} keepMounted className="leave-secondary">
        <Card>
          <CardHeader className="leave-secondary-heading">
            <CardTitle className="text-base">Employee Account Wizard</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <SmartCreateSection title="Create employee account wizard" size="standard" mobileSheet={phone} completionRevision={phone ? accountCompletion : 0} onClose={() => { if(phone) { setAccountEmployeeId("");setAccountUserId("");setAccountEmail("");setAccountPassword("");linkEmployeeUserMutation.reset();createAndLinkUserMutation.reset(); } }}><div className="leave-account-create space-y-4">{phone && <div className="leave-account-sources">{(linkEmployeeUserMutation.isError || createAndLinkUserMutation.isError) && <p role="alert">{String(((linkEmployeeUserMutation.error || createAndLinkUserMutation.error) as {response?:{data?:{detail?:string}}})?.response?.data?.detail || "Could not save this account action. Your entries are retained; please retry.")}</p>}{accountBusy && <p role="status">Saving employee account…</p>}<LeaveSourceNotice label="account employees" source={accountEmployeeSource} hasData={employeeOptions !== undefined}/><LeaveSourceNotice label="account users" source={accountUserSource} hasData={userOptions !== undefined}/><LeaveSourceNotice label="account roles" source={accountRolesSource} hasData={roles !== undefined}/></div>}<div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto]">
              {phone && <Label htmlFor={`${applyFieldId}-accountEmployeeSearch`}> Search employees</Label>}<Input disabled={phone && accountBusy} id={phone ? `${applyFieldId}-accountEmployeeSearch` : undefined} value={accountEmployeeSearch} onChange={(event) => setAccountEmployeeSearch(event.target.value)} placeholder="Search employee code or name" />
              {phone && <Label htmlFor={`${applyFieldId}-accountEmployeeId`}> Employee</Label>}<NativeSelect disabled={phone && accountBusy} id={phone ? `${applyFieldId}-accountEmployeeId` : undefined} value={accountEmployeeId} onChange={(event) => {
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
              </NativeSelect>
              <Button disabled={phone && accountBusy} variant="outline" onClick={() => qc.invalidateQueries({ queryKey: ["leave-account-employees"] })}>
                Refresh Employees
              </Button>
            </div>

            <div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto]">
              {phone && <Label htmlFor={`${applyFieldId}-accountUserSearch`}> Search existing users</Label>}<Input disabled={phone && accountBusy} id={phone ? `${applyFieldId}-accountUserSearch` : undefined} value={accountUserSearch} onChange={(event) => setAccountUserSearch(event.target.value)} placeholder="Search existing user email" />
              {phone && <Label htmlFor={`${applyFieldId}-accountUserId`}> Existing user</Label>}<NativeSelect disabled={phone && accountBusy} id={phone ? `${applyFieldId}-accountUserId` : undefined} value={accountUserId} onChange={(event) => setAccountUserId(event.target.value)} className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm">
                <option value="">Select unlinked user</option>
                {(userOptions || []).map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.email} {user.employee_code ? `(${user.employee_code})` : ""}
                  </option>
                ))}
              </NativeSelect>
              <Button data-save-action={phone && Boolean(accountUserId) ? "" : undefined} aria-busy={phone ? accountBusy : undefined} disabled={phone && accountBusy || !canLinkAccount || !accountEmployeeId || !accountUserId || linkEmployeeUserMutation.isPending} onClick={() => saveAccount("link")}>
                Link Existing User
              </Button>
            </div>

            <div className="grid gap-3 lg:grid-cols-[1fr_180px_auto]">
              {phone && <Label htmlFor={`${applyFieldId}-accountEmail`}> Login email</Label>}<Input disabled={phone && accountBusy} id={phone ? `${applyFieldId}-accountEmail` : undefined} inputMode={phone ? "email" : undefined} value={accountEmail} onChange={(event) => setAccountEmail(event.target.value)} placeholder="employee@email.com" />
              {phone && <Label htmlFor={`${applyFieldId}-accountPassword`}> Temporary password</Label>}<Input disabled={phone && accountBusy} id={phone ? `${applyFieldId}-accountPassword` : undefined} value={accountPassword} onChange={(event) => setAccountPassword(event.target.value)} placeholder="Temporary password" type="password" />
              <Button data-save-action={phone && !accountUserId ? "" : undefined} aria-busy={phone ? accountBusy : undefined} disabled={phone && accountBusy || !canCreateAccount || !accountEmployeeId || !accountEmail || !accountPassword || createAndLinkUserMutation.isPending} onClick={() => saveAccount("create")}>
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
            </div></div></SmartCreateSection>
          </CardContent>
        </Card>
        </MobileDisclosure>
      )}

      <MobileDisclosure title="Leave encashment" maxWidth={480} keepMounted className="leave-secondary">
      <Card>
        <CardHeader className="leave-secondary-heading">
          <CardTitle className="text-base">Leave Encashment</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <SmartCreateSection title="Create leave encashment" size="compact" mobileSheet={phone} completionRevision={phone ? encashCompletion : 0} onClose={() => { if(phone) { setEncashLeaveTypeId(""); setEncashDays(""); setEncashRemarks(""); requestEncashmentMutation.reset(); } }}><div className="leave-encash-create space-y-4">{phone && <><LeaveSourceNotice label="encashable leave types" source={leaveTypesSource} hasData={leaveTypes !== undefined}/>{requestEncashmentMutation.isError && <p role="alert" className="text-sm text-red-500">{String((requestEncashmentMutation.error as {response?:{data?:{detail?:string}}})?.response?.data?.detail || "Failed to request leave encashment. Your entries are retained.")}</p>}</>}<div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_120px_1.4fr_auto]">
            {phone && <Label htmlFor={`${applyFieldId}-encash-type`}>Leave type</Label>}<NativeSelect
              id={phone ? `${applyFieldId}-encash-type` : undefined} disabled={phone && requestEncashmentMutation.isPending}
              value={encashLeaveTypeId}
              onChange={(event) => setEncashLeaveTypeId(event.target.value)}
              className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">Select encashable leave</option>
              {leaveTypes?.map((type) => (
                <option key={type.id} value={type.id}>{type.name}</option>
              ))}
            </NativeSelect>
            {phone && <Label htmlFor={`${applyFieldId}-encash-days`}>Days</Label>}<Input id={phone ? `${applyFieldId}-encash-days` : undefined} disabled={phone && requestEncashmentMutation.isPending} value={encashDays} onChange={(event) => setEncashDays(event.target.value)} placeholder="Days" type="number" min="0" step="0.5" />
            {phone && <Label htmlFor={`${applyFieldId}-encash-remarks`}>Remarks (optional)</Label>}<Input id={phone ? `${applyFieldId}-encash-remarks` : undefined} disabled={phone && requestEncashmentMutation.isPending} value={encashRemarks} onChange={(event) => setEncashRemarks(event.target.value)} placeholder="Remarks" />
            <Button
              data-save-action={phone ? "" : undefined} aria-busy={phone ? requestEncashmentMutation.isPending : undefined}
              onClick={() => { if(phone) { if(!canApply || !encashLeaveTypeId || !encashDays || requestEncashmentMutation.isPending || encashSubmitting.current) return; encashSubmitting.current=true; } requestEncashmentMutation.mutate(); }}
              disabled={!canApply || !encashLeaveTypeId || !encashDays || requestEncashmentMutation.isPending}
            >
              Request
            </Button>
          </div></div></SmartCreateSection>

          {phone && <LeaveSourceNotice label="encashment requests" source={encashmentSource} hasData={encashmentRequests!==undefined}/>}
            {(!phone || encashmentRequests!==undefined) && <div className="overflow-x-auto">
            <GridTable gridId="apps/hrms/pages/leave/LeavePage:table-1" className="w-full min-w-[900px] text-sm">
              <thead className="border-b bg-muted/50">
                <tr>
                  {["Leave type", "Days", "Rate", "Amount", "Status", "Requested", "Remarks"].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {!encashmentRequests?.length ? (
                  <tr><td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">{phone && encashmentSource.isError ? "No encashment requests in the last loaded result" : "No leave encashment requests yet"}</td></tr>
                ) : (
                  encashmentRequests.slice(0, phone ? undefined : 5).map((item) => (
                    <tr {...recordPreviewProps(item)} key={item.id} className="border-b">
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
            </GridTable>
          </div>}
        </CardContent>
      </Card>
      </MobileDisclosure>

      <div className="leave-tabs flex gap-2 overflow-x-auto border-b" role={phone ? "tablist" : undefined} aria-label={phone ? "Leave views" : undefined} onKeyDown={phone ? mobileTabKeys : undefined}>
        {tabs.map((tab) => (
          <button
            key={tab}
            data-leave-tab={tab}
            role={phone ? "tab" : undefined}
            id={phone ? `${leaveTabsId}-tab-${tab}` : undefined}
            aria-controls={phone ? `${leaveTabsId}-panel-${tab}` : undefined}
            tabIndex={phone ? activeTab===tab ? 0 : -1 : undefined}
            aria-selected={phone ? activeTab === tab : undefined}
            onClick={() => setActiveTab(tab)}
            className={`border-b-2 px-1 pb-2 text-sm font-medium transition-colors ${
              activeTab === tab ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab === "my" ? "My Requests" : tab === "approvals" ? "Pending Approvals" : "Calendar"}
            {tab === "approvals" && pendingApprovals.length > 0 && (
              <span data-count-badge data-count-tone="amber" className="ml-2 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-xs text-primary-foreground">
                {pendingApprovals.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {activeTab === "my" && (
        <Card className="leave-main-panel" data-leave-panel="my" role={phone ? "tabpanel" : undefined} id={phone ? `${leaveTabsId}-panel-my` : undefined} aria-labelledby={phone ? `${leaveTabsId}-tab-my` : undefined}>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">My Leave Requests</CardTitle>
              <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={phone ? "Refresh my requests" : undefined} disabled={phone && (myRequestsSource.isFetching || myRequestsSource.fetchStatus==="paused")} onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {(!phone || canApproveLeave) && <div className="border-b p-4">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">Pending Leave Encashment</p>
                  <p className="text-xs text-muted-foreground">Approved requests become payroll earnings in the next open pay period.</p>
                </div>
                <span data-count-badge data-count-tone="amber" className="rounded-full bg-muted px-2 py-1 text-xs">{phone && pendingEncashmentRequests===undefined ? "—" : pendingEncashments.length}</span>
              </div>
              {phone && <LeaveSourceNotice label="encashment approvals" source={encashmentApprovalsSource} hasData={pendingEncashmentRequests!==undefined}/>}
              {pendingEncashments.length === 0 ? (phone && pendingEncashmentRequests===undefined ? null :
                <p className="rounded-md border border-dashed px-3 py-4 text-center text-sm text-muted-foreground">{phone && encashmentApprovalsSource.isError ? "No encashment approvals in the last loaded result" : "No pending encashment approvals"}</p>
              ) : (
                <GroupedRecords scope="apps/hrms/pages/leave/LeavePage:cards-1" items={(pendingEncashments) || []} fields={standardRecordGroups((pendingEncashments) || [])} gridClassName="space-y-2" renderItem={(item) => (
                    <div key={item.id} className="leave-encash-review grid gap-2 rounded-md border p-3 lg:grid-cols-[1fr_120px_140px_1fr_auto] lg:items-center">
                      <div>
                        <p className="text-sm font-medium">{item.employeeName || item.employeeCode || "Employee"}</p>
                        <p className="text-xs text-muted-foreground">{item.leaveTypeName} - {Number(item.daysToEncash).toFixed(2)} day(s)</p>
                      </div>
                      <p className="text-sm font-semibold">₹{Number(item.amount || 0).toLocaleString("en-IN")}</p>
                      <p className="text-xs text-muted-foreground">Rate ₹{Number(item.encashmentRate || 0).toLocaleString("en-IN")}</p>
                      <Input
                        aria-label={phone ? `Approval remarks for encashment #${item.id}` : undefined} disabled={phone && reviewEncashmentMutation.isPending}
                        value={encashReviewRemarks[item.id] || ""}
                        onChange={(event) => setEncashReviewRemarks((current) => ({ ...current, [item.id]: event.target.value }))}
                        placeholder="Approval remarks"
                      />
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => submitEncashDecision(item.id,"approve")} disabled={reviewEncashmentMutation.isPending}>Approve</Button>
                        <Button size="sm" variant="outline" onClick={() => submitEncashDecision(item.id,"reject")} disabled={reviewEncashmentMutation.isPending}>Reject</Button>
                      </div>
                      {phone && reviewEncashmentMutation.variables?.id===item.id && reviewEncashmentMutation.isPending && <p role="status">Saving encashment {reviewEncashmentMutation.variables.action} decision…</p>}
                      {phone && reviewEncashmentMutation.variables?.id===item.id && reviewEncashmentMutation.isError && <p role="alert" className="text-sm text-red-500">{String((reviewEncashmentMutation.error as {response?:{data?:{detail?:string}}})?.response?.data?.detail || "Could not save this decision. Your remarks are retained; please retry.")}</p>}
                    </div>
                  )}/>
              )}
            </div>}
            {phone && (cancelMutation.isPending || cancelMutation.isError) && <div className="leave-cancel-feedback p-3" role={cancelMutation.isError ? "alert" : "status"}>
              <p>Leave request #{cancelMutation.variables}: {cancelMutation.isPending ? "cancelling…" : String((cancelMutation.error as {response?:{data?:{detail?:string}}})?.response?.data?.detail || "Could not cancel this request. Please retry from its actions.")}</p>
            </div>}
            {phone && hasEmployeeProfile && <LeaveSourceNotice label="my leave requests" source={myRequestsSource} hasData={myRequests!==undefined}/>}{phone && !hasEmployeeProfile && <p role="status" className="p-3">Link an employee profile to load your leave requests.</p>}
            {(!phone || hasEmployeeProfile && myRequests!==undefined) && <div className="overflow-x-auto">
              <GridTable gridId="apps/hrms/pages/leave/LeavePage:table-2" className="w-full min-w-[900px] text-sm">
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
                      <tr {...recordPreviewProps(_)} key={i} className="border-b">
                        <td colSpan={9} className="px-4 py-3"><div className="h-4 skeleton rounded" /></td>
                      </tr>
                    ))
                  ) : !myRequests || myRequests.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="px-4 py-10 text-center text-muted-foreground">
                        <CalendarDays className="mx-auto mb-2 h-8 w-8 opacity-30" />
                        {phone && myRequestsSource.isError ? "No leave requests in the last loaded result" : "No leave requests yet"}
                      </td>
                    </tr>
                  ) : (
                    myRequests.map((r) => (
                      <tr {...recordPreviewProps(r)} key={r.id} className="border-b hover:bg-muted/30">
                        <td className="px-4 py-3 font-medium">{r.leave_type?.name}</td>
                        <td className="px-4 py-3" data-grid-value={r.from_date}>{formatDate(r.from_date)}</td>
                        <td className="px-4 py-3" data-grid-value={r.to_date}>{formatDate(r.to_date)}</td>
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
                              disabled={!canCancel||cancelMutation.isPending} onClick={() => { if(phone) { if(!canCancel || cancelMutation.isPending || cancelSubmitting.current) return; cancelSubmitting.current=true; } cancelMutation.mutate(r.id); }}
                            >
                              Cancel
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </GridTable>
            </div>}
          </CardContent>
        </Card>
      )}

      {activeTab === "calendar" && (
        <Card className="leave-main-panel" data-leave-panel="calendar" role={phone ? "tabpanel" : undefined} id={phone ? `${leaveTabsId}-panel-calendar` : undefined} aria-labelledby={phone ? `${leaveTabsId}-tab-calendar` : undefined}>
          <CardHeader>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <CardTitle className="text-base">Leave Calendar</CardTitle>
                <p className="mt-1 text-sm text-muted-foreground">
                  {phone && calendarData===undefined ? "—" : calendarData?.total_leave_days || 0} scheduled leave days in {monthLabel}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="outline" size="icon" className="h-9 w-9" aria-label={phone ? "Previous month" : undefined} onClick={() => moveMonth(-1)}>
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <div className="min-w-[150px] text-center text-sm font-medium">{monthLabel}</div>
                <Button variant="outline" size="icon" className="h-9 w-9" aria-label={phone ? "Next month" : undefined} onClick={() => moveMonth(1)}>
                  <ChevronRight className="h-4 w-4" />
                </Button>
                <NativeSelect
                  aria-label={phone ? "Calendar scope" : undefined}
                  value={calendarScope}
                  onChange={(event) => setCalendarScope(event.target.value as "mine" | "team" | "all")}
                  className="flex h-9 rounded-md border border-input bg-background px-3 py-1 text-sm"
                >
                  <option value="mine">My leave</option>
                  {canApproveLeave && <option value="team">Team leave</option>}
                  {["admin", "hr"].includes(roleKey) && <option value="all">All employees</option>}
                </NativeSelect>
                <Button variant="ghost" size="icon" className="h-9 w-9" aria-label={phone ? "Refresh leave calendar" : undefined} disabled={phone && (calendarSource.isFetching || calendarSource.fetchStatus==="paused")} onClick={() => qc.invalidateQueries({ queryKey: ["leave-calendar"] })}>
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {phone && <LeaveSourceNotice label="leave calendar" source={calendarSource} hasData={calendarData!==undefined}/>}
            {phone && calendarData!==undefined && !calendarSource.isError && !loadingCalendar && !calendarDays.length && <p role="status">No calendar entries in this period.</p>}
            {phone && calendarData===undefined && !loadingCalendar ? null : loadingCalendar ? (
              <div className="h-64 rounded-lg border bg-muted/30" />
            ) : (
              <div className="leave-calendar-days grid gap-2 sm:grid-cols-2 lg:grid-cols-7">
                {calendarDays.map((day) => {
                  const date = new Date(`${day.date}T00:00:00`);
                  const isWeekend = [0, 6].includes(date.getDay());
                  return (
                    <div
                      key={day.date}
                      className={`leave-calendar-day min-h-[150px] rounded-lg border p-3 ${isWeekend ? "bg-muted/30" : "bg-card"}`}
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
                            <div className="leave-calendar-person-info mt-0.5 flex items-center justify-between gap-2 text-muted-foreground">
                              <span className="truncate">{request.leave_type?.name || "Leave"}</span>
                              <span className={request.status === "Approved" ? "text-green-700" : "text-amber-700"}>
                                {request.status}
                              </span>
                            </div>
                          </div>
                        ))}
                        {day.employees_on_leave.length > 3 && (phone ? <details className="leave-calendar-more"><summary>{day.employees_on_leave.length - 3} more people</summary>{day.employees_on_leave.slice(3).map(request => <div key={request.id} className="rounded-md border px-2 py-1 text-xs"><p className="font-medium">{request.employee ? `${request.employee.first_name} ${request.employee.last_name}` : `Employee #${request.employee_id}`}</p><div className="leave-calendar-person-info text-muted-foreground"><span>{request.leave_type?.name || "Leave"}</span><span className={request.status === "Approved" ? "text-green-700" : "text-amber-700"}>{request.status}</span></div></div>)}</details> : <p className="text-xs text-muted-foreground">+{day.employees_on_leave.length - 3} more</p>)}
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
        <Card className="leave-main-panel" data-leave-panel="approvals" role={phone ? "tabpanel" : undefined} id={phone ? `${leaveTabsId}-panel-approvals` : undefined} aria-labelledby={phone ? `${leaveTabsId}-tab-approvals` : undefined}>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Pending Approvals</CardTitle>
              <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={phone ? "Refresh pending approvals" : undefined} disabled={phone && (approvalsSource.isFetching || approvalsSource.fetchStatus==="paused")} onClick={() => refetchAll()}>
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {phone && <LeaveSourceNotice label="leave approvals" source={approvalsSource} hasData={allRequests!==undefined}/>}
            {phone && allRequests===undefined ? null : mobile ? <div className="p-3">{pendingApprovals.length ? pendingApprovals.map(r=><article key={r.id} className="mobile-approval-card" aria-busy={phone && approveMutation.isPending && approveMutation.variables?.id===r.id ? true : undefined}><header>{phone ? <div><strong>{r.employee ? `${r.employee.first_name} ${r.employee.last_name}` : `Employee #${r.employee_id}`}</strong>{r.employee?.employee_id && <p>{r.employee.employee_id}</p>}</div> : <strong>{r.employee ? `${r.employee.first_name} ${r.employee.last_name}` : `Employee #${r.employee_id}`}</strong>}<span>{r.days_count} day(s)</span></header><p>{r.leave_type?.name} · {formatDate(r.from_date)} – {formatDate(r.to_date)}</p><p>{r.reason || "No reason provided"}</p><label className="text-sm">Review reason<textarea disabled={phone && approveMutation.isPending} className="block w-full rounded-lg border p-2 bg-background" value={reviewRemarks[r.id]||""} onChange={e=>setReviewRemarks(v=>({...v,[r.id]:e.target.value}))}/></label>{phone && approveMutation.variables?.id===r.id && approveMutation.isPending && <p role="status">Saving {approveMutation.variables.status.toLowerCase()} decision…</p>}{phone && approveMutation.variables?.id===r.id && approveMutation.isError && <p role="alert" className="text-sm text-red-500">{String((approveMutation.error as {response?:{data?:{detail?:string}}})?.response?.data?.detail || "Could not save this decision. Your review reason is retained; please retry.")}</p>}<footer><Button disabled={approveMutation.isPending} onClick={()=>submitDecision(r.id,"Approved")}>Approve</Button><Button variant="outline" disabled={approveMutation.isPending} onClick={()=>submitDecision(r.id,"Rejected")}>Reject</Button></footer></article>):<p>{phone && approvalsSource.isError ? "No pending approvals in the last loaded result" : "No pending approvals"}</p>}</div> : <div className="overflow-x-auto">
              <GridTable gridId="apps/hrms/pages/leave/LeavePage:table-3" className="w-full min-w-[900px] text-sm">
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
                      <tr {...recordPreviewProps(r)} key={r.id} className="border-b hover:bg-muted/30">
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
                        <td className="px-4 py-3" data-grid-value={r.from_date}>{formatDate(r.from_date)}</td>
                        <td className="px-4 py-3" data-grid-value={r.to_date}>{formatDate(r.to_date)}</td>
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
              </GridTable>
            </div>}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

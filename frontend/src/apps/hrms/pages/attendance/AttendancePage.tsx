import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Clock, CheckCircle2, XCircle, CalendarDays, MapPin,
  RefreshCw, ChevronLeft, ChevronRight, AlertCircle
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState, LoadingState } from "@/components/ui/state";
import AskAiButton from "@/components/ai-agents/AskAiButton";
import { attendanceApi } from "@/services/api";
import { formatDateTime, statusColor } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";
import { usePageTitle } from "@/hooks/use-page-title";
import { useAuthStore } from "@/store/authStore";

function getMonthDays(year: number, month: number) {
  const days: Date[] = [];
  const d = new Date(year, month - 1, 1);
  while (d.getMonth() === month - 1) {
    days.push(new Date(d));
    d.setDate(d.getDate() + 1);
  }
  return days;
}

const DAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const REGISTER_STATUSES = ["Present", "Absent", "Half-day", "Holiday", "Weekly Off", "WFH"];

interface RegisterEdit {
  selected: boolean;
  status: string;
  hours_worked: string;
  ot_hours: string;
  remarks: string;
}

interface RegisterRow {
  attendance_id?: number | null;
  employee_id: number;
  employee_code?: string | null;
  employee_name: string;
  department?: string | null;
  branch?: string | null;
  date: string;
  status: string;
  hours_worked: number | string;
  ot_hours: number | string;
  remarks?: string | null;
}

const statusDotColor: Record<string, string> = {
  Present: "bg-green-500",
  Absent: "bg-red-400",
  "Half-day": "bg-orange-400",
  WFH: "bg-blue-400",
  Holiday: "bg-purple-400",
  "On Leave": "bg-yellow-400",
};

export default function AttendancePage() {
  usePageTitle("Attendance");
  const qc = useQueryClient();
  const { user } = useAuthStore();
  const hasEmployeeProfile = Boolean(user?.employee_id);
  const today = new Date();
  const [viewMonth, setViewMonth] = useState(today.getMonth() + 1);
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [lockReason, setLockReason] = useState("Payroll cutoff");
  const [unlockReason, setUnlockReason] = useState("Approved correction");
  const [registerDate, setRegisterDate] = useState(today.toISOString().slice(0, 10));
  const [registerSearch, setRegisterSearch] = useState("");
  const [bulkStatus, setBulkStatus] = useState("Present");
  const [registerEdits, setRegisterEdits] = useState<Record<number, RegisterEdit>>({});

  const { data: todayRecord, isLoading: loadingToday } = useQuery({
    queryKey: ["attendance-today"],
    queryFn: () => attendanceApi.getToday().then((r) => r.data),
    enabled: hasEmployeeProfile,
  });

  const { data: summary } = useQuery({
    queryKey: ["attendance-summary", viewMonth, viewYear],
    queryFn: () =>
      attendanceApi.monthlySummary(viewMonth, viewYear).then((r) => r.data),
    enabled: hasEmployeeProfile,
  });

  const fromDate = `${viewYear}-${String(viewMonth).padStart(2, "0")}-01`;
  const lastDay = new Date(viewYear, viewMonth, 0).getDate();
  const toDate = `${viewYear}-${String(viewMonth).padStart(2, "0")}-${lastDay}`;

  const { data: records } = useQuery({
    queryKey: ["attendance-records", viewMonth, viewYear],
    queryFn: () =>
      attendanceApi.myAttendance(fromDate, toDate).then((r) => r.data),
    enabled: hasEmployeeProfile,
  });

  const { data: monthLocks } = useQuery({
    queryKey: ["attendance-locks", viewMonth, viewYear],
    queryFn: () => attendanceApi.locks({ month: viewMonth, year: viewYear }).then((r) => r.data),
  });

  const activeLock = Array.isArray(monthLocks)
    ? monthLocks.find((item) => item.status === "Locked") || monthLocks[0]
    : undefined;

  const { data: attendanceRegister, isLoading: loadingRegister } = useQuery({
    queryKey: ["attendance-register", registerDate, registerSearch],
    queryFn: () => attendanceApi.register({ date: registerDate, search: registerSearch || undefined }).then((r) => r.data),
  });

  const lockMonthMutation = useMutation({
    mutationFn: () => attendanceApi.lockMonth({ month: viewMonth, year: viewYear, reason: lockReason }),
    onSuccess: () => {
      toast({ title: "Attendance month locked" });
      qc.invalidateQueries({ queryKey: ["attendance-locks"] });
    },
    onError: () => toast({ title: "Could not lock attendance", variant: "destructive" }),
  });

  const unlockMonthMutation = useMutation({
    mutationFn: () => attendanceApi.unlockMonth(activeLock.id, unlockReason),
    onSuccess: () => {
      toast({ title: "Attendance month unlocked" });
      qc.invalidateQueries({ queryKey: ["attendance-locks"] });
    },
    onError: () => toast({ title: "Could not unlock attendance", variant: "destructive" }),
  });

  const checkInMutation = useMutation({
    mutationFn: () => attendanceApi.checkIn({ source: "Web" }),
    onSuccess: () => {
      toast({ title: "Checked in successfully!" });
      qc.invalidateQueries({ queryKey: ["attendance-today"] });
      qc.invalidateQueries({ queryKey: ["attendance-summary"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Check-in failed";
      toast({ title: "Error", description: msg, variant: "destructive" });
    },
  });

  const checkOutMutation = useMutation({
    mutationFn: () => attendanceApi.checkOut({}),
    onSuccess: () => {
      toast({ title: "Checked out successfully!" });
      qc.invalidateQueries({ queryKey: ["attendance-today"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Check-out failed";
      toast({ title: "Error", description: msg, variant: "destructive" });
    },
  });

  const saveRegisterMutation = useMutation({
    mutationFn: (entries: Array<Record<string, unknown>>) => attendanceApi.bulkEntry({ entries }),
    onSuccess: (response) => {
      toast({ title: "Attendance saved", description: `${response.data.saved} row${response.data.saved === 1 ? "" : "s"} saved.` });
      setRegisterEdits({});
      qc.invalidateQueries({ queryKey: ["attendance-register"] });
      qc.invalidateQueries({ queryKey: ["attendance-summary"] });
      qc.invalidateQueries({ queryKey: ["attendance-records"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Attendance save failed";
      toast({ title: "Could not save attendance", description: msg, variant: "destructive" });
    },
  });

  const days = getMonthDays(viewYear, viewMonth);
  const firstDow = days[0].getDay();

  const recordsByDate: Record<string, { status: string; check_in?: string; check_out?: string }> = {};
  if (Array.isArray(records)) {
    for (const r of records) {
      const key = r.attendance_date?.slice(0, 10) || "";
      if (key) recordsByDate[key] = r;
    }
  }

  const prevMonth = () => {
    if (viewMonth === 1) { setViewMonth(12); setViewYear((y) => y - 1); }
    else setViewMonth((m) => m - 1);
  };
  const nextMonth = () => {
    if (viewMonth === 12) { setViewMonth(1); setViewYear((y) => y + 1); }
    else setViewMonth((m) => m + 1);
  };

  const isCheckedIn = todayRecord && todayRecord.check_in && !todayRecord.check_out;
  const isCheckedOut = todayRecord && todayRecord.check_out;
  const registerRows = (attendanceRegister?.items || []) as RegisterRow[];
  const selectedRegisterIds = Object.entries(registerEdits).filter(([, value]) => value.selected).map(([id]) => Number(id));

  function editFor(row: RegisterRow): RegisterEdit {
    return registerEdits[row.employee_id] || {
      selected: false,
      status: row.status || "Absent",
      hours_worked: String(row.hours_worked ?? 0),
      ot_hours: String(row.ot_hours ?? 0),
      remarks: row.remarks || "",
    };
  }

  function updateRegisterRow(employeeId: number, patch: Partial<RegisterEdit>) {
    setRegisterEdits((current) => ({ ...current, [employeeId]: { ...(current[employeeId] || { selected: false, status: "Present", hours_worked: "8", ot_hours: "0", remarks: "" }), ...patch } }));
  }

  function saveRegisterRows(onlySelected = false) {
    const rowsToSave = registerRows
      .filter((row) => !onlySelected || selectedRegisterIds.includes(row.employee_id))
      .map((row) => {
        const edit = editFor(row);
        return {
          employee_id: row.employee_id,
          date: registerDate,
          status: edit.status,
          hours_worked: Number(edit.hours_worked || 0),
          ot_hours: Number(edit.ot_hours || 0),
          remarks: edit.remarks || undefined,
        };
      });
    if (!rowsToSave.length) {
      toast({ title: "Select at least one row", variant: "destructive" });
      return;
    }
    saveRegisterMutation.mutate(rowsToSave);
  }

  function applyBulkStatus() {
    if (!selectedRegisterIds.length) {
      toast({ title: "Select rows before bulk update", variant: "destructive" });
      return;
    }
    const defaultHours = bulkStatus === "Present" || bulkStatus === "WFH" ? "8" : bulkStatus === "Half-day" ? "4" : "0";
    setRegisterEdits((current) => {
      const next = { ...current };
      for (const id of selectedRegisterIds) {
        next[id] = { ...(next[id] || { selected: true, status: bulkStatus, hours_worked: defaultHours, ot_hours: "0", remarks: "" }), selected: true, status: bulkStatus, hours_worked: defaultHours };
      }
      return next;
    });
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      <div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="page-title">Attendance</h1>
            <p className="page-description">Track your daily attendance and monthly summary.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <AskAiButton module="HRMS" defaultAgentCode="hrms_attendance_anomaly" defaultPrompt="Analyze attendance anomalies for this employee." />
            <Button asChild variant="outline">
              <Link to="/hrms/attendance/shift-roster">
                <CalendarDays className="h-4 w-4" />
                Shift Roster
              </Link>
            </Button>
          </div>
        </div>
      </div>

      {/* Today's action card */}
      <Card>
        <CardContent className="p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Today - {today.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}</p>
              {loadingToday ? (
                <div className="h-6 w-40 skeleton rounded" />
              ) : isCheckedOut ? (
                <div className="flex items-center gap-2 text-green-600">
                  <CheckCircle2 className="h-5 w-5" />
                  <span className="font-semibold">Completed - {formatDateTime(todayRecord.check_in)} to {formatDateTime(todayRecord.check_out)}</span>
                </div>
              ) : isCheckedIn ? (
                <div className="flex items-center gap-2 text-blue-600">
                  <Clock className="h-5 w-5" />
                  <span className="font-semibold">Checked in at {formatDateTime(todayRecord.check_in)}</span>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <AlertCircle className="h-5 w-5" />
                  <span>{hasEmployeeProfile ? "Not checked in yet" : "Use Attendance Register below for HR entry"}</span>
                </div>
              )}
            </div>
            <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:gap-3">
              {hasEmployeeProfile && !isCheckedIn && !isCheckedOut && (
                <Button
                  onClick={() => checkInMutation.mutate()}
                  disabled={checkInMutation.isPending}
                  className="w-full bg-green-600 hover:bg-green-700 sm:w-auto"
                >
                  <Clock className="h-4 w-4 mr-2" />
                  Check In
                </Button>
              )}
              {hasEmployeeProfile && isCheckedIn && (
                <Button
                  onClick={() => checkOutMutation.mutate()}
                  disabled={checkOutMutation.isPending}
                  variant="outline"
                  className="w-full sm:w-auto"
                >
                  <XCircle className="h-4 w-4 mr-2" />
                  Check Out
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Monthly summary stats */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: "Present", value: summary.present ?? 0, color: "text-green-600" },
            { label: "Absent", value: summary.absent ?? 0, color: "text-red-500" },
            { label: "Half-day", value: summary.half_day ?? 0, color: "text-orange-500" },
            { label: "WFH", value: summary.wfh ?? 0, color: "text-blue-600" },
          ].map((s) => (
            <Card key={s.label}>
              <CardContent className="p-4 text-center">
                <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                <p className="text-xs text-muted-foreground mt-1">{s.label}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Attendance Lock</CardTitle>
          <CardDescription>Freeze attendance for payroll after HR review.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-[1fr_1fr_auto_auto]">
          <div className="rounded-md border p-3 text-sm">
            <p className="text-muted-foreground">Current month</p>
            <p className="font-semibold">{viewMonth}/{viewYear}</p>
          </div>
          <div className="rounded-md border p-3 text-sm">
            <p className="text-muted-foreground">Status</p>
            <Badge variant={activeLock?.status === "Locked" ? "default" : "outline"}>{activeLock?.status || "Open"}</Badge>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 md:col-span-2">
            <Input value={lockReason} onChange={(event) => setLockReason(event.target.value)} placeholder="Lock reason" />
            <Input value={unlockReason} onChange={(event) => setUnlockReason(event.target.value)} placeholder="Unlock reason" />
          </div>
          <Button onClick={() => lockMonthMutation.mutate()} disabled={lockMonthMutation.isPending || activeLock?.status === "Locked"}>
            Lock Month
          </Button>
          <Button variant="outline" onClick={() => unlockMonthMutation.mutate()} disabled={unlockMonthMutation.isPending || activeLock?.status !== "Locked"}>
            Unlock
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <CardTitle className="text-base">Attendance Register</CardTitle>
              <CardDescription>HR can manually enter and bulk save attendance for payroll.</CardDescription>
            </div>
            <div className="grid gap-2 sm:grid-cols-[150px_220px_auto]">
              <Input type="date" value={registerDate} onChange={(event) => setRegisterDate(event.target.value)} />
              <Input value={registerSearch} onChange={(event) => setRegisterSearch(event.target.value)} placeholder="Search employee" />
              <Button variant="outline" onClick={() => qc.invalidateQueries({ queryKey: ["attendance-register"] })}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Refresh
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-7">
            {[
              ["Present", attendanceRegister?.present ?? 0],
              ["Absent", attendanceRegister?.absent ?? 0],
              ["Half Day", attendanceRegister?.half_day ?? 0],
              ["Holiday", attendanceRegister?.holiday ?? 0],
              ["Weekly Off", attendanceRegister?.weekly_off ?? 0],
              ["WFH", attendanceRegister?.wfh ?? 0],
              ["OT Hours", attendanceRegister?.overtime_hours ?? 0],
            ].map(([label, value]) => (
              <div key={label} className="rounded-md border p-3 text-sm">
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="text-lg font-semibold">{Number(value || 0).toFixed(label === "OT Hours" ? 2 : 1)}</p>
              </div>
            ))}
          </div>

          <div className="ui-toolbar">
            <label className="sr-only" htmlFor="bulk-attendance-status">Bulk attendance status</label>
            <select id="bulk-attendance-status" value={bulkStatus} onChange={(event) => setBulkStatus(event.target.value)} className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm">
              {REGISTER_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
            </select>
            <Button variant="outline" onClick={applyBulkStatus}>Apply to selected</Button>
            <Button onClick={() => saveRegisterRows(true)} disabled={saveRegisterMutation.isPending || !selectedRegisterIds.length}>
              Save Selected
            </Button>
            <Button variant="secondary" onClick={() => saveRegisterRows(false)} disabled={saveRegisterMutation.isPending || !registerRows.length}>
              Save All Visible
            </Button>
            <span className="text-xs text-muted-foreground">{selectedRegisterIds.length} selected</span>
          </div>

          <div className="ui-table-wrap">
            <table className="ui-table min-w-[1120px]">
              <thead>
                <tr>
                  {["", "Employee Code", "Employee Name", "Department", "Branch", "Date", "Status", "Hours Worked", "OT Hours", "Remarks"].map((h) => (
                    <th key={h} className={h === "" ? "w-10" : undefined}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loadingRegister ? (
                  <tr><td colSpan={10}><LoadingState label="Loading attendance register" className="border-0" /></td></tr>
                ) : !registerRows.length ? (
                  <tr><td colSpan={10}><EmptyState title="No employees found" description="Adjust the search or confirm that employees are active for this register date." className="border-0" /></td></tr>
                ) : registerRows.map((row) => {
                  const edit = editFor(row);
                  return (
                    <tr key={row.employee_id}>
                      <td>
                        <input aria-label={`Select ${row.employee_name}`} type="checkbox" checked={edit.selected} onChange={(event) => updateRegisterRow(row.employee_id, { selected: event.target.checked })} />
                      </td>
                      <td className="font-medium">{row.employee_code || "-"}</td>
                      <td>{row.employee_name}</td>
                      <td className="text-muted-foreground">{row.department || "-"}</td>
                      <td className="text-muted-foreground">{row.branch || "-"}</td>
                      <td>{registerDate}</td>
                      <td>
                        <select aria-label={`Status for ${row.employee_name}`} value={edit.status} onChange={(event) => updateRegisterRow(row.employee_id, { status: event.target.value })} className="h-9 rounded-md border border-input bg-background px-2 text-sm">
                          {REGISTER_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
                        </select>
                      </td>
                      <td>
                        <Input aria-label={`Hours worked for ${row.employee_name}`} className="h-9 w-24" type="number" min="0" step="0.5" value={edit.hours_worked} onChange={(event) => updateRegisterRow(row.employee_id, { hours_worked: event.target.value })} />
                      </td>
                      <td>
                        <Input aria-label={`Overtime hours for ${row.employee_name}`} className="h-9 w-24" type="number" min="0" step="0.5" value={edit.ot_hours} onChange={(event) => updateRegisterRow(row.employee_id, { ot_hours: event.target.value })} />
                      </td>
                      <td>
                        <Input aria-label={`Remarks for ${row.employee_name}`} className="h-9 min-w-48" value={edit.remarks} onChange={(event) => updateRegisterRow(row.employee_id, { remarks: event.target.value })} placeholder="Remarks" />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Calendar */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle className="text-base">
              {new Date(viewYear, viewMonth - 1).toLocaleString("en", { month: "long", year: "numeric" })}
            </CardTitle>
            <div className="flex items-center gap-2 self-end sm:self-auto">
              <Button variant="outline" size="icon" className="h-8 w-8" onClick={prevMonth}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button variant="outline" size="icon" className="h-8 w-8" onClick={nextMonth}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-7 gap-1 text-center mb-2">
            {DAY_LABELS.map((d) => (
              <div key={d} className="text-xs font-medium text-muted-foreground py-1">{d}</div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1 text-xs sm:text-sm">
            {Array.from({ length: firstDow }).map((_, i) => (
              <div key={`pad-${i}`} />
            ))}
            {days.map((day) => {
              const key = day.toISOString().slice(0, 10);
              const rec = recordsByDate[key];
              const isToday = key === today.toISOString().slice(0, 10);
              const isFuture = day > today;
              const dot = rec ? statusDotColor[rec.status] : null;

              return (
                <div
                  key={key}
                  className={`relative flex h-9 w-full flex-col items-center justify-center rounded-lg text-xs sm:h-10 sm:text-sm
                    ${isToday ? "bg-primary text-primary-foreground font-bold" : ""}
                    ${!isToday && rec ? "bg-muted/50" : ""}
                    ${isFuture ? "opacity-40" : ""}
                  `}
                >
                  <span>{day.getDate()}</span>
                  {dot && !isToday && (
                    <span className={`absolute bottom-1 h-1.5 w-1.5 rounded-full ${dot}`} />
                  )}
                </div>
              );
            })}
          </div>

          {/* Legend */}
          <div className="flex flex-wrap gap-3 mt-4 pt-4 border-t">
            {Object.entries(statusDotColor).map(([label, cls]) => (
              <div key={label} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span className={`h-2.5 w-2.5 rounded-full ${cls}`} />
                {label}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Recent records table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Attendance Records</CardTitle>
          <CardDescription>
            {new Date(viewYear, viewMonth - 1).toLocaleString("en", { month: "long", year: "numeric" })}
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="ui-table-wrap border-0">
            <table className="ui-table min-w-[640px]">
              <thead>
                <tr>
                  {["Date", "Status", "Check In", "Check Out", "Hours"].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {!records || records.length === 0 ? (
                  <tr>
                    <td colSpan={5}><EmptyState title="No records for this period" description="Attendance will appear here after check-in, biometric import, or HR register save." className="border-0" /></td>
                  </tr>
                ) : (
                  [...records].reverse().map((r: {
                    id: number;
                    attendance_date: string;
                    status: string;
                    check_in?: string;
                    check_out?: string;
                    total_hours?: number;
                  }) => (
                    <tr key={r.id}>
                      <td>
                        {new Date(r.attendance_date).toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}
                      </td>
                      <td>
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(r.status)}`}>
                          {r.status}
                        </span>
                      </td>
                      <td className="text-muted-foreground">
                        {r.check_in ? new Date(r.check_in).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : "-"}
                      </td>
                      <td className="text-muted-foreground">
                        {r.check_out ? new Date(r.check_out).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : "-"}
                      </td>
                      <td>
                        {r.total_hours != null ? `${r.total_hours.toFixed(1)}h` : "-"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

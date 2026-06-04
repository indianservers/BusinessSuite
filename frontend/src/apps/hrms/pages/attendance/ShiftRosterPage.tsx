import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CalendarDays, Copy, Loader2, Send } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { attendanceApi, companyApi, employeeApi, shiftRosterApi } from "@/services/api";
import { toast } from "@/hooks/use-toast";
import { usePageTitle } from "@/hooks/use-page-title";
import { cn } from "@/lib/utils";

type Shift = {
  id: number;
  name: string;
  code?: string;
  start_time?: string;
  end_time?: string;
  working_hours?: number | string;
};

type EmployeeRow = {
  id: number;
  employeeId?: string;
  employee_id?: string;
  name?: string;
  first_name?: string;
  last_name?: string;
  departmentId?: number;
  department_id?: number;
  departmentName?: string;
};

type Roster = {
  id: number;
  employeeId: number;
  shiftId: number;
  rosterDate: string;
  status: string;
  shift?: { id: number; name: string; code?: string; startTime?: string; endTime?: string; workingHours?: number };
  conflicts?: string[];
};

type Department = { id: number; name: string };

const shiftColors = ["bg-blue-50 text-blue-800 border-blue-200", "bg-green-50 text-green-800 border-green-200", "bg-amber-50 text-amber-800 border-amber-200", "bg-violet-50 text-violet-800 border-violet-200", "bg-rose-50 text-rose-800 border-rose-200"];

function toIsoDate(value: Date) {
  const copy = new Date(value);
  copy.setMinutes(copy.getMinutes() - copy.getTimezoneOffset());
  return copy.toISOString().slice(0, 10);
}

function startOfWeek(value: Date) {
  const copy = new Date(value);
  const day = copy.getDay() || 7;
  copy.setDate(copy.getDate() - day + 1);
  return copy;
}

function employeeName(employee: EmployeeRow) {
  return employee.name || `${employee.first_name || ""} ${employee.last_name || ""}`.trim() || employee.employee_id || employee.employeeId || `Employee #${employee.id}`;
}

export default function ShiftRosterPage() {
  usePageTitle("Shift Roster");
  const qc = useQueryClient();
  const [weekStart, setWeekStart] = useState(toIsoDate(startOfWeek(new Date())));
  const [departmentId, setDepartmentId] = useState("");
  const [selectedShiftId, setSelectedShiftId] = useState<number | null>(null);
  const [bulkShiftId, setBulkShiftId] = useState("");
  const [weeklyOffShiftId, setWeeklyOffShiftId] = useState("");
  const [weeklyOffDay, setWeeklyOffDay] = useState("6");
  const [lastConflicts, setLastConflicts] = useState<Array<{ employeeId?: number; rosterDate?: string; messages?: string[] }>>([]);

  const weekDays = useMemo(() => {
    const start = new Date(`${weekStart}T00:00:00`);
    return Array.from({ length: 7 }, (_, index) => {
      const day = new Date(start);
      day.setDate(start.getDate() + index);
      return { date: toIsoDate(day), label: day.toLocaleDateString("en-IN", { weekday: "short", day: "2-digit", month: "short" }) };
    });
  }, [weekStart]);
  const params = { from: weekDays[0].date, to: weekDays[6].date, departmentId: departmentId || undefined };

  const shifts = useQuery({ queryKey: ["shift-roster-shifts"], queryFn: () => attendanceApi.listShifts().then((r) => r.data as Shift[]) });
  const departments = useQuery({ queryKey: ["shift-roster-departments"], queryFn: () => companyApi.listDepartments().then((r) => r.data as Department[]) });
  const roster = useQuery({
    queryKey: ["shift-roster", params],
    queryFn: () => shiftRosterApi.list(params).then((r) => r.data as { employees: EmployeeRow[]; rosters: Roster[] }),
  });
  const weeklyOffs = useQuery({
    queryKey: ["shift-weekly-offs", weeklyOffShiftId],
    queryFn: () => attendanceApi.weeklyOffs({ shift_id: weeklyOffShiftId || undefined }).then((r) => r.data as Array<{ id: number; shift_id: number; weekday: number; week_number?: number; is_active: boolean }>),
  });
  const employeesFallback = useQuery({
    queryKey: ["shift-roster-employees-fallback", departmentId],
    queryFn: () => employeeApi.list({ department_id: departmentId || undefined, limit: 100, per_page: 100 }).then((r) => r.data),
    enabled: !roster.data?.employees?.length,
  });

  const employees: EmployeeRow[] = roster.data?.employees?.length
    ? roster.data.employees
    : Array.isArray(employeesFallback.data) ? employeesFallback.data : employeesFallback.data?.items || employeesFallback.data?.data || [];

  const rosterByCell = useMemo(() => {
    const map = new Map<string, Roster>();
    for (const item of roster.data?.rosters || []) {
      map.set(`${item.employeeId}:${item.rosterDate.slice(0, 10)}`, item);
    }
    return map;
  }, [roster.data]);

  const assign = useMutation({
    mutationFn: ({ employeeId, shiftId, date }: { employeeId: number; shiftId: number; date: string }) =>
      shiftRosterApi.assign({ employeeId, shiftId, rosterDate: date, status: "draft" }),
    onSuccess: (response) => {
      const conflicts = response.data.conflicts || [];
      setLastConflicts(conflicts.length ? [{ messages: conflicts }] : []);
      toast({ title: conflicts.length ? "Shift assigned with warnings" : "Shift assigned" });
      qc.invalidateQueries({ queryKey: ["shift-roster"] });
    },
    onError: () => toast({ title: "Could not assign shift", variant: "destructive" }),
  });

  const bulkAssign = useMutation({
    mutationFn: () => shiftRosterApi.bulkAssign({
      shiftId: Number(bulkShiftId),
      fromDate: weekDays[0].date,
      toDate: weekDays[6].date,
      departmentId: departmentId ? Number(departmentId) : undefined,
      status: "draft",
    }),
    onSuccess: (response) => {
      setLastConflicts(response.data.conflicts || []);
      toast({ title: "Bulk roster assigned", description: `${response.data.assigned} cells updated.` });
      qc.invalidateQueries({ queryKey: ["shift-roster"] });
    },
    onError: () => toast({ title: "Bulk assignment failed", variant: "destructive" }),
  });

  const copyWeek = useMutation({
    mutationFn: () => {
      const source = new Date(`${weekStart}T00:00:00`);
      source.setDate(source.getDate() - 7);
      return shiftRosterApi.copyWeek({
        sourceWeekStart: toIsoDate(source),
        targetWeekStart: weekStart,
        departmentId: departmentId ? Number(departmentId) : undefined,
        status: "draft",
      });
    },
    onSuccess: (response) => {
      setLastConflicts(response.data.conflicts || []);
      toast({ title: "Previous week copied", description: `${response.data.copied} assignments copied.` });
      qc.invalidateQueries({ queryKey: ["shift-roster"] });
    },
    onError: () => toast({ title: "Could not copy previous week", variant: "destructive" }),
  });

  const publish = useMutation({
    mutationFn: () => shiftRosterApi.publish({
      fromDate: weekDays[0].date,
      toDate: weekDays[6].date,
      departmentId: departmentId ? Number(departmentId) : undefined,
    }),
    onSuccess: (response) => {
      toast({ title: "Roster published", description: `${response.data.published} assignments published to ESS.` });
      qc.invalidateQueries({ queryKey: ["shift-roster"] });
    },
    onError: () => toast({ title: "Could not publish roster", variant: "destructive" }),
  });

  const remove = useMutation({
    mutationFn: (id: number) => shiftRosterApi.delete(id),
    onSuccess: () => {
      toast({ title: "Roster cell cleared" });
      qc.invalidateQueries({ queryKey: ["shift-roster"] });
    },
  });

  const createWeeklyOff = useMutation({
    mutationFn: () => attendanceApi.createWeeklyOff({
      shift_id: Number(weeklyOffShiftId),
      weekday: Number(weeklyOffDay),
      week_number: null,
      is_active: true,
    }),
    onSuccess: () => {
      toast({ title: "Weekly off saved" });
      qc.invalidateQueries({ queryKey: ["shift-weekly-offs"] });
    },
    onError: () => toast({ title: "Could not save weekly off", variant: "destructive" }),
  });

  function dropShift(employeeId: number, date: string, data: string) {
    const shiftId = Number(data || selectedShiftId);
    if (!shiftId) return;
    assign.mutate({ employeeId, shiftId, date });
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="page-title">Shift Roster</h1>
          <p className="page-description">Build, validate, and publish weekly shift assignments for teams.</p>
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          <div className="space-y-1">
            <Label>Week start</Label>
            <Input type="date" value={weekStart} onChange={(event) => setWeekStart(toIsoDate(startOfWeek(new Date(`${event.target.value}T00:00:00`))))} />
          </div>
          <div className="space-y-1">
            <Label>Department</Label>
            <select className="h-10 rounded-md border bg-background px-3 text-sm" value={departmentId} onChange={(event) => setDepartmentId(event.target.value)}>
              <option value="">All departments</option>
              {(departments.data || []).map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <Label>Bulk shift</Label>
            <select className="h-10 rounded-md border bg-background px-3 text-sm" value={bulkShiftId} onChange={(event) => setBulkShiftId(event.target.value)}>
              <option value="">Select shift</option>
              {(shifts.data || []).map((shift) => <option key={shift.id} value={shift.id}>{shift.name}</option>)}
            </select>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[280px_1fr]">
        <Card>
          <CardHeader><CardTitle className="text-base">Shift Palette</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {(shifts.data || []).map((shift, index) => (
              <button
                key={shift.id}
                type="button"
                draggable
                onDragStart={(event) => event.dataTransfer.setData("shiftId", String(shift.id))}
                onClick={() => setSelectedShiftId(shift.id)}
                className={cn("w-full rounded-md border p-3 text-left text-sm", shiftColors[index % shiftColors.length], selectedShiftId === shift.id && "ring-2 ring-primary")}
              >
                <p className="font-semibold">{shift.name}</p>
                <p className="text-xs opacity-80">{shift.code || "SHIFT"} - {String(shift.start_time || "").slice(0, 5)} to {String(shift.end_time || "").slice(0, 5)}</p>
              </button>
            ))}
            {!shifts.isLoading && !shifts.data?.length && <p className="text-sm text-muted-foreground">Create shifts in HRMS settings before building a roster.</p>}
            <div className="flex flex-col gap-2 pt-3">
              <Button variant="outline" onClick={() => copyWeek.mutate()} disabled={copyWeek.isPending}>
                {copyWeek.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Copy className="h-4 w-4" />} Copy Previous Week
              </Button>
              <Button variant="outline" onClick={() => bulkAssign.mutate()} disabled={!bulkShiftId || bulkAssign.isPending}>
                <CalendarDays className="h-4 w-4" /> Bulk Assign Week
              </Button>
              <Button onClick={() => publish.mutate()} disabled={publish.isPending}>
                {publish.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Publish Roster
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Weekly Off Setup</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1">
              <Label>Shift</Label>
              <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={weeklyOffShiftId} onChange={(event) => setWeeklyOffShiftId(event.target.value)}>
                <option value="">Select shift</option>
                {(shifts.data || []).map((shift) => <option key={shift.id} value={shift.id}>{shift.name}</option>)}
              </select>
            </div>
            <div className="space-y-1">
              <Label>Weekly off day</Label>
              <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={weeklyOffDay} onChange={(event) => setWeeklyOffDay(event.target.value)}>
                {["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((label, index) => (
                  <option key={label} value={index}>{label}</option>
                ))}
              </select>
            </div>
            <Button className="w-full" variant="outline" onClick={() => createWeeklyOff.mutate()} disabled={!weeklyOffShiftId || createWeeklyOff.isPending}>
              Save Weekly Off
            </Button>
            <div className="space-y-2 text-sm">
              {(weeklyOffs.data || []).slice(0, 6).map((item) => (
                <div key={item.id} className="flex items-center justify-between rounded-md border p-2">
                  <span>Shift #{item.shift_id}</span>
                  <Badge variant="outline">{["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][item.weekday] || item.weekday}</Badge>
                </div>
              ))}
              {!weeklyOffs.isLoading && weeklyOffShiftId && !weeklyOffs.data?.length && <p className="text-muted-foreground">No weekly offs configured for this shift.</p>}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-base">Weekly Roster</CardTitle>
              <Badge variant="outline">{employees.length} employees</Badge>
            </div>
          </CardHeader>
          <CardContent>
            {roster.isLoading ? <div className="h-64 animate-pulse rounded bg-muted" /> : (
              <div className="overflow-x-auto rounded-lg border">
                <table className="w-full min-w-[980px] text-sm">
                  <thead className="bg-muted/60">
                    <tr>
                      <th className="sticky left-0 z-10 w-56 bg-muted px-3 py-3 text-left">Employee</th>
                      {weekDays.map((day) => <th key={day.date} className="px-3 py-3 text-left">{day.label}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {employees.map((employee) => (
                      <tr key={employee.id} className="border-t">
                        <td className="sticky left-0 z-10 bg-background px-3 py-3">
                          <p className="font-medium">{employeeName(employee)}</p>
                          <p className="text-xs text-muted-foreground">{employee.employeeId || employee.employee_id || employee.id} {employee.departmentName ? `- ${employee.departmentName}` : ""}</p>
                        </td>
                        {weekDays.map((day) => {
                          const cell = rosterByCell.get(`${employee.id}:${day.date}`);
                          const shiftIndex = shifts.data?.findIndex((shift) => shift.id === cell?.shiftId) ?? 0;
                          return (
                            <td
                              key={day.date}
                              onDragOver={(event) => event.preventDefault()}
                              onDrop={(event) => dropShift(employee.id, day.date, event.dataTransfer.getData("shiftId"))}
                              onClick={() => selectedShiftId && dropShift(employee.id, day.date, String(selectedShiftId))}
                              className="h-24 min-w-32 cursor-pointer border-l p-2 align-top hover:bg-muted/30"
                            >
                              {cell ? (
                                <div className={cn("rounded-md border p-2", shiftColors[Math.max(shiftIndex, 0) % shiftColors.length])}>
                                  <div className="flex items-start justify-between gap-2">
                                    <div>
                                      <p className="font-medium">{cell.shift?.code || cell.shift?.name || "Shift"}</p>
                                      <p className="text-xs">{String(cell.shift?.startTime || "").slice(0, 5)}-{String(cell.shift?.endTime || "").slice(0, 5)}</p>
                                    </div>
                                    <button type="button" className="text-xs opacity-70 hover:opacity-100" onClick={(event) => { event.stopPropagation(); remove.mutate(cell.id); }}>Clear</button>
                                  </div>
                                  <Badge className="mt-2 capitalize" variant={cell.status === "published" ? "outline" : "secondary"}>{cell.status}</Badge>
                                  {!!cell.conflicts?.length && <AlertTriangle className="mt-2 h-4 w-4 text-amber-600" />}
                                </div>
                              ) : (
                                <span className="text-xs text-muted-foreground">Drop shift</span>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                    {!employees.length && (
                      <tr><td colSpan={8} className="px-3 py-10 text-center text-muted-foreground">No employees available for this filter.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {!!lastConflicts.length && (
        <Card className="border-amber-200 bg-amber-50/60">
          <CardHeader><CardTitle className="flex items-center gap-2 text-base text-amber-900"><AlertTriangle className="h-5 w-5" /> Conflict Warnings</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm text-amber-900">
            {lastConflicts.slice(0, 8).map((item, index) => (
              <div key={index} className="rounded-md border border-amber-200 bg-background/70 p-2">
                <p className="font-medium">{item.employeeId ? `Employee #${item.employeeId}` : "Roster warning"} {item.rosterDate ? `on ${item.rosterDate}` : ""}</p>
                {(item.messages || []).map((message) => <p key={message}>{message}</p>)}
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

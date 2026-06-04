import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarDays, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { attendanceApi } from "@/services/api";
import { formatDateTime, statusColor } from "@/lib/utils";
import { usePageTitle } from "@/hooks/use-page-title";

type AttendanceRow = {
  id?: number;
  date?: string;
  attendance_date?: string;
  status?: string;
  hours_worked?: number | string;
  overtime_hours?: number | string;
  check_in?: string;
  check_out?: string;
  remarks?: string;
};

function isoDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

export default function MyAttendancePage() {
  usePageTitle("My Attendance");
  const today = new Date();
  const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
  const [fromDate, setFromDate] = useState(isoDate(firstDay));
  const [toDate, setToDate] = useState(isoDate(today));

  const month = useMemo(() => Number(fromDate.slice(5, 7)) || today.getMonth() + 1, [fromDate, today]);
  const year = useMemo(() => Number(fromDate.slice(0, 4)) || today.getFullYear(), [fromDate, today]);

  const todayQuery = useQuery({
    queryKey: ["my-attendance-today"],
    queryFn: () => attendanceApi.getToday().then((r) => r.data as AttendanceRow | null),
    retry: false,
  });

  const attendance = useQuery({
    queryKey: ["my-attendance", fromDate, toDate],
    queryFn: () => attendanceApi.myAttendance(fromDate, toDate).then((r) => r.data as AttendanceRow[]),
    retry: false,
  });

  const summary = useQuery({
    queryKey: ["my-attendance-summary", month, year],
    queryFn: () => attendanceApi.monthlySummary(month, year).then((r) => r.data as Record<string, number>),
    retry: false,
  });

  const rows = Array.isArray(attendance.data) ? attendance.data : [];
  const todayRecord = todayQuery.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">My Attendance</h1>
        <p className="text-sm text-muted-foreground">View your attendance, hours, and overtime without register or lock controls.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        {[
          ["Present", summary.data?.present_days],
          ["Absent", summary.data?.absent_days],
          ["Half Day", summary.data?.half_days],
          ["Overtime", summary.data?.overtime_hours],
        ].map(([label, value]) => (
          <Card key={label}>
            <CardContent className="p-4">
              <p className="text-xs uppercase text-muted-foreground">{label}</p>
              <p className="mt-1 text-2xl font-semibold">{value ?? 0}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Clock className="h-4 w-4" />
            Today
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm md:grid-cols-4">
          <div>
            <p className="text-muted-foreground">Status</p>
            <Badge className={statusColor(todayRecord?.status || "Not Marked")}>{todayRecord?.status || "Not Marked"}</Badge>
          </div>
          <div>
            <p className="text-muted-foreground">Check In</p>
            <p>{todayRecord?.check_in ? formatDateTime(todayRecord.check_in) : "-"}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Check Out</p>
            <p>{todayRecord?.check_out ? formatDateTime(todayRecord.check_out) : "-"}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Hours</p>
            <p>{todayRecord?.hours_worked ?? "-"}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="gap-4 md:flex-row md:items-center md:justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <CalendarDays className="h-4 w-4" />
            Attendance History
          </CardTitle>
          <div className="grid gap-2 sm:grid-cols-2">
            <Input type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} />
            <Input type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} />
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-2 pr-4 font-medium">Date</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                  <th className="py-2 pr-4 font-medium">Hours</th>
                  <th className="py-2 pr-4 font-medium">OT Hours</th>
                  <th className="py-2 pr-4 font-medium">Remarks</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={row.id || `${row.date}-${index}`} className="border-b last:border-0">
                    <td className="py-3 pr-4">{row.attendance_date || row.date || "-"}</td>
                    <td className="py-3 pr-4"><Badge className={statusColor(row.status || "Not Marked")}>{row.status || "Not Marked"}</Badge></td>
                    <td className="py-3 pr-4">{row.hours_worked ?? "-"}</td>
                    <td className="py-3 pr-4">{row.overtime_hours ?? 0}</td>
                    <td className="py-3 pr-4">{row.remarks || "-"}</td>
                  </tr>
                ))}
                {!rows.length && (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-muted-foreground">
                      {attendance.isLoading ? "Loading attendance..." : "No attendance found for this period."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

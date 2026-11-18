import {useRecordScope} from "@/lib/record-scope";
import {useAuthStore} from "@/store/authStore";
import {Button} from "@/components/ui/button";
import "./my-roster-mobile.css";
import GridTable from "@/shared/data-grid/GridTable";
import { recordPreviewProps } from "@/components/RecordQuickPreview";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarDays } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { shiftRosterApi } from "@/services/api";
import { statusColor } from "@/lib/utils";
import { usePageTitle } from "@/hooks/use-page-title";

type RosterRow = {
  id?: number;
  employee_id?: number;
  employee_name?: string;
  employee_code?: string;
  roster_date?: string;
  rosterDate?:string;
  employeeId?:number;
  shift?:{name?:string;code?:string}|null;
  shift_name?: string;
  shift_code?: string;
  status?: string;
};

function isoDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export default function MyRosterPage() {
  usePageTitle("My Roster");
  const actor=useAuthStore(state=>state.user);
  const scope=useRecordScope();
  const today = new Date();
  const nextWeek = new Date(today);
  nextWeek.setDate(today.getDate() + 7);
  const [fromDate, setFromDate] = useState(isoDate(today));
  const [toDate, setToDate] = useState(isoDate(nextWeek));

  const roster = useQuery({
    queryKey: ["my-roster", fromDate, toDate,actor?.employee_id,scope],
    enabled:!!actor?.employee_id,
    queryFn: () => shiftRosterApi.list({from:fromDate,to:toDate,employeeId:actor?.employee_id}).then((r) => r.data as { rosters?: RosterRow[] } | RosterRow[]),
    retry: false,
  });

  const loadedRows=Array.isArray(roster.data)?roster.data:roster.data?.rosters||[];
  const rows=loadedRows.map(row=>({...row,roster_date:row.roster_date??row.rosterDate,shift_name:row.shift_name??row.shift?.name,shift_code:row.shift_code??row.shift?.code}));

  return (
    <div className="hrms-my-roster-page space-y-6">
      <div>
        <h1 className="page-title">My Roster</h1>
        <p className="text-sm text-muted-foreground">View your assigned shifts and weekly offs. Roster publishing and bulk tools are restricted to HR.</p>
      </div>

      <Card>
        <CardHeader className="gap-4 md:flex-row md:items-center md:justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <CalendarDays className="h-4 w-4" />
            Shift Schedule
          </CardTitle>
          <div className="grid gap-2 sm:grid-cols-2">
            <Input aria-label="Roster from date" type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} />
            <Input aria-label="Roster to date" type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} />
          </div>
        </CardHeader>
        <CardContent>
          {!actor?.employee_id&&<p role="status">An employee profile is required to view your roster.</p>}
          {actor?.employee_id&&roster.isPending&&<p role="status">Loading your roster…</p>}
          {roster.isError&&<p role="alert">Your roster could not load. <Button variant="outline" disabled={roster.isFetching} onClick={()=>roster.refetch()}>Retry my roster</Button></p>}
          {!!actor?.employee_id&&!!roster.data&&<div className="overflow-x-auto">
            <GridTable gridId="apps/hrms/pages/attendance/MyRosterPage:table-1" className="min-w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-2 pr-4 font-medium">Date</th>
                  <th className="py-2 pr-4 font-medium">Shift</th>
                  <th className="py-2 pr-4 font-medium">Code</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr {...recordPreviewProps(row)} key={row.id || `${row.roster_date}-${index}`} className="border-b last:border-0">
                    <td className="py-3 pr-4">{row.roster_date || "-"}</td>
                    <td className="py-3 pr-4">{row.shift_name || "Weekly Off"}</td>
                    <td className="py-3 pr-4">{row.shift_code || "-"}</td>
                    <td className="py-3 pr-4"><Badge className={statusColor(row.status || "Scheduled")}>{row.status || "Scheduled"}</Badge></td>
                  </tr>
                ))}
                {!rows.length && (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-muted-foreground">
                      {roster.isLoading ? "Loading roster..." : "No roster found for this period."}
                    </td>
                  </tr>
                )}
              </tbody>
            </GridTable>
          </div>}
        </CardContent>
      </Card>
    </div>
  );
}

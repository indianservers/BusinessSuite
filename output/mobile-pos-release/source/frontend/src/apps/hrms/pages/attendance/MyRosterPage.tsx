import {selectedBranch} from "@/lib/branch-context";
import {useMobile} from "@/components/mobile/useMobile";
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
  return date.toISOString().slice(0, 10);
}

function browserRosterScope(){try{return [sessionStorage.getItem("suite-tenant"),sessionStorage.getItem("suite-organization"),selectedBranch()];}catch{return [];}}

export default function MyRosterPage() {
  usePageTitle("My Roster");
  const phone=useMobile(480),actor=useAuthStore(state=>state.user);
  const scope=phone?JSON.stringify([actor?.id,actor?.employee_id,actor?.access,actor?.role,actor?.is_superuser,...browserRosterScope()]):"";
  const today = new Date();
  const nextWeek = new Date(today);
  nextWeek.setDate(today.getDate() + 7);
  const [fromDate, setFromDate] = useState(isoDate(today));
  const [toDate, setToDate] = useState(isoDate(nextWeek));

  const roster = useQuery({
    queryKey: ["my-roster", fromDate, toDate,...(phone?[scope]:[])],
    enabled:!phone||!!actor?.employee_id,
    queryFn: () => shiftRosterApi.list(phone?{from:fromDate,to:toDate,employeeId:actor?.employee_id}:{ from_date: fromDate, to_date: toDate }).then((r) => r.data as { rosters?: RosterRow[] } | RosterRow[]),
    retry: false,
  });

  const loadedRows=Array.isArray(roster.data)?roster.data:roster.data?.rosters||[];
  const rows=phone?loadedRows.map(row=>({...row,roster_date:row.roster_date??row.rosterDate,shift_name:row.shift_name??row.shift?.name,shift_code:row.shift_code??row.shift?.code})):loadedRows;

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
          {phone&&!actor?.employee_id&&<p role="status">An employee profile is required to view your roster.</p>}
          {phone&&actor?.employee_id&&roster.isPending&&<p role="status">Loading your roster…</p>}
          {phone&&roster.isError&&<p role="alert">Your roster could not load. <Button variant="outline" disabled={roster.isFetching} onClick={()=>roster.refetch()}>Retry my roster</Button></p>}
          {(!phone||!!actor?.employee_id&&!!roster.data)&&<div className="overflow-x-auto">
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

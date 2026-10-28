import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { formatDate } from "@/lib/utils";
type Day = { date: string; leaves: { employee_name: string; status: string }[]; holidays: string[] };
type Availability = { offset: number; days: Day[]; today: { employee_id: number; name: string; status: string }[]; moments: { employee_id: number; name: string; kind: string; date: string }[]; probation_due: { employee_id: number; name: string; due_date: string }[] };
export default function TeamAvailability() {
  const userId = useAuthStore(s => s.user?.id);
  const [month, setMonth] = useState(new Date().toLocaleDateString("en-CA").slice(0, 7));
  const [day, setDay] = useState<Day | null>(null);
  const query = useQuery({ queryKey: ["team-availability", userId, month], queryFn: () => api.get<Availability>("/reports/my-team/availability", { params: { year: Number(month.slice(0, 4)), month: Number(month.slice(5)) } }).then(r => r.data), enabled: /^\d{4}-\d{2}$/.test(month) });
  return <Card className="min-w-0"><CardHeader><CardTitle className="text-base">Team availability & upcoming reviews</CardTitle></CardHeader><CardContent className="space-y-3"><label className="block text-sm">Calendar month<Input type="month" value={month} onChange={e => { setMonth(e.target.value); setDay(null); }} /></label>{query.isPending && <p role="status">Loading team calendar…</p>}{query.isError && <p role="alert">Team calendar could not load. <button className="underline" onClick={() => query.refetch()}>Retry calendar</button></p>}
    {query.data && <><div className="overflow-x-auto"><div className="grid min-w-[490px] grid-cols-7 gap-1 text-xs">{["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(d => <p key={d} className="text-center text-muted-foreground">{d}</p>)}{Array.from({ length: query.data.offset }, (_, i) => <span key={`offset-${i}`} />)}{query.data.days.map(d => <button key={d.date} className="min-h-16 rounded border p-2 text-left hover:bg-muted" aria-label={`Availability ${d.date}`} onClick={() => setDay(d)}><p>{Number(d.date.slice(8))}</p>{d.holidays.length > 0 && <p className="text-primary">Holiday</p>}{d.leaves.length > 0 && <p>{d.leaves.length} leave requests</p>}</button>)}</div></div>
      {day && <div className="space-y-1 rounded border p-3 text-sm"><p className="font-medium">{formatDate(day.date)}</p>{day.holidays.map(h => <p key={h}>{h}</p>)}{day.leaves.map((l, i) => <p key={i}>{l.employee_name} · {l.status}</p>)}{!day.leaves.length && !day.holidays.length && <p className="text-muted-foreground">No leave requests or holidays recorded for this day.</p>}</div>}
      <details><summary className="cursor-pointer text-sm">Today's recorded attendance ({query.data.today.length})</summary>{query.data.today.map(row => <p key={row.employee_id} className="mt-2 text-sm">{row.name} · {row.status}</p>)}</details>
      {query.data.moments.length > 0 && <div><p className="text-sm font-medium">People moments in the next 7 days</p>{query.data.moments.map((row, i) => <p key={i} className="text-sm"><Link className="underline" to={`/hrms/employees/${row.employee_id}`}>{row.name}</Link> · {row.kind} · {formatDate(row.date)}</p>)}</div>}
      {query.data.probation_due.length > 0 && <div><p className="text-sm font-medium">Probation reviews due within 30 days</p>{query.data.probation_due.map(row => <p key={row.employee_id} className="text-sm"><Link className="underline" to={`/hrms/employees/${row.employee_id}`}>{row.name}</Link> · {formatDate(row.due_date)} · <Link className="underline" to="/hrms/probation">Open review</Link></p>)}</div>}
    </>}
  </CardContent></Card>;
}

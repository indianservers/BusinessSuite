import { useState } from "react";
import EmployeeSearchSelect from "../../components/EmployeeSearchSelect";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, DoorOpen, Plus, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { employeeApi, exitApi } from "@/services/api";
import { toast } from "@/hooks/use-toast";
import { usePageTitle } from "@/hooks/use-page-title";
import { formatDate } from "@/lib/utils";

export default function ExitPage() {
  usePageTitle("Exit Management");
  const qc = useQueryClient();
  const [employeeId, setEmployeeId] = useState("");
  const [lastWorkingDate, setLastWorkingDate] = useState("");
  const [reason, setReason] = useState("");
  const [checklistRecordId, setChecklistRecordId] = useState("");
  const [taskName, setTaskName] = useState("");

  const employees = useQuery({ queryKey: ["exit-employees"], queryFn: () => employeeApi.list({ per_page: 100 }).then((r) => r.data.items) });
  const records = useQuery({ queryKey: ["exit-records"], queryFn: () => exitApi.records().then((r) => r.data) });

  const create = useMutation({
    mutationFn: () => exitApi.createRecord({
      employee_id: Number(employeeId),
      exit_type: "Resignation",
      resignation_date: new Date().toISOString().slice(0, 10),
      last_working_date: lastWorkingDate || undefined,
      reason,
    }),
    onSuccess: () => {
      toast({ title: "Exit record created" });
      setEmployeeId("");
      setReason("");
      qc.invalidateQueries({ queryKey: ["exit-records"] });
    },
    onError: () => toast({ title: "Could not create exit record", variant: "destructive" }),
  });
  const approve = useMutation({
    mutationFn: (id: number) => exitApi.approveRecord(id),
    onSuccess: () => {
      toast({ title: "Exit approved" });
      qc.invalidateQueries({ queryKey: ["exit-records"] });
    },
  });
  const createTask = useMutation({
    mutationFn: () => exitApi.createChecklistItem({ exit_record_id: Number(checklistRecordId), task_name: taskName, assigned_to_role: "HR" }),
    onSuccess: () => {
      toast({ title: "Checklist task added" });
      setTaskName("");
    },
  });

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 rounded-lg border bg-card p-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Exit</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Exit management</h1>
          <p className="mt-1 text-sm text-muted-foreground">Track resignations, approvals, checklist tasks, and final settlement status.</p>
        </div>
        <div className="flex flex-wrap gap-2"><Button variant="outline" asChild><Link to="/hrms/assets?view=clearance">Asset clearance</Link></Button><Button variant="outline" onClick={() => records.refetch()}><RefreshCw className="h-4 w-4" />Refresh</Button></div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
        <div className="space-y-5">
          <Card>
            <CardHeader><CardTitle className="text-base">Initiate exit</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <EmployeeSearchSelect endpoint="/exit/employees" value={employeeId} onChange={setEmployeeId} />
              <div className="space-y-2"><Label>Last working date</Label><Input type="date" value={lastWorkingDate} onChange={(e) => setLastWorkingDate(e.target.value)} /></div>
              <div className="space-y-2"><Label>Reason</Label><Input value={reason} onChange={(e) => setReason(e.target.value)} /></div>
              <Button onClick={() => create.mutate()} disabled={!employeeId || create.isPending}><Plus className="h-4 w-4" />Create exit</Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Checklist task</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <select value={checklistRecordId} onChange={(e) => setChecklistRecordId(e.target.value)} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"><option value="">Select exit record</option>{records.data?.map((r: any) => <option key={r.id} value={r.id}>Record #{r.id} - Employee #{r.employee_id}</option>)}</select>
              <Input value={taskName} onChange={(e) => setTaskName(e.target.value)} placeholder="Collect laptop / revoke access / final settlement" />
              <Button variant="outline" onClick={() => createTask.mutate()} disabled={!checklistRecordId || !taskName}>Add task</Button>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader><CardTitle className="text-base">Exit records</CardTitle><CardDescription>{records.data?.length ?? 0} records</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {records.data?.map((record: any) => (
              <div key={record.id} className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary"><DoorOpen className="h-5 w-5" /></div>
                  <div>
                    <p className="font-medium">Employee #{record.employee_id} â€¢ {record.exit_type || "Exit"}</p>
                    <p className="text-sm text-muted-foreground">LWD {formatDate(record.last_working_date)} â€¢ {record.reason || "No reason"}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={record.status === "Completed" ? "success" : "warning"}>{record.status}</Badge>
                  {record.status === "Initiated" && <Button size="sm" variant="outline" onClick={() => approve.mutate(record.id)}><CheckCircle2 className="h-4 w-4" />Approve</Button>}
                </div>
              </div>
            ))}
            {!records.isLoading && !records.data?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No exit records yet.</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

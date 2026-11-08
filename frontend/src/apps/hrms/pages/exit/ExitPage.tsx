import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import { standardRecordGroups } from "@/shared/data-grid/record-group-fields";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import { NativeSelect } from "@/components/ui/native-select";
import { useState } from "react";
import EmployeeSearchSelect from "../../components/EmployeeSearchSelect";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, DoorOpen, Plus, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, employeeApi, exitApi } from "@/services/api";
import { toast } from "@/hooks/use-toast";
import { usePageTitle } from "@/hooks/use-page-title";
import { formatDate } from "@/lib/utils";
import { verificationError } from "../compliance/verificationRecords";

export default function ExitPage() {
  usePageTitle("Exit Management");
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const selectedEmployee = Number(params.get("employee_id")) || undefined;
  const [employeeId, setEmployeeId] = useState(selectedEmployee ? String(selectedEmployee) : "");
  const [lastWorkingDate, setLastWorkingDate] = useState("");
  const [reason, setReason] = useState("");
  const [exitType, setExitType] = useState("Resignation");
  const [resignationDate, setResignationDate] = useState("");
  const [checklistRecordId, setChecklistRecordId] = useState("");
  const [taskName, setTaskName] = useState("");

  const employees = useQuery({ queryKey: ["exit-employees"], queryFn: () => employeeApi.list({ per_page: 100 }).then((r) => r.data.items) });
  const records = useQuery({ queryKey: ["exit-records", selectedEmployee], queryFn: () => exitApi.records(selectedEmployee).then((r) => r.data) });

  const create = useMutation({
    mutationFn: () => exitApi.createRecord({
      employee_id: Number(employeeId),
      exit_type: exitType,
      resignation_date: resignationDate || undefined,
      last_working_date: lastWorkingDate || undefined,
      reason,
    }),
    onSuccess: () => {
      toast({ title: "Exit record created" });
      setEmployeeId("");
      setReason("");
      qc.invalidateQueries({ queryKey: ["exit-records"] });
    },
    onError: (error) => toast({ title: verificationError(error), variant: "destructive" }),
  });
  const approve = useMutation({
    mutationFn: (id: number) => exitApi.approveRecord(id),
    onSuccess: () => {
      toast({ title: "Exit approved" });
      qc.invalidateQueries({ queryKey: ["exit-records"] });
    },
  });
  const complete = useMutation({
    mutationFn: (id: number) => exitApi.completeRecord(id),
    onSuccess: () => {
      toast({ title: "Exit completed; employee file retained" });
      for (const key of ["exit-records", "employee", "bgv-register", "bgv-employee-file", "hr-lifecycle-checklist"]) qc.invalidateQueries({queryKey: [key]});
    },
    onError: (error) => toast({title: verificationError(error), variant: "destructive"}),
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
        <div className="flex flex-wrap gap-2"><Button variant="outline" asChild><Link to="/hrms/assets?view=clearance">Asset clearance</Link></Button><Button variant="outline" asChild><Link to="/hrms/background-verification?population=former">Former employee files</Link></Button><Button variant="outline" onClick={() => records.refetch()}><RefreshCw className="h-4 w-4" />Refresh</Button></div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
        <div className="space-y-5">
          <SmartCreateSection title="Create employee exit" size="standard"><Card>
            <CardHeader><CardTitle className="text-base">Initiate exit</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <EmployeeSearchSelect endpoint="/exit/employees" value={employeeId} onChange={setEmployeeId} />
              {selectedEmployee && <p className="text-sm">Preparing records for the employee selected from their file.</p>}
              <label className="block text-sm">Exit type<NativeSelect aria-label="Exit type" className="mt-1 h-10 w-full rounded border bg-background px-2" value={exitType} onChange={e => setExitType(e.target.value)}>{["Resignation", "Termination", "Retirement", "Absconding"].map(type => <option key={type}>{type}</option>)}</NativeSelect></label>
              <label className="block text-sm">Resignation / notice date<Input type="date" value={resignationDate} onChange={e => setResignationDate(e.target.value)}/></label>
              <div className="space-y-2"><Label>Last working date</Label><Input type="date" value={lastWorkingDate} onChange={(e) => setLastWorkingDate(e.target.value)} /></div>
              <div className="space-y-2"><Label>Reason</Label><Input value={reason} onChange={(e) => setReason(e.target.value)} /></div>
              <Button onClick={() => create.mutate()} disabled={!employeeId || create.isPending}><Plus className="h-4 w-4" />Create exit</Button>
            </CardContent>
          </Card></SmartCreateSection>

          <SmartCreateSection title="Create clearance task" size="standard"><Card>
            <CardHeader><CardTitle className="text-base">Checklist task</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <NativeSelect loading={records.isFetching} error={records.isError} value={checklistRecordId} onChange={(e) => setChecklistRecordId(e.target.value)} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"><option value="">Select exit record</option>{records.data?.map((r: any) => <option key={r.id} value={r.id}>Record #{r.id} - Employee #{r.employee_id}</option>)}</NativeSelect>
              <Input value={taskName} onChange={(e) => setTaskName(e.target.value)} placeholder="Collect laptop / revoke access / final settlement" />
              <Button variant="outline" onClick={() => createTask.mutate()} disabled={!checklistRecordId || !taskName}>Add task</Button>
            </CardContent>
          </Card></SmartCreateSection>
        </div>

        <Card>
          <CardHeader><CardTitle className="text-base">Exit records</CardTitle><CardDescription>{records.data?.length ?? 0} records</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {<GroupedRecords scope="apps/hrms/pages/exit/ExitPage:records-1" items={(records.data) || []} fields={standardRecordGroups((records.data) || [])} gridClassName="space-y-3" renderItem={(record: any) => (
              <div key={record.id} className="flex flex-col gap-3 rounded-lg border p-4">
                <div className="flex gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary"><DoorOpen className="h-5 w-5" /></div>
                  <div>
                    <p className="font-medium">Employee #{record.employee_id} • {record.exit_type || "Exit"}</p>
                    <p className="text-sm text-muted-foreground">LWD {formatDate(record.last_working_date)} • {record.reason || "No reason"}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={record.status === "Completed" ? "success" : "warning"}>{record.status}</Badge>
                  {record.status === "Initiated" && <Button size="sm" variant="outline" onClick={() => approve.mutate(record.id)}><CheckCircle2 className="h-4 w-4" />Approve</Button>}
                  {record.status === "In Progress" && <Button size="sm" variant="outline" disabled={complete.isPending} onClick={() => complete.mutate(record.id)}>Complete exit</Button>}
                  <Button size="sm" variant="ghost" asChild><Link to={`/hrms/employees/${record.employee_id}?tab=verification`}>Open employee file</Link></Button>
                </div>
                <ExitChecklist recordId={record.id} closed={["Completed", "Cancelled"].includes(record.status)}/>
              </div>
            )}/>}
            {!records.isLoading && !records.data?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No exit records yet.</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ExitChecklist({recordId, closed}: {recordId: number; closed: boolean}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const tasks = useQuery({queryKey: ["exit-checklist", recordId], enabled: open, queryFn: () => api.get<Array<{id: number; task_name: string; assigned_to_role: string | null; is_completed: boolean; remarks: string | null}>>(`/exit/records/${recordId}/checklist`).then(r => r.data)});
  const complete = useMutation({mutationFn: ({id, remarks}: {id: number; remarks: string}) => exitApi.completeChecklistItem(id, remarks), onSuccess: () => {
    qc.invalidateQueries({queryKey: ["exit-checklist", recordId]}); qc.invalidateQueries({queryKey: ["bgv-employee-file"]}); qc.invalidateQueries({queryKey: ["hr-lifecycle-checklist"]});
  }});
  return <details open={open} onToggle={e => setOpen(e.currentTarget.open)}><summary className="cursor-pointer text-sm font-medium">Exit clearance checklist</summary>
    {tasks.isPending && <p className="mt-2 text-sm">Loading checklist…</p>}{tasks.isError && <p role="alert" className="mt-2 text-sm">Checklist could not load. <button className="underline" onClick={() => tasks.refetch()}>Retry</button></p>}
    {complete.isError && <p role="alert" className="mt-2 text-sm text-destructive">{verificationError(complete.error)}</p>}
    <ul className="mt-3 space-y-3">{tasks.data?.map(task => <li key={task.id} className="space-y-2 border-b pb-3 text-sm"><p className="font-medium">{task.is_completed ? "Complete" : "Pending"}: {task.task_name} · {task.assigned_to_role}</p>{task.remarks && <p>{task.remarks}</p>}{!task.is_completed && !closed && <form className="flex flex-wrap gap-2" onSubmit={e => {e.preventDefault();complete.mutate({id: task.id, remarks: notes[task.id] || ""});}}><Input aria-label={`Evidence for ${task.task_name}`} placeholder="Clearance evidence / handover notes" value={notes[task.id] || ""} onChange={e => setNotes({...notes, [task.id]: e.target.value})} className="min-w-0 flex-1" required minLength={3}/><Button size="sm" variant="outline" disabled={complete.isPending || (notes[task.id] || "").trim().length < 3} type="submit">Record clearance</Button></form>}</li>)}</ul>
  </details>;
}

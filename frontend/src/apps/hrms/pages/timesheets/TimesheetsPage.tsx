import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import RecordMaintenance from "@/components/RecordMaintenance";
import GridTable from "@/shared/data-grid/GridTable";
import { NativeSelect } from "@/components/ui/native-select";
import { recordPreviewProps } from "@/components/RecordQuickPreview";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock3, FolderKanban, Plus, Send, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { timesheetsApi } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { getRoleKey } from "@/lib/roles";
import { usePageTitle } from "@/hooks/use-page-title";
import { toast } from "@/hooks/use-toast";

type Project = {
  id: number;
  code: string;
  name: string;
  client_name?: string | null;
  status: string;
  is_billable: boolean;
};

type TimesheetEntry = {
  id: number;
  work_date: string;
  hours: string | number;
  is_billable: boolean;
  task_name?: string | null;
};

type Timesheet = {
  id: number;
  project_id: number;
  period_start: string;
  period_end: string;
  status: string;
  total_hours: string | number;
  billable_hours: string | number;
  non_billable_hours: string | number;
  entries: TimesheetEntry[];
};

const today = new Date();
const weekStart = new Date(today);
weekStart.setDate(today.getDate() - (today.getDay() + 6) % 7);
const weekEnd = new Date(weekStart);
weekEnd.setDate(weekStart.getDate() + 6);

function isoDate(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

function statusTone(status: string) {
  if (status === "Approved") return "bg-green-100 text-green-700 border-green-200";
  if (status === "Rejected") return "bg-red-100 text-red-700 border-red-200";
  if (status === "Submitted") return "bg-amber-100 text-amber-700 border-amber-200";
  return "bg-slate-100 text-slate-700 border-slate-200";
}

export default function TimesheetsPage() {
  usePageTitle("Timesheets");
  const qc = useQueryClient();
  const { user } = useAuthStore();
  const roleKey = getRoleKey(user?.role, user?.is_superuser);
  const grant=user?.access?.grants.hrms,managed=!!user?.access?.managed;
  const granted=(permission:string,action:string)=>!!user?.is_superuser||!!(grant?.enabled&&grant.permissions.includes(permission)&&grant.actions.includes(action));
  const canManageProjects=managed?granted("timesheet_manage","create"):roleKey==="admin"||roleKey==="hr";
  const canApprove=managed?granted("timesheet_approve","approve"):roleKey==="admin"||roleKey==="hr"||roleKey==="manager";
  const canCreateSheet=!!user?.employee_id&&(!managed||granted("timesheet_view","create"));
  const [selectedSheetId, setSelectedSheetId] = useState<number | null>(null);
  const [projectForm, setProjectForm] = useState({ code: "", name: "", client_name: "" });
  const [sheetForm, setSheetForm] = useState({
    project_id: "",
    period_start: isoDate(weekStart),
    period_end: isoDate(weekEnd),
  });
  const [entryForm, setEntryForm] = useState({
    work_date: isoDate(today),
    hours: "8",
    is_billable: true,
    task_name: "",
  });

  const { data: projects = [] } = useQuery({
    queryKey: ["timesheet-projects"],
    queryFn: () => timesheetsApi.projects({ status: "Active" }).then((r) => r.data as Project[]),
  });

  const { data: sheets = [] } = useQuery({
    queryKey: ["timesheets"],
    queryFn: () => timesheetsApi.list().then((r) => r.data as Timesheet[]),
  });

  const projectById = useMemo(
    () => new Map((projects as Project[]).map((project) => [project.id, project])),
    [projects],
  );
  const selectedSheet = useMemo(
    () => selectedSheetId === null ? (sheets as Timesheet[])[0] : (sheets as Timesheet[]).find((sheet) => sheet.id === selectedSheetId),
    [sheets, selectedSheetId],
  );

  const createProject = useMutation({
    mutationFn: () => timesheetsApi.createProject({
      ...projectForm,
      code: projectForm.code.trim(),
      name: projectForm.name.trim(),
      client_name: projectForm.client_name.trim() || undefined,
    }),
    onSuccess: () => {
      toast({ title: "Project created" });
      setProjectForm({ code: "", name: "", client_name: "" });
      qc.invalidateQueries({ queryKey: ["timesheet-projects"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Project save failed";
      toast({ title: "Error", description: msg, variant: "destructive" });
    },
  });

  const createSheet = useMutation({
    mutationFn: () => timesheetsApi.create({
      project_id: Number(sheetForm.project_id),
      period_start: sheetForm.period_start,
      period_end: sheetForm.period_end,
    }),
    onSuccess: (response) => {
      toast({ title: "Timesheet created" });
      setSelectedSheetId(response.data.id);
      qc.invalidateQueries({ queryKey: ["timesheets"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Timesheet save failed";
      toast({ title: "Error", description: msg, variant: "destructive" });
    },
  });

  const addEntry = useMutation({
    mutationFn: () => timesheetsApi.addEntry(selectedSheet!.id, {
      work_date: entryForm.work_date,
      hours: entryForm.hours,
      is_billable: entryForm.is_billable,
      task_name: entryForm.task_name.trim() || undefined,
    }),
    onSuccess: () => {
      toast({ title: "Entry added" });
      setEntryForm((current) => ({ ...current, task_name: "" }));
      qc.invalidateQueries({ queryKey: ["timesheets"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Entry save failed";
      toast({ title: "Error", description: msg, variant: "destructive" });
    },
  });

  const submitSheet = useMutation({
    mutationFn: (id: number) => timesheetsApi.submit(id),
    onSuccess: () => {
      toast({ title: "Timesheet submitted" });
      qc.invalidateQueries({ queryKey: ["timesheets"] });
    },
    onError:()=>toast({title:"Could not submit timesheet",description:"Your entries are retained. Check the status and try again.",variant:"destructive"}),
  });

  const reviewSheet = useMutation({
    mutationFn: ({ id, status }: { id: number; status: "Approved" | "Rejected" }) =>
      timesheetsApi.review(id, { status }),
    onSuccess: (_, variables) => {
      toast({ title: `Timesheet ${variables.status.toLowerCase()}` });
      qc.invalidateQueries({ queryKey: ["timesheets"] });
    },
    onError:()=>toast({title:"Could not review timesheet",description:"The previous status is retained. Refresh and retry.",variant:"destructive"}),
  });

  const totals = useMemo(() => {
    const all = sheets as Timesheet[];
    return {
      total: all.reduce((sum, sheet) => sum + Number(sheet.total_hours || 0), 0),
      billable: all.reduce((sum, sheet) => sum + Number(sheet.billable_hours || 0), 0),
      submitted: all.filter((sheet) => sheet.status === "Submitted").length,
    };
  }, [sheets]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="page-title">Timesheets</h1>
          <p className="page-description">Project time capture, approval, and billable utilization for services teams.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground">Recorded hours</p>
            <p className="text-2xl font-bold mt-1">{totals.total.toFixed(1)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground">Billable hours</p>
            <p className="text-2xl font-bold mt-1">{totals.billable.toFixed(1)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground">Awaiting approval</p>
            <p className="text-2xl font-bold mt-1">{totals.submitted}</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[360px_minmax(0,1fr)] gap-6">
        <div className="space-y-4">
          {canManageProjects && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <FolderKanban className="h-4 w-4" />
                  Project Master
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <SmartCreateSection title="Create timesheet project" size="standard"><div className="space-y-4"><div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label>Code</Label>
                    <Input aria-label="Timesheet project code" value={projectForm.code} onChange={(e) => setProjectForm({ ...projectForm, code: e.target.value })} />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Client</Label>
                    <Input aria-label="Timesheet project client" value={projectForm.client_name} onChange={(e) => setProjectForm({ ...projectForm, client_name: e.target.value })} />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label>Name</Label>
                  <Input aria-label="Timesheet project name" value={projectForm.name} onChange={(e) => setProjectForm({ ...projectForm, name: e.target.value })} />
                </div>
                <Button
                  className="w-full"
                  onClick={() => createProject.mutate()}
                  disabled={!projectForm.code || !projectForm.name || createProject.isPending}
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Add Project
                </Button></div></SmartCreateSection><details><summary>Manage timesheet projects</summary>{projects.map(project=><div key={project.id} className="flex items-center justify-between gap-2 border-t py-2"><span>{project.name}</span><RecordMaintenance record={project as unknown as Record<string,unknown>} name={project.name} endpoint={`/timesheets/projects/${project.id}`} fields={[{key:"code",label:"Project code",required:true},{key:"name",label:"Project name",required:true}]} queryKeys={["timesheet-projects"]} canEdit={canManageProjects} canDelete={canManageProjects} mergeRecord/></div>)}</details>
              </CardContent>
            </Card>
          )}

          {canCreateSheet && (
            <SmartCreateSection title="Create timesheet" size="standard"><Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Clock3 className="h-4 w-4" />
                  New Timesheet
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-1.5">
                  <Label>Project</Label>
                  <NativeSelect
                    aria-label="Timesheet project" value={sheetForm.project_id}
                    onChange={(e) => setSheetForm({ ...sheetForm, project_id: e.target.value })}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    <option value="">Select project</option>
                    {(projects as Project[]).map((project) => (
                      <option key={project.id} value={project.id}>{project.code} - {project.name}</option>
                    ))}
                  </NativeSelect>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label>Start</Label>
                    <Input aria-label="Timesheet period start" type="date" value={sheetForm.period_start} onChange={(e) => setSheetForm({ ...sheetForm, period_start: e.target.value })} />
                  </div>
                  <div className="space-y-1.5">
                    <Label>End</Label>
                    <Input aria-label="Timesheet period end" type="date" value={sheetForm.period_end} onChange={(e) => setSheetForm({ ...sheetForm, period_end: e.target.value })} />
                  </div>
                </div>
                <Button
                  className="w-full"
                  onClick={() => createSheet.mutate()}
                  disabled={!sheetForm.project_id || createSheet.isPending}
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Create Timesheet
                </Button>
              </CardContent>
            </Card></SmartCreateSection>
          )}
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Timesheet Register</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <GridTable gridId="apps/hrms/pages/timesheets/TimesheetsPage:table-1" className="w-full text-sm">
                  <thead className="border-b bg-muted/50">
                    <tr>
                      {["Project", "Period", "Total", "Billable", "Status", "Actions"].map((heading) => (
                        <th key={heading} className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wide">
                          {heading}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(sheets as Timesheet[]).length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">No timesheets found</td>
                      </tr>
                    ) : (
                      (sheets as Timesheet[]).map((sheet) => {
                        const project = projectById.get(sheet.project_id);
                        return (
                          <tr {...recordPreviewProps(sheet)} key={sheet.id} className="border-b hover:bg-muted/30">
                            <td className="px-4 py-3">
                              <button className="font-medium text-left hover:text-primary" onClick={() => setSelectedSheetId(sheet.id)}>
                                {project?.name || `Project #${sheet.project_id}`}
                              </button>
                              <p className="text-xs text-muted-foreground">{project?.client_name || project?.code}</p>
                            </td>
                            <td className="px-4 py-3 text-muted-foreground">{sheet.period_start} to {sheet.period_end}</td>
                            <td className="px-4 py-3">{Number(sheet.total_hours || 0).toFixed(1)}</td>
                            <td className="px-4 py-3">{Number(sheet.billable_hours || 0).toFixed(1)}</td>
                            <td className="px-4 py-3">
                              <Badge variant="outline" className={statusTone(sheet.status)}>{sheet.status}</Badge>
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex flex-wrap gap-2">
                                {sheet.status === "Draft" && canCreateSheet && (
                                  <Button size="sm" variant="outline" className="h-8" onClick={() => submitSheet.mutate(sheet.id)}>
                                    <Send className="h-3.5 w-3.5 mr-1" />
                                    Submit
                                  </Button>
                                )}
                                {sheet.status === "Submitted" && canApprove && (
                                  <>
                                    <Button size="sm" className="h-8 bg-green-600 hover:bg-green-700 text-white" onClick={() => reviewSheet.mutate({ id: sheet.id, status: "Approved" })}>
                                      <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                                      Approve
                                    </Button>
                                    <Button size="sm" variant="outline" className="h-8 text-red-600 border-red-200" onClick={() => reviewSheet.mutate({ id: sheet.id, status: "Rejected" })}>
                                      <XCircle className="h-3.5 w-3.5 mr-1" />
                                      Reject
                                    </Button>
                                  </>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </GridTable>
              </div>
            </CardContent>
          </Card>

          {selectedSheet && selectedSheet.status === "Draft" && canCreateSheet && (
            <SmartCreateSection title={<>Add Work Entry</>} size="standard"><Card>
              <CardHeader>
                <CardTitle className="text-base">Add Work Entry</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-1 md:grid-cols-[160px_120px_140px_minmax(0,1fr)_auto] gap-3 items-end">
                <div className="space-y-1.5">
                  <Label>Date</Label>
                  <Input type="date" value={entryForm.work_date} onChange={(e) => setEntryForm({ ...entryForm, work_date: e.target.value })} />
                </div>
                <div className="space-y-1.5">
                  <Label>Hours</Label>
                  <Input aria-label="Timesheet entry hours" type="number" step="0.25" min="0.25" max="24" value={entryForm.hours} onChange={(e) => setEntryForm({ ...entryForm, hours: e.target.value })} />
                </div>
                <label className="flex h-10 items-center gap-2 rounded-md border px-3 text-sm">
                  <input type="checkbox" checked={entryForm.is_billable} onChange={(e) => setEntryForm({ ...entryForm, is_billable: e.target.checked })} />
                  Billable
                </label>
                <div className="space-y-1.5">
                  <Label>Task</Label>
                  <Input aria-label="Timesheet work description" value={entryForm.task_name} onChange={(e) => setEntryForm({ ...entryForm, task_name: e.target.value })} />
                </div>
                <Button onClick={() => addEntry.mutate()} disabled={!selectedSheet || addEntry.isPending}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add
                </Button>
              </CardContent>
            </Card></SmartCreateSection>
          )}

          {selectedSheet && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Entries</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <GridTable gridId="apps/hrms/pages/timesheets/TimesheetsPage:table-2" className="w-full text-sm">
                    <thead className="border-b bg-muted/50">
                      <tr>
                        {["Date", "Task", "Hours", "Type"].map((heading) => (
                          <th key={heading} className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wide">
                            {heading}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {selectedSheet.entries.length === 0 ? (
                        <tr>
                          <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">No entries added</td>
                        </tr>
                      ) : (
                        selectedSheet.entries.map((entry) => (
                          <tr {...recordPreviewProps(entry)} key={entry.id} className="border-b">
                            <td className="px-4 py-3">{entry.work_date}</td>
                            <td className="px-4 py-3">{entry.task_name || "General work"}</td>
                            <td className="px-4 py-3">{Number(entry.hours).toFixed(1)}</td>
                            <td className="px-4 py-3">{entry.is_billable ? "Billable" : "Non-billable"}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </GridTable>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

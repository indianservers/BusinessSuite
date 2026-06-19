import type React from "react";
import { FormEvent, useEffect, useState } from "react";
import { Activity, AlertTriangle, BarChart3, CheckCircle2, Flame, Gauge, Play, RotateCcw, TrendingUp } from "lucide-react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatDate, statusColor } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";
import { projectsAPI, reportsAPI, sprintsAPI, tasksAPI } from "../services/api";
import type { PMSProject, PMSSprint, PMSSprintActionItem, PMSTaskListItem, ProjectVelocity, SprintBurndown, WorkloadResponse } from "../types";

export default function SprintsPage() {
  const [projects, setProjects] = useState<PMSProject[]>([]);
  const [projectId, setProjectId] = useState("");
  const [sprints, setSprints] = useState<PMSSprint[]>([]);
  const [name, setName] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [goal, setGoal] = useState("Planned delivery increment");
  const [capacityHours, setCapacityHours] = useState("40");
  const [burndown, setBurndown] = useState<SprintBurndown | null>(null);
  const [velocity, setVelocity] = useState<ProjectVelocity | null>(null);
  const [workload, setWorkload] = useState<WorkloadResponse | null>(null);
  const [backlogTasks, setBacklogTasks] = useState<PMSTaskListItem[]>([]);
  const [completeTarget, setCompleteTarget] = useState<PMSSprint | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionSprintId, setActionSprintId] = useState<number | null>(null);
  const [creatingSprint, setCreatingSprint] = useState(false);
  const [completeDraft, setCompleteDraft] = useState({
    incompleteAction: "move_to_next_sprint",
    carryForwardSprintId: "",
    reviewNotes: "",
    retrospectiveNotes: "",
    whatWentWell: "",
    whatDidNotGoWell: "",
    outcome: "",
    createActionItemTasks: false,
    actionItems: [{ title: "", due_date: "" }] as Array<Partial<PMSSprintActionItem> & { title: string; due_date?: string }>,
  });

  useEffect(() => {
    projectsAPI.list().then((items) => {
      setProjects(items);
      const firstId = String(items[0]?.id || "");
      setProjectId(firstId);
      if (firstId) loadProject(Number(firstId));
    }).catch((err) => setError(apiError(err, "Unable to load projects.")));
  }, []);

  const loadProject = async (id: number) => {
    try {
      setError(null);
      const [sprintItems, velocityData, workloadData, taskData] = await Promise.all([
        sprintsAPI.list(id),
        sprintsAPI.velocity(id).catch(() => null),
        reportsAPI.workload(id, { group_by: "sprint" }).catch(() => null),
        tasksAPI.listAll({ projectId: id, pageSize: 200, sortBy: "updatedDate", sortOrder: "desc" }).catch(() => null),
      ]);
      setSprints(sprintItems);
      setVelocity(velocityData);
      setWorkload(workloadData);
      setBacklogTasks(taskData?.items || []);
      if (sprintItems[0]) {
        sprintsAPI.burndown(sprintItems[0].id).then(setBurndown).catch(() => setBurndown(null));
      } else {
        setBurndown(null);
      }
    } catch (err: any) {
      setError(apiError(err, "Unable to load sprint planning data."));
    }
  };

  const switchProject = (value: string) => {
    setProjectId(value);
    if (value) loadProject(Number(value));
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!projectId || !name || !startDate || !endDate) return;
    try {
      setCreatingSprint(true);
      setError(null);
      const sprint = await sprintsAPI.create(Number(projectId), {
        name,
        goal,
        status: "Planned",
        start_date: startDate,
        end_date: endDate,
        capacity_hours: Number(capacityHours || 0),
      } as any);
      setSprints((items) => [sprint, ...items]);
      setName("");
      toast({ title: "Sprint created" });
    } catch (err: any) {
      setError(apiError(err, "Could not create sprint."));
    } finally {
      setCreatingSprint(false);
    }
  };

  const refreshSprint = (updated: PMSSprint) => {
    setSprints((items) => items.map((item) => item.id === updated.id ? updated : item));
    sprintsAPI.burndown(updated.id).then(setBurndown).catch(() => setBurndown(null));
    if (projectId) sprintsAPI.velocity(Number(projectId)).then(setVelocity).catch(() => null);
  };

  const startSprint = async (sprint: PMSSprint) => {
    try {
      setActionSprintId(sprint.id);
      setError(null);
      refreshSprint(await sprintsAPI.start(sprint.id));
      toast({ title: "Sprint started" });
    } catch (err: any) {
      setError(apiError(err, "Could not start sprint."));
    } finally {
      setActionSprintId(null);
    }
  };

  const openSprintReview = async (sprint: PMSSprint) => {
    const carryForward = sprints.find((item) => item.id !== sprint.id && item.status === "Planned")?.id;
    setCompleteTarget(sprint);
    setCompleteDraft({
      incompleteAction: carryForward ? "move_to_next_sprint" : "keep_in_sprint",
      carryForwardSprintId: carryForward ? String(carryForward) : "",
      reviewNotes: sprint.review_notes || "",
      retrospectiveNotes: sprint.retrospective_notes || "",
      whatWentWell: sprint.what_went_well || "",
      whatDidNotGoWell: sprint.what_did_not_go_well || "",
      outcome: sprint.outcome || "",
      createActionItemTasks: false,
      actionItems: [{ title: "", due_date: "" }],
    });
    setReviewLoading(true);
    try {
      const review = await sprintsAPI.review(sprint.id);
      setCompleteDraft((current) => ({
        ...current,
        reviewNotes: review.sprint.review_notes || current.reviewNotes,
        retrospectiveNotes: review.sprint.retrospective_notes || current.retrospectiveNotes,
        whatWentWell: review.sprint.what_went_well || current.whatWentWell,
        whatDidNotGoWell: review.sprint.what_did_not_go_well || current.whatDidNotGoWell,
        outcome: review.sprint.outcome || current.outcome,
        actionItems: review.action_items.length ? review.action_items.map((item) => ({ title: item.title, due_date: item.due_date || "", owner_user_id: item.owner_user_id || undefined, status: item.status })) : current.actionItems,
      }));
    } finally {
      setReviewLoading(false);
    }
  };

  const saveSprintReview = async () => {
    if (!completeTarget) return;
    const actionItems = completeDraft.actionItems.filter((item) => item.title.trim());
    const payload = {
      incomplete_action: completeDraft.incompleteAction as "move_to_backlog" | "move_to_next_sprint" | "keep_in_sprint",
      carry_forward_sprint_id: completeDraft.carryForwardSprintId ? Number(completeDraft.carryForwardSprintId) : undefined,
      review_notes: completeDraft.reviewNotes,
      retrospective_notes: completeDraft.retrospectiveNotes,
      what_went_well: completeDraft.whatWentWell,
      what_did_not_go_well: completeDraft.whatDidNotGoWell,
      outcome: completeDraft.outcome,
      create_action_item_tasks: completeDraft.createActionItemTasks,
      action_items: actionItems,
    };
    try {
      setActionSprintId(completeTarget.id);
      setError(null);
      const review = completeTarget.status === "Completed"
        ? await sprintsAPI.updateReview(completeTarget.id, payload)
        : { sprint: await sprintsAPI.complete(completeTarget.id, payload) };
      refreshSprint(review.sprint);
      setCompleteTarget(null);
      toast({ title: completeTarget.status === "Completed" ? "Sprint review saved" : "Sprint completed" });
    } catch (err: any) {
      setError(apiError(err, "Could not save sprint review."));
    } finally {
      setActionSprintId(null);
    }
  };

  const completeTasks = completeTarget ? backlogTasks.filter((task) => task.sprint_id === completeTarget.id && ["Done", "Completed", "Closed", "Resolved"].includes(task.status)) : [];
  const incompleteTasks = completeTarget ? backlogTasks.filter((task) => task.sprint_id === completeTarget.id && !["Done", "Completed", "Closed", "Resolved"].includes(task.status)) : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Sprints</h1>
        <p className="page-description">Plan agile delivery windows, commitment snapshots, carry-forward scope, capacity, burndown, and velocity.</p>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Metric icon={Activity} label="Sprints" value={sprints.length} />
        <Metric icon={Play} label="Active" value={sprints.filter((sprint) => sprint.status === "Active").length} />
        <Metric icon={TrendingUp} label="Avg velocity" value={`${Math.round(velocity?.average_velocity_points || 0)} pts`} />
        <Metric icon={AlertTriangle} label="Over capacity" value={workload?.items.filter((item) => (item.load_percent || 0) > 100).length || 0} tone="text-red-600" />
      </div>
      <Card>
        <CardHeader><CardTitle>Create sprint</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="grid gap-4 md:grid-cols-[1fr_1fr_1fr_8rem_11rem_11rem_auto] md:items-end">
            <Field label="Project"><select value={projectId} onChange={(event) => switchProject(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></Field>
            <Field label="Sprint name"><Input value={name} onChange={(event) => setName(event.target.value)} /></Field>
            <Field label="Goal"><Input value={goal} onChange={(event) => setGoal(event.target.value)} /></Field>
            <Field label="Capacity"><Input type="number" value={capacityHours} onChange={(event) => setCapacityHours(event.target.value)} /></Field>
            <Field label="Start"><Input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></Field>
            <Field label="End"><Input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></Field>
            <Button type="submit" disabled={creatingSprint}>{creatingSprint ? "Creating..." : "Create"}</Button>
          </form>
        </CardContent>
      </Card>
      {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      <div className="grid gap-4 xl:grid-cols-[1.4fr_0.8fr]">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><BarChart3 className="h-5 w-5" />Burndown</CardTitle></CardHeader>
          <CardContent className="h-72">
            {burndown?.points.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={burndown.points}>
                  <XAxis dataKey="date" tickLine={false} axisLine={false} />
                  <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
                  <Tooltip />
                  <Line type="monotone" dataKey="ideal_remaining_points" stroke="#64748b" strokeDasharray="4 4" dot={false} />
                  <Line type="monotone" dataKey="actual_remaining_points" stroke="hsl(var(--primary))" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            ) : <EmptyState text="Start a sprint to capture burndown." />}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Gauge className="h-5 w-5" />Capacity</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {(workload?.items || []).slice(0, 5).map((item) => (
              <div key={`${item.sprint_id || "none"}`} className="rounded-md border p-3">
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className="font-medium">Sprint {item.sprint_id || "Unassigned"}</span>
                  <Badge variant={(item.load_percent || 0) > 100 ? "destructive" : "outline"}>{Math.round(item.load_percent || 0)}%</Badge>
                </div>
                <div className="mt-2 h-2 rounded-full bg-muted"><div className="h-2 rounded-full bg-primary" style={{ width: `${Math.min(item.load_percent || 0, 100)}%` }} /></div>
                <p className="mt-2 text-xs text-muted-foreground">{item.task_count} tasks / {item.story_points} pts / {item.estimated_hours}h</p>
              </div>
            ))}
            {!workload?.items.length ? <EmptyState text="No open sprint workload yet." /> : null}
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader><CardTitle>Sprint backlog</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {backlogTasks.slice(0, 12).map((task) => (
            <div key={task.id} className="grid gap-2 rounded-md border p-3 text-sm md:grid-cols-[8rem_minmax(0,1fr)_10rem_6rem_12rem] md:items-center">
              <span className="font-semibold text-muted-foreground">{task.task_key}</span>
              <span className="min-w-0 truncate font-medium">{task.title}</span>
              <Badge className={statusColor(task.status)}>{task.status}</Badge>
              <span>{task.story_points ?? 0} pts</span>
              <div className="flex flex-wrap gap-1">
                {(task.tags || []).slice(0, 3).map((tag) => {
                  const label = typeof tag === "string" ? tag : tag.name;
                  return <Badge key={label} variant="outline" className="h-5 rounded px-1.5 text-[11px]">{label}</Badge>;
                })}
                {!task.tags?.length ? <span className="text-xs text-muted-foreground">No tags</span> : null}
              </div>
            </div>
          ))}
          {!backlogTasks.length ? <EmptyState text="No tasks found for this project backlog." /> : null}
        </CardContent>
      </Card>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {sprints.map((sprint) => (
          <Card key={sprint.id}>
            <CardContent className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3"><div className="rounded-lg bg-primary/10 p-2 text-primary"><Activity className="h-5 w-5" /></div><div><h2 className="font-semibold">{sprint.name}</h2><p className="text-sm text-muted-foreground">{formatDate(sprint.start_date)} - {formatDate(sprint.end_date)}</p></div></div>
                <Badge className={statusColor(sprint.status)}>{sprint.status}</Badge>
              </div>
              <p className="mt-4 text-sm text-muted-foreground">{sprint.goal || "No sprint goal defined."}</p>
              <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
                <Fact icon={Flame} label="Committed" value={`${sprint.committed_story_points || 0} pts`} />
                <Fact icon={CheckCircle2} label="Completed" value={`${sprint.completed_story_points || 0} pts`} />
                <Fact icon={RotateCcw} label="Carry-over" value={sprint.carry_forward_task_count || 0} />
                <Fact icon={AlertTriangle} label="Scope changes" value={sprint.scope_change_count || 0} />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button size="sm" onClick={() => startSprint(sprint)} disabled={actionSprintId === sprint.id || sprint.status === "Active" || sprint.status === "Completed"}><Play className="h-4 w-4" />Start</Button>
                <Button size="sm" variant="outline" onClick={() => openSprintReview(sprint)}><CheckCircle2 className="h-4 w-4" />{sprint.status === "Completed" ? "Review" : "Complete"}</Button>
                <Button size="sm" variant="ghost" onClick={() => sprintsAPI.burndown(sprint.id).then(setBurndown)}><BarChart3 className="h-4 w-4" />Burndown</Button>
              </div>
              {(sprint.outcome || sprint.review_notes || sprint.retrospective_notes) ? (
                <div className="mt-4 rounded-md border bg-muted/30 p-3 text-sm">
                  <p className="font-medium">Review outcome</p>
                  <p className="mt-1 line-clamp-2 text-muted-foreground">{sprint.outcome || sprint.review_notes || sprint.retrospective_notes}</p>
                </div>
              ) : null}
            </CardContent>
          </Card>
        ))}
        {!sprints.length ? <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">Create your first sprint to unlock lifecycle controls.</div> : null}
      </div>
      {completeTarget ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-lg bg-background shadow-xl">
            <div className="border-b p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold">{completeTarget.status === "Completed" ? "Sprint review" : "Complete sprint"}: {completeTarget.name}</h2>
                  <p className="text-sm text-muted-foreground">Capture review outcomes, retrospective notes, and follow-up action items.</p>
                </div>
                <Button variant="ghost" onClick={() => setCompleteTarget(null)}>Close</Button>
              </div>
            </div>
            <div className="grid gap-5 p-5 lg:grid-cols-[1fr_1.1fr]">
              <div className="space-y-4">
                <TaskSummary title="Completed tasks" tasks={completeTasks} empty="No completed tasks in this sprint." />
                <TaskSummary title="Incomplete tasks" tasks={incompleteTasks} empty="No incomplete tasks." />
                {completeTarget.status !== "Completed" ? (
                  <Field label="Incomplete task handling">
                    <select value={completeDraft.incompleteAction} onChange={(event) => setCompleteDraft((draft) => ({ ...draft, incompleteAction: event.target.value }))} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                      <option value="move_to_backlog">Move to backlog</option>
                      <option value="move_to_next_sprint">Move to next sprint</option>
                      <option value="keep_in_sprint">Keep in current sprint</option>
                    </select>
                  </Field>
                ) : null}
                {completeDraft.incompleteAction === "move_to_next_sprint" && completeTarget.status !== "Completed" ? (
                  <Field label="Next sprint">
                    <select value={completeDraft.carryForwardSprintId} onChange={(event) => setCompleteDraft((draft) => ({ ...draft, carryForwardSprintId: event.target.value }))} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                      <option value="">Select sprint</option>
                      {sprints.filter((sprint) => sprint.id !== completeTarget.id && sprint.status === "Planned").map((sprint) => <option key={sprint.id} value={sprint.id}>{sprint.name}</option>)}
                    </select>
                  </Field>
                ) : null}
              </div>
              <div className="space-y-4">
                {reviewLoading ? <div className="rounded-md border p-3 text-sm text-muted-foreground">Loading saved review notes...</div> : null}
                <TextareaField label="Sprint outcome" value={completeDraft.outcome} onChange={(value) => setCompleteDraft((draft) => ({ ...draft, outcome: value }))} />
                <TextareaField label="Review notes" value={completeDraft.reviewNotes} onChange={(value) => setCompleteDraft((draft) => ({ ...draft, reviewNotes: value }))} />
                <TextareaField label="What went well" value={completeDraft.whatWentWell} onChange={(value) => setCompleteDraft((draft) => ({ ...draft, whatWentWell: value }))} />
                <TextareaField label="What did not go well" value={completeDraft.whatDidNotGoWell} onChange={(value) => setCompleteDraft((draft) => ({ ...draft, whatDidNotGoWell: value }))} />
                <TextareaField label="Retrospective notes" value={completeDraft.retrospectiveNotes} onChange={(value) => setCompleteDraft((draft) => ({ ...draft, retrospectiveNotes: value }))} />
                <div className="space-y-2">
                  <Label>Action items</Label>
                  {completeDraft.actionItems.map((item, index) => (
                    <div key={index} className="grid gap-2 md:grid-cols-[1fr_10rem_auto]">
                      <Input placeholder="Follow-up action" value={item.title} onChange={(event) => setCompleteDraft((draft) => ({ ...draft, actionItems: draft.actionItems.map((current, itemIndex) => itemIndex === index ? { ...current, title: event.target.value } : current) }))} />
                      <Input type="date" value={item.due_date || ""} onChange={(event) => setCompleteDraft((draft) => ({ ...draft, actionItems: draft.actionItems.map((current, itemIndex) => itemIndex === index ? { ...current, due_date: event.target.value } : current) }))} />
                      <Button type="button" variant="outline" onClick={() => setCompleteDraft((draft) => ({ ...draft, actionItems: draft.actionItems.filter((_, itemIndex) => itemIndex !== index) }))}>Remove</Button>
                    </div>
                  ))}
                  <Button type="button" variant="outline" onClick={() => setCompleteDraft((draft) => ({ ...draft, actionItems: [...draft.actionItems, { title: "", due_date: "" }] }))}>Add action item</Button>
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={completeDraft.createActionItemTasks} onChange={(event) => setCompleteDraft((draft) => ({ ...draft, createActionItemTasks: event.target.checked }))} />
                    Create action items as backlog tasks
                  </label>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 border-t p-5">
              <Button variant="outline" onClick={() => setCompleteTarget(null)}>Cancel</Button>
              <Button onClick={saveSprintReview} disabled={actionSprintId === completeTarget.id || (completeTarget.status !== "Completed" && completeDraft.incompleteAction === "move_to_next_sprint" && !completeDraft.carryForwardSprintId)}>
                {actionSprintId === completeTarget.id ? "Saving..." : completeTarget.status === "Completed" ? "Save review" : "Complete sprint"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function apiError(err: any, fallback: string) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  return fallback;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="space-y-2"><Label>{label}</Label>{children}</div>;
}

function Metric({ icon: Icon, label, value, tone }: { icon: typeof Activity; label: string; value: string | number; tone?: string }) {
  return <Card><CardContent className="flex items-center gap-3 p-4"><div className="rounded-lg bg-primary/10 p-2 text-primary"><Icon className="h-5 w-5" /></div><div><p className="text-sm text-muted-foreground">{label}</p><p className={`text-xl font-semibold ${tone || ""}`}>{value}</p></div></CardContent></Card>;
}

function Fact({ icon: Icon, label, value }: { icon: typeof Activity; label: string; value: string | number }) {
  return <div className="rounded-md bg-muted/50 p-2"><div className="flex items-center gap-1 text-xs text-muted-foreground"><Icon className="h-3.5 w-3.5" />{label}</div><p className="mt-1 font-semibold">{value}</p></div>;
}

function EmptyState({ text }: { text: string }) {
  return <div className="flex h-full min-h-32 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">{text}</div>;
}

function TextareaField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <textarea value={value} onChange={(event) => onChange(event.target.value)} className="min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring" />
    </div>
  );
}

function TaskSummary({ title, tasks, empty }: { title: string; tasks: PMSTaskListItem[]; empty: string }) {
  return (
    <div className="rounded-md border p-3">
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="font-medium">{title}</span>
        <Badge variant="outline">{tasks.length}</Badge>
      </div>
      <div className="max-h-56 space-y-2 overflow-y-auto">
        {tasks.map((task) => (
          <div key={task.id} className="rounded border bg-muted/30 p-2 text-sm">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">{task.task_key}</span>
              <Badge className={statusColor(task.status)}>{task.status}</Badge>
            </div>
            <p className="mt-1 line-clamp-2 text-muted-foreground">{task.title}</p>
          </div>
        ))}
        {!tasks.length ? <p className="py-4 text-center text-sm text-muted-foreground">{empty}</p> : null}
      </div>
    </div>
  );
}


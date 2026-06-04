import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Target, Plus, Star, TrendingUp, CheckCircle2, RefreshCw, MessageSquareText, Users, Grid3X3, BriefcaseBusiness, IndianRupee
} from "lucide-react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { performanceApi } from "@/services/api";
import { formatDate, statusColor } from "@/lib/utils";
import { usePageTitle } from "@/hooks/use-page-title";
import { toast } from "@/hooks/use-toast";

interface Cycle {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  status: string;
}

interface Goal {
  id: number;
  title: string;
  description?: string;
  target_value?: number;
  current_value?: number;
  unit?: string;
  due_date?: string;
  status: string;
  priority?: string;
  progress_pct?: number;
}

interface GoalForm {
  title: string;
  description?: string;
  due_date?: string;
  target_value?: number;
  unit?: string;
  priority?: string;
  cycle_id?: number;
}

interface ReviewForm {
  rating: number;
  self_comments?: string;
  goals_achieved?: number;
  cycle_id?: number;
}

interface Feedback360Request {
  id: number;
  employee_id: number;
  reviewer_id: number;
  relationship_type: string;
  due_date?: string;
  status: string;
  overall_rating?: number;
  comments?: string;
  created_at: string;
}

type PerformanceTab = "goals" | "reviews" | "360" | "calibration" | "oneOnOnes" | "nineBox" | "succession" | "compensation";

interface CalibrationSession {
  id: number;
  name: string;
  status: string;
  cycle_id: number;
  participants?: Array<{ id: number; employee_id: number; proposed_rating?: string | number; final_rating?: string | number; potential_rating?: string | number; notes?: string }>;
}

interface OneOnOneRecord {
  id: number;
  manager_id: number;
  employee_id: number;
  meeting_date: string;
  status: string;
  talking_points_json?: Array<{ text?: string; topic?: string }>;
  action_items_json?: Array<{ owner?: string; action?: string; due?: string }>;
}

interface NineBoxItem {
  employee_id: number;
  employee_name?: string;
  performance_rating?: string;
  potential_rating?: string;
  box: string;
}

interface CriticalRole {
  id: number;
  role_name: string;
  business_impact: string;
  vacancy_risk: string;
  successors?: Array<{ id: number; employee_id: number; readiness_level: string; development_actions_json?: Array<{ action?: string }> }>;
}

interface CompensationWorksheetRow {
  id: number;
  employee_id: number;
  current_ctc: string | number;
  proposed_merit_amount: string | number;
  proposed_merit_percent: string | number;
  proposed_ctc: string | number;
  budget_impact: string | number;
  approval_status: string;
}

export default function PerformancePage() {
  usePageTitle("Performance");
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<PerformanceTab>("goals");
  const [showGoalForm, setShowGoalForm] = useState(false);
  const [selectedCycle, setSelectedCycle] = useState<number | "">("");

  const { data: cycles } = useQuery({
    queryKey: ["perf-cycles"],
    queryFn: () => performanceApi.cycles().then((r) => r.data),
  });

  const { data: goals, isLoading: loadingGoals, refetch: refetchGoals } = useQuery({
    queryKey: ["goals", selectedCycle],
    queryFn: () =>
      performanceApi.goals(selectedCycle ? Number(selectedCycle) : undefined).then((r) => r.data),
    enabled: Boolean(selectedCycle),
    retry: false,
  });

  const { data: feedback360, isLoading: loading360 } = useQuery({
    queryKey: ["feedback-360-requests"],
    queryFn: () => performanceApi.feedback360Requests().then((r) => r.data as Feedback360Request[]),
    retry: false,
  });
  const { data: calibrationSessions } = useQuery({
    queryKey: ["perf-calibration", selectedCycle],
    queryFn: () => performanceApi.calibrationSessions(selectedCycle ? { cycle_id: Number(selectedCycle) } : undefined).then((r) => r.data as CalibrationSession[]),
  });
  const { data: oneOnOnes } = useQuery({
    queryKey: ["perf-one-on-ones"],
    queryFn: () => performanceApi.oneOnOnes().then((r) => r.data as OneOnOneRecord[]),
  });
  const { data: nineBox } = useQuery({
    queryKey: ["perf-nine-box", selectedCycle],
    queryFn: () => performanceApi.nineBox(selectedCycle ? { cycle_id: Number(selectedCycle) } : undefined).then((r) => r.data as { items: NineBoxItem[]; count: number }),
    enabled: Boolean(selectedCycle),
    retry: false,
  });
  const { data: criticalRoles } = useQuery({
    queryKey: ["perf-critical-roles"],
    queryFn: () => performanceApi.criticalRoles().then((r) => r.data as CriticalRole[]),
  });
  const { data: worksheetRows } = useQuery({
    queryKey: ["perf-comp-worksheet"],
    queryFn: () => performanceApi.compensationWorksheet().then((r) => r.data as CompensationWorksheetRow[]),
    retry: false,
  });

  const { register: regGoal, handleSubmit: submitGoal, reset: resetGoal, formState: { errors: goalErrors } } = useForm<GoalForm>();
  const { register: regReview, handleSubmit: submitReview, reset: resetReview } = useForm<ReviewForm>({
    defaultValues: { rating: 3, goals_achieved: 0 },
  });

  const createGoalMutation = useMutation({
    mutationFn: (data: GoalForm) =>
      performanceApi.createGoal({
        ...data,
        cycle_id: selectedCycle ? Number(selectedCycle) : undefined,
        target_value: data.target_value ? Number(data.target_value) : undefined,
      }),
    onSuccess: () => {
      toast({ title: "Goal created!" });
      resetGoal();
      setShowGoalForm(false);
      refetchGoals();
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed";
      toast({ title: "Error", description: msg, variant: "destructive" });
    },
  });

  const updateGoalMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Goal> }) =>
      performanceApi.updateGoal(id, data),
    onSuccess: () => {
      toast({ title: "Goal updated" });
      refetchGoals();
    },
  });

  const submitReviewMutation = useMutation({
    mutationFn: (data: ReviewForm) =>
      performanceApi.submitReview({
        cycle_id: selectedCycle ? Number(selectedCycle) : undefined,
        review_type: "Self",
        overall_rating: Number(data.rating),
        comments: data.self_comments,
        strengths: `Goals achieved: ${Number(data.goals_achieved || 0)} of ${totalGoals}`,
      }),
    onSuccess: () => {
      toast({ title: "Review submitted!" });
      resetReview();
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed";
      toast({ title: "Error", description: msg, variant: "destructive" });
    },
  });

  const completedGoals = (goals as Goal[])?.filter((g) => g.status === "Completed").length ?? 0;
  const totalGoals = (goals as Goal[])?.length ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="page-title">Performance</h1>
          <p className="page-description">Manage goals, track progress, and submit reviews.</p>
        </div>
        {activeTab === "goals" && (
          <Button size="sm" onClick={() => setShowGoalForm((v) => !v)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Goal
          </Button>
        )}
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: "Total Goals", value: totalGoals, color: "text-blue-600" },
          { label: "Completed", value: completedGoals, color: "text-green-600" },
          { label: "In Progress", value: (goals as Goal[])?.filter((g) => g.status === "In Progress").length ?? 0, color: "text-orange-600" },
          { label: "Overdue", value: (goals as Goal[])?.filter((g) => g.status === "Overdue").length ?? 0, color: "text-red-600" },
        ].map((s) => (
          <Card key={s.label}>
            <CardContent className="p-4 text-center">
              <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
              <p className="text-xs text-muted-foreground mt-1">{s.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Cycle selector */}
      <div className="flex items-center gap-3">
        <Label className="text-sm">Review Cycle</Label>
        <select
          value={selectedCycle}
          onChange={(e) => setSelectedCycle(e.target.value ? Number(e.target.value) : "")}
          className="flex h-9 rounded-md border border-input bg-background px-3 py-2 text-sm"
        >
          <option value="">All Cycles</option>
          {(cycles as Cycle[])?.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2 border-b">
        {([
          ["goals", "My Goals"],
          ["reviews", "Submit Review"],
          ["360", "360 Reviews"],
          ["calibration", "Calibration"],
          ["oneOnOnes", "1:1s"],
          ["nineBox", "Nine Box"],
          ["succession", "Succession"],
          ["compensation", "Comp Worksheet"],
        ] as Array<[PerformanceTab, string]>).map(([tab, label]) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-2 px-1 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {activeTab === "goals" && (
        <div className="space-y-4">
          {/* Create goal form */}
          {showGoalForm && (
            <Card>
              <CardHeader><CardTitle className="text-base">New Goal</CardTitle></CardHeader>
              <CardContent>
                <form
                  onSubmit={submitGoal((data) => createGoalMutation.mutate(data))}
                  className="grid grid-cols-1 sm:grid-cols-2 gap-4"
                >
                  <div className="sm:col-span-2 space-y-1.5">
                    <Label>Goal Title *</Label>
                    <Input {...regGoal("title", { required: "Required" })} placeholder="e.g. Complete Q2 product launch" />
                    {goalErrors.title && <p className="text-xs text-red-500">{goalErrors.title.message}</p>}
                  </div>
                  <div className="sm:col-span-2 space-y-1.5">
                    <Label>Description</Label>
                    <textarea
                      {...regGoal("description")}
                      rows={2}
                      className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none"
                      placeholder="Describe the goal..."
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Target Value</Label>
                    <Input type="number" {...regGoal("target_value")} placeholder="e.g. 100" />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Unit</Label>
                    <Input {...regGoal("unit")} placeholder="e.g. %, deals, tasks" />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Due Date</Label>
                    <Input type="date" {...regGoal("due_date")} />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Priority</Label>
                    <select
                      {...regGoal("priority")}
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    >
                      <option value="">Normal</option>
                      <option value="High">High</option>
                      <option value="Medium">Medium</option>
                      <option value="Low">Low</option>
                    </select>
                  </div>
                  <div className="sm:col-span-2 flex gap-3">
                    <Button type="submit" disabled={createGoalMutation.isPending}>
                      {createGoalMutation.isPending ? "Creating..." : "Create Goal"}
                    </Button>
                    <Button type="button" variant="outline" onClick={() => setShowGoalForm(false)}>Cancel</Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          )}

          {/* Goals list */}
          {loadingGoals ? (
            Array.from({ length: 4 }).map((_, i) => (
              <Card key={i}><CardContent className="p-5"><div className="h-16 skeleton rounded" /></CardContent></Card>
            ))
          ) : !(goals as Goal[])?.length ? (
            <Card>
              <CardContent className="p-12 text-center text-muted-foreground">
                <Target className="h-10 w-10 mx-auto mb-3 opacity-30" />
                <p>No goals yet. Add your first goal!</p>
              </CardContent>
            </Card>
          ) : (
            (goals as Goal[]).map((goal) => {
              const progress = goal.progress_pct ?? (goal.target_value && goal.current_value != null
                ? Math.min(100, (goal.current_value / goal.target_value) * 100)
                : 0);

              return (
                <Card key={goal.id}>
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 space-y-2">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="font-semibold text-sm">{goal.title}</h3>
                          {goal.priority && (
                            <span className={`text-xs px-1.5 py-0.5 rounded ${statusColor(goal.priority)}`}>
                              {goal.priority}
                            </span>
                          )}
                        </div>
                        {goal.description && (
                          <p className="text-xs text-muted-foreground">{goal.description}</p>
                        )}
                        {goal.target_value && (
                          <p className="text-xs text-muted-foreground">
                            Progress: {goal.current_value ?? 0} / {goal.target_value} {goal.unit || ""}
                          </p>
                        )}
                        <div className="h-1.5 bg-muted rounded-full overflow-hidden w-full max-w-xs">
                          <div
                            className="h-full bg-primary rounded-full transition-all"
                            style={{ width: `${progress}%` }}
                          />
                        </div>
                        <p className="text-xs text-muted-foreground">{Math.round(progress)}% complete</p>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(goal.status)}`}>
                          {goal.status}
                        </span>
                        {goal.due_date && (
                          <span className="text-xs text-muted-foreground">Due {formatDate(goal.due_date)}</span>
                        )}
                        {goal.status !== "Completed" && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 text-xs"
                            onClick={() => updateGoalMutation.mutate({ id: goal.id, data: { status: "Completed" } })}
                          >
                            <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                            Mark Done
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })
          )}
        </div>
      )}

      {activeTab === "reviews" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Self Review</CardTitle>
            <CardDescription>Submit your performance self-assessment</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={submitReview((data) => submitReviewMutation.mutate(data))}
              className="space-y-6"
            >
              {/* Star rating */}
              <div className="space-y-2">
                <Label>Overall Rating *</Label>
                <div className="flex gap-3">
                  {[1, 2, 3, 4, 5].map((r) => (
                    <label key={r} className="cursor-pointer">
                      <input
                        type="radio"
                        value={r}
                        {...regReview("rating")}
                        className="sr-only"
                      />
                      <Star className="h-8 w-8 text-yellow-400 fill-yellow-400 hover:scale-110 transition-transform" />
                    </label>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">Rating: 1 (Needs Improvement) â€“ 5 (Exceptional)</p>
              </div>

              <div className="space-y-1.5">
                <Label>Goals Achieved</Label>
                <Input
                  type="number"
                  min={0}
                  max={totalGoals}
                  {...regReview("goals_achieved")}
                  placeholder={`Out of ${totalGoals} goals`}
                />
              </div>

              <div className="space-y-1.5">
                <Label>Self Comments</Label>
                <textarea
                  {...regReview("self_comments")}
                  rows={4}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none"
                  placeholder="Summarize your achievements, challenges, and areas for growth..."
                />
              </div>

              <Button type="submit" disabled={submitReviewMutation.isPending}>
                {submitReviewMutation.isPending ? "Submitting..." : "Submit Review"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {activeTab === "360" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">360 Reviews</CardTitle>
            <CardDescription>Pending and submitted feedback requests</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading360 ? (
              Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-16 skeleton rounded" />)
            ) : !(feedback360 || []).length ? (
              <div className="rounded-lg border p-8 text-center text-sm text-muted-foreground">
                <MessageSquareText className="mx-auto mb-3 h-8 w-8 opacity-40" />
                No 360 feedback requests assigned.
              </div>
            ) : (
              (feedback360 || []).map((item) => (
                <div key={item.id} className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm font-medium">Employee #{item.employee_id} feedback</p>
                    <p className="text-xs text-muted-foreground">
                      {item.relationship_type} review {item.due_date ? `due ${formatDate(item.due_date)}` : "with no due date"}
                    </p>
                    {item.comments && <p className="mt-2 text-xs text-muted-foreground">{item.comments}</p>}
                  </div>
                  <Badge variant={item.status === "Submitted" ? "default" : "secondary"}>{item.status}</Badge>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === "calibration" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Calibration Sessions</CardTitle>
            <CardDescription>Review-cycle rating moderation with proposed, final, and potential ratings.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {(calibrationSessions || []).map((session) => (
              <div key={session.id} className="rounded-lg border p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium">{session.name}</p>
                    <p className="text-xs text-muted-foreground">Cycle #{session.cycle_id} - {session.participants?.length || 0} participants</p>
                  </div>
                  <Badge>{session.status}</Badge>
                </div>
                <div className="mt-3 grid gap-2 sm:grid-cols-3">
                  {(session.participants || []).slice(0, 6).map((participant) => (
                    <div key={participant.id} className="rounded-md bg-muted/50 p-3 text-xs">
                      <p className="font-medium">Employee #{participant.employee_id}</p>
                      <p className="text-muted-foreground">Proposed {participant.proposed_rating || "-"} / Final {participant.final_rating || "-"}</p>
                      <p className="text-muted-foreground">Potential {participant.potential_rating || "-"}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            {!calibrationSessions?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No calibration sessions yet.</p>}
          </CardContent>
        </Card>
      )}

      {activeTab === "oneOnOnes" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">One-on-Ones</CardTitle>
            <CardDescription>Manager and employee conversations with action follow-through.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {(oneOnOnes || []).slice(0, 20).map((item) => (
              <div key={item.id} className="grid gap-3 rounded-lg border p-4 sm:grid-cols-[1fr_auto]">
                <div>
                  <p className="text-sm font-medium">Employee #{item.employee_id} with Manager #{item.manager_id}</p>
                  <p className="text-xs text-muted-foreground">{formatDate(item.meeting_date)}</p>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {(item.talking_points_json || []).map((point) => point.text || point.topic).filter(Boolean).join(", ") || "No talking points captured"}
                  </p>
                </div>
                <Badge variant={item.status === "Closed" ? "default" : "secondary"}>{item.status}</Badge>
              </div>
            ))}
            {!oneOnOnes?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No one-on-one records yet.</p>}
          </CardContent>
        </Card>
      )}

      {activeTab === "nineBox" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Nine-Box Grid</CardTitle>
            <CardDescription>Performance and potential placement from calibration outcomes.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-3">
              {(nineBox?.items || []).map((item) => (
                <div key={`${item.employee_id}-${item.box}`} className="rounded-lg border p-4">
                  <Grid3X3 className="mb-2 h-4 w-4 text-primary" />
                  <p className="text-sm font-medium">{item.employee_name || `Employee #${item.employee_id}`}</p>
                  <p className="text-xs text-muted-foreground">Performance {item.performance_rating || "-"} / Potential {item.potential_rating || "-"}</p>
                  <Badge className="mt-3" variant="secondary">{item.box}</Badge>
                </div>
              ))}
            </div>
            {!nineBox?.items?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No nine-box placements yet.</p>}
          </CardContent>
        </Card>
      )}

      {activeTab === "succession" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Succession & Career Paths</CardTitle>
            <CardDescription>Critical roles, successors, readiness, and development actions.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {(criticalRoles || []).map((role) => (
              <div key={role.id} className="rounded-lg border p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium">{role.role_name}</p>
                    <p className="text-xs text-muted-foreground">Impact {role.business_impact} - Vacancy risk {role.vacancy_risk}</p>
                  </div>
                  <BriefcaseBusiness className="h-5 w-5 text-primary" />
                </div>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {(role.successors || []).map((candidate) => (
                    <div key={candidate.id} className="rounded-md bg-muted/50 p-3 text-xs">
                      <p className="font-medium">Successor Employee #{candidate.employee_id}</p>
                      <p className="text-muted-foreground">{candidate.readiness_level}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            {!criticalRoles?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No critical roles configured.</p>}
          </CardContent>
        </Card>
      )}

      {activeTab === "compensation" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Compensation Worksheet</CardTitle>
            <CardDescription>Restricted merit planning with pay-band and budget impact tracking.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {(worksheetRows || []).map((row) => (
              <div key={row.id} className="grid gap-3 rounded-lg border p-4 sm:grid-cols-[1fr_auto]">
                <div>
                  <p className="text-sm font-medium">Employee #{row.employee_id}</p>
                  <p className="text-xs text-muted-foreground">
                    Current INR {Number(row.current_ctc || 0).toLocaleString("en-IN")} - Proposed INR {Number(row.proposed_ctc || 0).toLocaleString("en-IN")}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Merit INR {Number(row.proposed_merit_amount || 0).toLocaleString("en-IN")} ({row.proposed_merit_percent || 0}%) - Budget impact INR {Number(row.budget_impact || 0).toLocaleString("en-IN")}
                  </p>
                </div>
                <div className="flex items-center gap-2 sm:justify-end">
                  <IndianRupee className="h-4 w-4 text-primary" />
                  <Badge>{row.approval_status}</Badge>
                </div>
              </div>
            ))}
            {!worksheetRows?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No accessible compensation worksheet rows.</p>}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

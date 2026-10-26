import { RichTextField, RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import { Fragment, type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, Edit2, Plus, ShieldAlert, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn, formatDate, statusColor } from "@/lib/utils";
import { pmsUsersAPI, projectsAPI, risksAPI, tasksAPI } from "../services/api";
import type { CreateRiskInput, PMSMentionUser, PMSProject, PMSRisk, PMSTask } from "../types";

type Filters = {
  projectId: string;
  status: string;
  ownerId: string;
  severity: string;
};

const riskError = (error: any, fallback: string) => {
  const detail = error?.response?.data?.detail;
  return typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map(item => item.msg).join(". ") : fallback;
};

const defaultFilters: Filters = {
  projectId: "",
  status: "",
  ownerId: "",
  severity: "",
};

const emptyForm: CreateRiskInput = {
  project_id: 0,
  linked_task_id: null,
  title: "",
  description: "",
  category: "",
  probability: 3,
  impact: 3,
  status: "open",
  owner_user_id: null,
  mitigation_plan: "",
  contingency_plan: "",
  due_date: "",
};

export default function RisksPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [filters, setFilters] = useState<Filters>({ ...defaultFilters, projectId: projectId || "" });
  const [projects, setProjects] = useState<PMSProject[]>([]);
  const [users, setUsers] = useState<PMSMentionUser[]>([]);
  const [tasks, setTasks] = useState<PMSTask[]>([]);
  const [risks, setRisks] = useState<PMSRisk[]>([]);
  const [form, setForm] = useState<CreateRiskInput>(emptyForm);
  const [editing, setEditing] = useState<PMSRisk | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (projectId) {
      setFilters((current) => ({ ...current, projectId }));
    }
  }, [projectId]);

  useEffect(() => {
    Promise.all([
      projectsAPI.list(),
      pmsUsersAPI.search({ q: "", limit: 25 }),
    ])
      .then(([projectItems, userItems]) => {
        setProjects(projectItems);
        setUsers(userItems);
        const initialProjectId = Number(projectId || projectItems[0]?.id || 0);
        setForm((current) => ({ ...current, project_id: initialProjectId }));
      })
      .catch((err) => setError(riskError(err, "Unable to load risk register filters.")));
  }, [projectId]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    risksAPI.list(filters)
      .then(setRisks)
      .catch((err) => setError(riskError(err, "Unable to load risks.")))
      .finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => {
    if (!form.project_id) {
      setTasks([]);
      return;
    }
    tasksAPI.list(form.project_id)
      .then(setTasks)
      .catch(() => setTasks([]));
  }, [form.project_id]);

  const ownersById = useMemo(() => new Map(users.map((user) => [user.id, user.name || user.email])), [users]);
  const projectsById = useMemo(() => new Map(projects.map((project) => [project.id, project])), [projects]);
  const openHighRisks = risks.filter((risk) => ["open", "mitigating"].includes(risk.status) && risk.risk_score >= 15);
  const avgScore = risks.length ? Math.round(risks.reduce((sum, risk) => sum + risk.risk_score, 0) / risks.length) : 0;

  const updateFilter = (key: keyof Filters, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }));
  };

  const resetForm = () => {
    setEditing(null);
    setShowForm(false);
    setForm({ ...emptyForm, project_id: Number(filters.projectId || projects[0]?.id || 0) });
  };

  const startEdit = (risk: PMSRisk) => {
    setEditing(risk);
    setShowForm(true);
    setForm({
      project_id: risk.project_id,
      linked_task_id: risk.linked_task_id || null,
      title: risk.title,
      description: risk.description || "",
      category: risk.category || "",
      probability: risk.probability,
      impact: risk.impact,
      status: risk.status,
      owner_user_id: risk.owner_user_id || null,
      mitigation_plan: risk.mitigation_plan || "",
      contingency_plan: risk.contingency_plan || "",
      due_date: risk.due_date || "",
    });
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!form.project_id || !form.title.trim()) return;
    setSaving(true);
    setError(null);
    const payload = {
      ...form,
      linked_task_id: form.linked_task_id || null,
      owner_user_id: form.owner_user_id || null,
      due_date: form.due_date || null,
      title: form.title.trim(),
    };
    try {
      if (editing) {
        await risksAPI.update(editing.id, payload);
      } else {
        await risksAPI.create(payload);
      }
      const data = await risksAPI.list(filters);
      setRisks(data);
      resetForm();
    } catch (err: any) {
      setError(riskError(err, "Unable to save risk."));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (risk: PMSRisk) => {
    if (!window.confirm(`Delete risk "${risk.title}"?`)) return;
    await risksAPI.delete(risk.id);
    setRisks((current) => current.filter((item) => item.id !== risk.id));
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="page-title">Risk Register</h1>
          <p className="page-description">Track project-level probability, impact, mitigation plans, owners, and delivery health risk.</p>
        </div>
        <Button onClick={() => setShowForm(true)}><Plus className="h-4 w-4" />Add risk</Button>
      </div>

      <Card>
        <CardContent className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-4">
          <Filter label="Project" value={filters.projectId} onChange={(value) => updateFilter("projectId", value)}>
            <option value="">All accessible projects</option>
            {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </Filter>
          <Filter label="Status" value={filters.status} onChange={(value) => updateFilter("status", value)}>
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="mitigating">Mitigating</option>
            <option value="closed">Closed</option>
          </Filter>
          <Filter label="Owner" value={filters.ownerId} onChange={(value) => updateFilter("ownerId", value)}>
            <option value="">All owners</option>
            {users.map((user) => <option key={user.id} value={user.id}>{user.name || user.email}</option>)}
          </Filter>
          <Filter label="Severity" value={filters.severity} onChange={(value) => updateFilter("severity", value)}>
            <option value="">All severities</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </Filter>
        </CardContent>
      </Card>

      {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}

      <div className="grid gap-4 md:grid-cols-3">
        <Metric icon={ShieldAlert} label="Open high risks" value={openHighRisks.length} tone="text-red-600" />
        <Metric icon={AlertTriangle} label="Total risks" value={risks.length} />
        <Metric icon={ShieldAlert} label="Average score" value={avgScore} tone={avgScore >= 15 ? "text-red-600" : avgScore >= 8 ? "text-amber-600" : "text-emerald-600"} />
      </div>

      {showForm ? (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>{editing ? "Edit risk" : "Add risk"}</CardTitle>
            <Button variant="ghost" size="sm" onClick={resetForm}><X className="h-4 w-4" /></Button>
          </CardHeader>
          <CardContent>
            <form className="grid gap-4 lg:grid-cols-2" onSubmit={submit}>
              <Field label="Project">
                <select className="input" value={form.project_id || ""} onChange={(event) => setForm((current) => ({ ...current, project_id: Number(event.target.value), linked_task_id: null }))} required>
                  <option value="">Select project</option>
                  {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                </select>
              </Field>
              <Field label="Title">
                <Input value={form.title} onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))} required />
              </Field>
              <Field label="Category">
                <Input value={form.category || ""} onChange={(event) => setForm((current) => ({ ...current, category: event.target.value }))} placeholder="Delivery, Scope, Budget, Vendor" />
              </Field>
              <Field label="Owner">
                <select className="input" value={form.owner_user_id || ""} onChange={(event) => setForm((current) => ({ ...current, owner_user_id: event.target.value ? Number(event.target.value) : null }))}>
                  <option value="">Unassigned</option>
                  {users.map((user) => <option key={user.id} value={user.id}>{user.name || user.email}</option>)}
                </select>
              </Field>
              <Field label="Probability">
                <select className="input" value={form.probability || 3} onChange={(event) => setForm((current) => ({ ...current, probability: Number(event.target.value) }))}>
                  {[1, 2, 3, 4, 5].map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </Field>
              <Field label="Impact">
                <select className="input" value={form.impact || 3} onChange={(event) => setForm((current) => ({ ...current, impact: Number(event.target.value) }))}>
                  {[1, 2, 3, 4, 5].map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </Field>
              <Field label="Status">
                <select className="input" value={form.status || "open"} onChange={(event) => setForm((current) => ({ ...current, status: event.target.value }))}>
                  <option value="open">Open</option>
                  <option value="mitigating">Mitigating</option>
                  <option value="closed">Closed</option>
                </select>
              </Field>
              <Field label="Due date">
                <Input type="date" value={form.due_date || ""} onChange={(event) => setForm((current) => ({ ...current, due_date: event.target.value }))} />
              </Field>
              <Field label="Linked task">
                <select className="input" value={form.linked_task_id || ""} onChange={(event) => setForm((current) => ({ ...current, linked_task_id: event.target.value ? Number(event.target.value) : null }))}>
                  <option value="">No linked task</option>
                  {tasks.map((task) => <option key={task.id} value={task.id}>{task.task_key} - {task.title}</option>)}
                </select>
              </Field>
              <Field label={`Score ${(form.probability || 0) * (form.impact || 0)}`}>
                <div className={cn("rounded-md border px-3 py-2 text-sm font-medium", severityTone((form.probability || 0) * (form.impact || 0)))}>
                  {severityLabel((form.probability || 0) * (form.impact || 0))}
                </div>
              </Field>
              <Field label="Description" wide>
                <RichTextField data-legacy-format="markdown" className="input min-h-24" value={form.description || ""} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} />
              </Field>
              <Field label="Mitigation plan" wide>
                <RichTextField data-legacy-format="markdown" className="input min-h-24" value={form.mitigation_plan || ""} onChange={(event) => setForm((current) => ({ ...current, mitigation_plan: event.target.value }))} />
              </Field>
              <Field label="Contingency plan" wide>
                <RichTextField data-legacy-format="markdown" className="input min-h-24" value={form.contingency_plan || ""} onChange={(event) => setForm((current) => ({ ...current, contingency_plan: event.target.value }))} />
              </Field>
              <div className="flex gap-2 lg:col-span-2">
                <Button type="submit" disabled={saving || !form.title.trim() || !form.project_id}>{saving ? "Saving..." : editing ? "Update risk" : "Create risk"}</Button>
                <Button type="button" variant="outline" onClick={resetForm}>Cancel</Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
        <Card>
          <CardHeader><CardTitle>Risk Matrix</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-[44px_repeat(5,minmax(0,1fr))] gap-2 text-center text-xs">
              <div />
              {[1, 2, 3, 4, 5].map((probability) => <div key={probability} className="font-medium text-muted-foreground">P{probability}</div>)}
              {[5, 4, 3, 2, 1].map((impact) => (
                <Fragment key={impact}>
                  <div key={`label-${impact}`} className="flex items-center justify-center font-medium text-muted-foreground">I{impact}</div>
                  {[1, 2, 3, 4, 5].map((probability) => {
                    const score = impact * probability;
                    const count = risks.filter((risk) => risk.impact === impact && risk.probability === probability).length;
                    return (
                      <div key={`${impact}-${probability}`} className={cn("flex aspect-square items-center justify-center rounded-md border font-semibold", matrixTone(score))}>
                        {count || ""}
                      </div>
                    );
                  })}
                </Fragment>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Register</CardTitle></CardHeader>
          <CardContent className="p-0">
            {loading ? <div className="m-4 h-72 rounded-lg skeleton" /> : null}
            {!loading ? (
              <div className="overflow-x-auto">
                <table className="min-w-[1040px] w-full text-sm">
                  <thead className="border-b bg-muted/40 text-left text-xs uppercase text-muted-foreground">
                    <tr>
                      {["Risk", "Project", "Status", "Score", "Owner", "Due", "Linked task", "Plans", ""].map((heading) => (
                        <th key={heading} className="p-3 font-semibold">{heading}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {risks.map((risk) => (
                      <tr key={risk.id} className="border-b align-top hover:bg-muted/40">
                        <td className="max-w-sm p-3">
                          <p className="font-semibold">{risk.title}</p>
                          <div className="line-clamp-2 text-xs text-muted-foreground"><RichTextContent value={risk.description || risk.category || "No description"}/></div>
                        </td>
                        <td className="p-3">{projectsById.get(risk.project_id)?.name || `Project ${risk.project_id}`}</td>
                        <td className="p-3"><Badge className={statusColor(risk.status)}>{risk.status}</Badge></td>
                        <td className="p-3"><Badge className={severityTone(risk.risk_score)}>{risk.risk_score} {severityLabel(risk.risk_score)}</Badge></td>
                        <td className="p-3">{risk.owner_user_id ? ownersById.get(risk.owner_user_id) || `User ${risk.owner_user_id}` : "Unassigned"}</td>
                        <td className="p-3">{risk.due_date ? formatDate(risk.due_date) : "-"}</td>
                        <td className="p-3">{risk.linked_task_id ? <Link className="text-primary underline-offset-4 hover:underline" to={`/pms/tasks/${risk.linked_task_id}`}>Task #{risk.linked_task_id}</Link> : "-"}</td>
                        <td className="max-w-xs p-3 text-xs text-muted-foreground">
                          <p className="line-clamp-1">Mitigation: {risk.mitigation_plan || "-"}</p>
                          <p className="line-clamp-1">Contingency: {risk.contingency_plan || "-"}</p>
                        </td>
                        <td className="p-3">
                          <div className="flex justify-end gap-1">
                            <Button variant="ghost" size="sm" onClick={() => startEdit(risk)}><Edit2 className="h-4 w-4" /></Button>
                            <Button variant="ghost" size="sm" onClick={() => remove(risk)}><Trash2 className="h-4 w-4 text-red-600" /></Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!risks.length ? <div className="p-8 text-center text-sm text-muted-foreground">No risks match the current filters.</div> : null}
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Filter({ label, value, onChange, children }: { label: string; value: string; onChange: (value: string) => void; children: ReactNode }) {
  return (
    <label className="space-y-1 text-sm">
      <span className="text-xs font-medium uppercase text-muted-foreground">{label}</span>
      <select className="input" value={value} onChange={(event) => onChange(event.target.value)}>{children}</select>
    </label>
  );
}

function Field({ label, wide, children }: { label: string; wide?: boolean; children: ReactNode }) {
  return (
    <div className={cn("space-y-1", wide && "lg:col-span-2")}>
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function Metric({ icon: Icon, label, value, tone = "text-primary" }: { icon: typeof ShieldAlert; label: string; value: string | number; tone?: string }) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between p-4">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className={cn("text-2xl font-semibold", tone)}>{value}</p>
        </div>
        <Icon className={cn("h-5 w-5", tone)} />
      </CardContent>
    </Card>
  );
}

function severityLabel(score: number) {
  if (score >= 15) return "High";
  if (score >= 8) return "Medium";
  return "Low";
}

function severityTone(score: number) {
  if (score >= 15) return "border-red-200 bg-red-50 text-red-700";
  if (score >= 8) return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-emerald-200 bg-emerald-50 text-emerald-700";
}

function matrixTone(score: number) {
  if (score >= 20) return "border-red-300 bg-red-200 text-red-900";
  if (score >= 15) return "border-red-200 bg-red-100 text-red-800";
  if (score >= 8) return "border-amber-200 bg-amber-100 text-amber-800";
  return "border-emerald-200 bg-emerald-50 text-emerald-800";
}

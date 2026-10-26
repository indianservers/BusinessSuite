import { RichTextField, RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useSearchParams, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { projectsAPI } from "../services/api";
import type { ProjectPriority, ProjectStatus } from "../types";

export default function CreateProjectPage() {
  const navigate = useNavigate();
  const { projectId } = useParams();
  const editing = Boolean(projectId);
  const [loading, setLoading] = useState(editing);
  const [canEdit, setCanEdit] = useState(!editing);
  const [searchParams] = useSearchParams();
  const workspaceId = Number(searchParams.get("workspace_id")) || undefined;
  const [name, setName] = useState("");
  const [projectKey, setProjectKey] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<ProjectStatus>("Active");
  const [priority, setPriority] = useState<ProjectPriority>("Medium");
  const [startDate, setStartDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [budget, setBudget] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    let active = true;
    projectsAPI.get(Number(projectId)).then(project => {
      if (!active) return;
      setCanEdit(project.can_edit_project === true);
      setName(project.name); setProjectKey(project.project_key); setDescription(project.description || "");
      setStatus(project.status); setPriority(project.priority); setStartDate(project.start_date?.slice(0,10) || "");
      setDueDate(project.due_date?.slice(0,10) || ""); setBudget(String(project.budget_amount ?? ""));
      if (!project.can_edit_project) setError("You do not have permission to edit this project.");
    }).catch(err => {if(active) setError(err?.response?.data?.detail || "Unable to load project.");})
      .finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  }, [projectId]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (loading || !canEdit || submitting) return;
    if (!name.trim()) return setError("Project name is required.");
    if (!editing && !/^[A-Z0-9]{2,10}$/.test(projectKey)) return setError("Project key must be uppercase and 2-10 characters.");
    if (startDate && dueDate && startDate > dueDate) return setError("Start date cannot be after due date.");
    if (Number(budget || 0) < 0) return setError("Budget cannot be negative.");

    try {
      setSubmitting(true);
      setError(null);
      const payload = {
        workspace_id: workspaceId,
        name,
        project_key: projectKey,
        description,
        status,
        priority,
        start_date: startDate || undefined,
        due_date: dueDate || undefined,
        budget_amount: budget ? Number(budget) : undefined,
      };
      const project = editing
        ? await projectsAPI.update(Number(projectId), {...payload, start_date:startDate || null, due_date:dueDate || null, budget_amount:Number(budget || 0)})
        : await projectsAPI.create(payload);
      navigate(`/pms/projects/${project.id}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Failed to create project.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Button type="button" variant="ghost" onClick={() => navigate("/pms/projects")}>
        <ArrowLeft className="h-4 w-4" />Back
      </Button>
      <Card>
        <CardHeader>
          <CardTitle>{editing ? "Edit project" : "Create project"}</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-5" onSubmit={submit}>
            {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
            <fieldset disabled={loading || !canEdit || submitting} className="space-y-5"><div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="project-name">Project name</Label>
                <Input id="project-name" value={name} onChange={(event) => setName(event.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="project-key">Project key</Label>
                <Input disabled={editing} id="project-key" value={projectKey} onChange={(event) => setProjectKey(event.target.value.toUpperCase())} maxLength={10} />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="project-description">Description</Label>
              <RichTextField data-legacy-format="markdown" id="project-description" value={description} onChange={(event) => setDescription(event.target.value)} className="min-h-28 w-full rounded-md border bg-background px-3 py-2 text-sm" />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="project-status">Status</Label>
                <select id="project-status" value={status} onChange={(event) => setStatus(event.target.value as ProjectStatus)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                  {["Draft", "Planned", "Active", "On Hold", "Completed", "Cancelled", "Archived"].map((item) => <option key={item}>{item}</option>)}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="project-priority">Priority</Label>
                <select id="project-priority" value={priority} onChange={(event) => setPriority(event.target.value as ProjectPriority)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                  {["Low", "Medium", "High", "Critical"].map((item) => <option key={item}>{item}</option>)}
                </select>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="start-date">Start date</Label>
                <Input id="start-date" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="due-date">Due date</Label>
                <Input id="due-date" type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="budget">Budget limit</Label>
                <Input id="budget" type="number" min="0" step="0.01" value={budget} onChange={(event) => setBudget(event.target.value)} placeholder="Optional cap" />
                <p className="text-xs text-muted-foreground">Used for budget vs actual tracking.</p>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => navigate("/pms/projects")}>Cancel</Button>
              <Button type="submit" disabled={submitting}>{submitting ? "Saving…" : editing ? "Save changes" : "Create project"}</Button>
            </div>
          </fieldset></form>
        </CardContent>
      </Card>
    </div>
  );
}


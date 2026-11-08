import {useRecordAutosave,useRecordDraft} from "@/hooks/use-record-autosave";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import { api } from "@/services/api";
import { type FieldRecord, fieldPath } from "../components/CustomFields";
import { CustomFieldsForm, type FieldDraft } from "../components/CustomFields";
import { RichTextField, RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import { FormEvent, useEffect, useRef, useState } from "react";
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
  const [customReady,setCustomReady]=useState(!editing);
  const [canEdit, setCanEdit] = useState(!editing);
  const [searchParams] = useSearchParams();
  const workspaceId = Number(searchParams.get("workspace_id")) || undefined;
  const [customValues,setCustomValues]=useState<FieldDraft>({});
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
      api.get<FieldRecord>(fieldPath("project",Number(projectId))).then(({data})=>{if(active)setCustomValues(Object.fromEntries(data.fields.map(f=>[f.id,{value:f.value??null,...(f.country_code?{country_code:f.country_code}:{})}])));}).catch(()=>undefined).finally(()=>{if(active)setCustomReady(true);});
      setName(project.name); setProjectKey(project.project_key); setDescription(project.description || "");
      setStatus(project.status); setPriority(project.priority); setStartDate(project.start_date?.slice(0,10) || "");
      setDueDate(project.due_date?.slice(0,10) || ""); setBudget(String(project.budget_amount ?? ""));
      if (!project.can_edit_project) setError("You do not have permission to edit this project.");
    }).catch(err => {if(active) setError(err?.response?.data?.detail || "Unable to load project.");})
      .finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  }, [projectId]);

  const writing=useRef(false);
  const savedSnapshot=useRef<string>();
  const submit = async (event?: FormEvent,automatic=false) => {
    event?.preventDefault();
    if (loading || !canEdit || submitting || writing.current) return false;
    if (!name.trim()) {setError("Project name is required.");return false;}
    if (!editing && !/^[A-Z0-9]{2,10}$/.test(projectKey)) {setError("Project key must be uppercase and 2-10 characters.");return false;}
    if (startDate && dueDate && startDate > dueDate) {setError("Start date cannot be after due date.");return false;}
    if (Number(budget || 0) < 0) {setError("Budget cannot be negative.");return false;}

    try {
      writing.current=true;setSubmitting(!automatic);
      setError(null);
      const payload = {
        workspace_id: workspaceId,
        custom_fields: customValues,
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
      if(automatic)savedSnapshot.current=JSON.stringify(snapshot);
      if(!automatic){clearDraft();navigate(`/pms/projects/${project.id}`);}return true;
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Failed to create project.");return false;
    } finally {
      writing.current=false;setSubmitting(false);
    }
  };

  const snapshot={name,projectKey,description,status,priority,startDate,dueDate,budget,customValues};
  const clearDraft=useRecordDraft(`project:${workspaceId||"default"}:new`,snapshot,d=>{setName(d.name);setProjectKey(d.projectKey);setDescription(d.description);setStatus(d.status);setPriority(d.priority);setStartDate(d.startDate);setDueDate(d.dueDate);setBudget(d.budget);setCustomValues(d.customValues);},!editing);
  useEffect(()=>{if(editing&&!loading&&customReady&&savedSnapshot.current===undefined)savedSnapshot.current=JSON.stringify(snapshot);},[editing,loading,customReady,snapshot]);
  const auto=useRecordAutosave({value:snapshot,enabled:editing&&canEdit&&!loading&&customReady&&!submitting,dirty:savedSnapshot.current!==undefined&&savedSnapshot.current!==JSON.stringify(snapshot),save:()=>submit(undefined,true)});
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
          <CompactForm className="space-y-5" onSubmit={submit}>
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
            <CustomFieldsForm placement={editing?"edit":"create"} entity="project" projectId={projectId?Number(projectId):undefined} values={customValues} onChange={setCustomValues}/>
            <div className="space-y-2">
              <Label htmlFor="project-description">Description</Label>
              <RichTextField data-legacy-format="markdown" id="project-description" value={description} onChange={(event) => setDescription(event.target.value)} className="min-h-28 w-full rounded-md border bg-background px-3 py-2 text-sm" />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="project-status">Status</Label>
                <NativeSelect id="project-status" value={status} onChange={(event) => setStatus(event.target.value as ProjectStatus)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                  {["Draft", "Planned", "Active", "On Hold", "Completed", "Cancelled", "Archived"].map((item) => <option key={item}>{item}</option>)}
                </NativeSelect>
              </div>
              <div className="space-y-2">
                <Label htmlFor="project-priority">Priority</Label>
                <NativeSelect id="project-priority" value={priority} onChange={(event) => setPriority(event.target.value as ProjectPriority)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                  {["Low", "Medium", "High", "Critical"].map((item) => <option key={item}>{item}</option>)}
                </NativeSelect>
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
              <span role="status">{editing?auto.message:"Draft saved automatically"}</span><Button type="submit" data-save-action disabled={submitting||auto.saving}>{submitting ? "Saving…" : editing ? "Save changes" : "Create project"}</Button>
            </div>
          </fieldset></CompactForm>
        </CardContent>
      </Card>
    </div>
  );
}


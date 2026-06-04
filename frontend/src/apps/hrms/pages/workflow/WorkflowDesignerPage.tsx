import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, Copy, Edit2, GitBranch, GripVertical, MoreHorizontal, Plus, Save, Search, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { workflowDefinitionsApi } from "@/services/api";
import { usePageTitle } from "@/hooks/use-page-title";
import { toast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

type WorkflowDefinition = {
  id: number;
  name: string;
  description?: string | null;
  module: string;
  trigger_event: string;
  is_active: boolean;
  version?: number;
  steps?: WorkflowStep[];
};

type WorkflowStep = {
  id: number;
  definition_id?: number;
  step_order: number;
  name: string;
  step_type: string;
  assignee_type: string;
  assignee_role?: string | null;
  assignee_user_id?: number | null;
  timeout_hours?: number | null;
  timeout_action?: string | null;
  condition_expression?: string | null;
  skip_if_condition?: string | null;
  reminder_hours?: number | null;
  escalation_user_id?: number | null;
  escalation_role?: string | null;
  action_type?: string | null;
  action_config?: { target_module?: string; target_id?: number; fields?: Record<string, unknown> } | null;
  delegation_type?: string | null;
  delegation_value?: string | null;
  delegation_starts_at?: string | null;
  delegation_ends_at?: string | null;
  is_active: boolean;
  description?: string | null;
};

const MODULES = ["employee", "leave", "payroll", "recruitment", "onboarding", "helpdesk", "attendance", "expense", "exit", "custom"];
const STEP_TYPES = ["approval", "review", "notification", "action", "condition", "parallel"];
const ASSIGNEE_TYPES = ["role", "user", "manager", "reporting_manager", "department_head"];
const TIMEOUT_ACTIONS = ["escalate", "auto_approve", "auto_reject"];
const CONDITION_FIELDS = ["amount", "leave_days", "days_count", "department", "role", "employee_type", "location", "requires_hr"];
const SAFE_ACTION_FIELDS: Record<string, string[]> = {
  leave: ["status", "review_remarks"],
  attendance: ["status", "manager_remarks", "hr_remarks"],
  expense: ["status", "approval_notes", "finance_notes"],
  payroll: ["status", "approval_status", "remarks"],
  reimbursement: ["status", "approval_status", "payment_status", "remarks"],
  employee: ["status", "probation_status", "work_location", "background_verification_status"],
};

const moduleColors: Record<string, string> = {
  employee: "bg-blue-100 text-blue-800",
  leave: "bg-green-100 text-green-800",
  payroll: "bg-purple-100 text-purple-800",
  recruitment: "bg-orange-100 text-orange-800",
  onboarding: "bg-teal-100 text-teal-800",
  helpdesk: "bg-red-100 text-red-800",
  attendance: "bg-yellow-100 text-yellow-800",
  expense: "bg-indigo-100 text-indigo-800",
  exit: "bg-gray-100 text-gray-800",
  custom: "bg-pink-100 text-pink-800",
};

export default function WorkflowDesignerPage() {
  usePageTitle("Workflow Designer");
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [selectedDefinitionId, setSelectedDefinitionId] = useState<number | null>(null);
  const [selectedStepId, setSelectedStepId] = useState<number | null>(null);
  const [newOpen, setNewOpen] = useState(false);
  const [definitionName, setDefinitionName] = useState("");
  const [isDirty, setIsDirty] = useState(false);
  const [dragFromIndex, setDragFromIndex] = useState<number | null>(null);
  const [dragToIndex, setDragToIndex] = useState<number | null>(null);
  const [stepToDelete, setStepToDelete] = useState<WorkflowStep | null>(null);
  const cardRefs = useRef<Array<HTMLDivElement | null>>([]);

  const definitionsQuery = useQuery({
    queryKey: ["workflow-definitions"],
    queryFn: () => workflowDefinitionsApi.list().then((r) => r.data as WorkflowDefinition[]),
  });
  const stepsQuery = useQuery({
    queryKey: ["workflow-steps", selectedDefinitionId],
    queryFn: () => workflowDefinitionsApi.steps(selectedDefinitionId!).then((r) => r.data as WorkflowStep[]),
    enabled: !!selectedDefinitionId,
  });

  const definitions = definitionsQuery.data || [];
  const selectedDefinition = definitions.find((item) => item.id === selectedDefinitionId) || null;
  const steps = useMemo(() => [...(stepsQuery.data || selectedDefinition?.steps || [])].sort((a, b) => a.step_order - b.step_order), [stepsQuery.data, selectedDefinition]);
  const selectedStep = steps.find((step) => step.id === selectedStepId) || null;
  const filteredDefinitions = definitions.filter((item) => item.name.toLowerCase().includes(search.toLowerCase()));
  const validationWarnings = useMemo(() => workflowWarnings(selectedDefinition, steps), [selectedDefinition, steps]);

  useEffect(() => {
    if (!selectedDefinitionId && definitions.length) setSelectedDefinitionId(definitions[0].id);
  }, [definitions, selectedDefinitionId]);

  useEffect(() => {
    setDefinitionName(selectedDefinition?.name || "");
    setIsDirty(false);
    setSelectedStepId(null);
  }, [selectedDefinition?.id]);

  useEffect(() => {
    if (dragFromIndex === null) return;
    const onMove = (event: MouseEvent) => {
      const index = cardRefs.current.findIndex((node) => {
        if (!node) return false;
        const rect = node.getBoundingClientRect();
        return event.clientY < rect.top + rect.height / 2;
      });
      setDragToIndex(index === -1 ? steps.length : Math.max(0, index));
    };
    const onUp = () => {
      if (dragToIndex !== null && dragFromIndex !== null && dragToIndex !== dragFromIndex) {
        const reordered = [...steps];
        const [moved] = reordered.splice(dragFromIndex, 1);
        reordered.splice(Math.min(dragToIndex, reordered.length), 0, moved);
        reorderSteps.mutate(reordered.map((step, index) => ({ step_id: step.id, step_order: index + 1 })));
      }
      setDragFromIndex(null);
      setDragToIndex(null);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, [dragFromIndex, dragToIndex, steps]);

  const invalidateDefinitions = () => qc.invalidateQueries({ queryKey: ["workflow-definitions"] });
  const invalidateSteps = () => qc.invalidateQueries({ queryKey: ["workflow-steps", selectedDefinitionId] });

  const createDefinition = useMutation({
    mutationFn: (data: Partial<WorkflowDefinition>) => workflowDefinitionsApi.create(data),
    onSuccess: (response) => {
      const created = response.data as WorkflowDefinition;
      toast({ title: "Workflow created" });
      setSelectedDefinitionId(created.id);
      setNewOpen(false);
      invalidateDefinitions();
    },
    onError: () => toast({ title: "Unable to create workflow", variant: "destructive" }),
  });
  const updateDefinition = useMutation({
    mutationFn: (data: Partial<WorkflowDefinition>) => workflowDefinitionsApi.update(selectedDefinitionId!, data),
    onSuccess: () => {
      toast({ title: "Workflow saved" });
      setIsDirty(false);
      invalidateDefinitions();
    },
    onError: () => toast({ title: "Unable to save workflow", variant: "destructive" }),
  });
  const deleteDefinition = useMutation({
    mutationFn: (id: number) => workflowDefinitionsApi.delete(id),
    onSuccess: () => {
      toast({ title: "Workflow deleted" });
      setSelectedDefinitionId(null);
      invalidateDefinitions();
    },
  });
  const toggleDefinition = useMutation({
    mutationFn: () => workflowDefinitionsApi.toggleActive(selectedDefinitionId!),
    onSuccess: () => {
      toast({ title: "Workflow status updated" });
      invalidateDefinitions();
    },
  });
  const createStep = useMutation({
    mutationFn: (order: number) => workflowDefinitionsApi.createStep(selectedDefinitionId!, defaultStep(order)),
    onSuccess: (response) => {
      toast({ title: "Step added" });
      setSelectedStepId((response.data as WorkflowStep).id);
      invalidateSteps();
    },
  });
  const deleteStep = useMutation({
    mutationFn: (stepId: number) => workflowDefinitionsApi.deleteStep(selectedDefinitionId!, stepId),
    onSuccess: () => {
      toast({ title: "Step deleted" });
      setSelectedStepId(null);
      setStepToDelete(null);
      invalidateSteps();
    },
  });
  const reorderSteps = useMutation({
    mutationFn: (payload: Array<{ step_id: number; step_order: number }>) => workflowDefinitionsApi.reorderSteps(selectedDefinitionId!, payload),
    onSuccess: () => {
      toast({ title: "Steps reordered" });
      invalidateSteps();
    },
  });

  return (
    <div className="flex h-[calc(100vh-7rem)] overflow-hidden rounded-lg border bg-background">
      <aside className="flex w-[260px] shrink-0 flex-col border-r bg-muted/20">
        <div className="border-b p-3">
          <div className="flex items-center justify-between gap-2">
            <h1 className="font-semibold">Workflows</h1>
            <Button size="sm" onClick={() => setNewOpen(true)}><Plus className="mr-1 h-4 w-4" />New</Button>
          </div>
          <div className="relative mt-3">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input className="pl-8" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search" />
          </div>
        </div>
        <div className="flex-1 space-y-2 overflow-y-auto p-3">
          {definitionsQuery.isLoading && <div className="h-28 animate-pulse rounded bg-muted" />}
          {filteredDefinitions.map((definition) => (
            <DefinitionCard
              key={definition.id}
              definition={definition}
              selected={definition.id === selectedDefinitionId}
              onSelect={() => setSelectedDefinitionId(definition.id)}
              onDuplicate={() => createDefinition.mutate({ ...definition, name: `${definition.name} Copy` })}
              onDelete={() => deleteDefinition.mutate(definition.id)}
              onToggle={() => { setSelectedDefinitionId(definition.id); setTimeout(() => toggleDefinition.mutate(), 0); }}
            />
          ))}
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-14 items-center justify-between gap-3 border-b px-4">
          {selectedDefinition ? (
            <>
              <div className="flex min-w-0 items-center gap-2">
                <Input
                  value={definitionName}
                  onChange={(e) => { setDefinitionName(e.target.value); setIsDirty(true); }}
                  onBlur={() => isDirty && updateDefinition.mutate({ name: definitionName })}
                  className="h-9 max-w-xs border-transparent bg-transparent text-base font-semibold"
                />
                <ModuleBadge module={selectedDefinition.module} />
                <Badge variant="outline">v{selectedDefinition.version || 1}</Badge>
              </div>
              <div className="flex items-center gap-2">
                <Switch checked={selectedDefinition.is_active} onChange={() => toggleDefinition.mutate()} />
                {isDirty && <Button size="sm" onClick={() => updateDefinition.mutate({ name: definitionName })}><Save className="mr-2 h-4 w-4" />Save All</Button>}
              </div>
            </>
          ) : <span className="text-sm text-muted-foreground">No workflow selected</span>}
        </div>

        <div className="flex-1 overflow-auto bg-muted/10 p-6">
          {!selectedDefinition ? (
            <div className="flex h-full items-center justify-center text-center text-muted-foreground">Select a workflow to design it, or create a new one.</div>
          ) : (
            <div className="mx-auto max-w-3xl space-y-4">
              <div className="rounded-xl border-2 border-dashed border-primary/40 bg-primary/5 p-4">
                <p className="text-sm text-muted-foreground">Trigger</p>
                <div className="mt-1 flex items-center gap-2"><GitBranch className="h-5 w-5 text-primary" /><p className="font-semibold">{selectedDefinition.trigger_event}</p><ModuleBadge module={selectedDefinition.module} /></div>
              </div>
              {validationWarnings.length ? (
                <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                  <div className="mb-2 flex items-center gap-2 font-medium"><AlertTriangle className="h-4 w-4" />Activation warnings</div>
                  <ul className="space-y-1">
                    {validationWarnings.map((warning) => <li key={warning}>{warning}</li>)}
                  </ul>
                </div>
              ) : null}
              <Connector onAdd={() => createStep.mutate(1)} active={dragToIndex === 0} />
              {steps.map((step, index) => (
                <div key={step.id}>
                  <div
                    ref={(node) => { cardRefs.current[index] = node; }}
                    onClick={() => setSelectedStepId(step.id)}
                    className={cn("rounded-xl border bg-card p-4 shadow-sm transition-all", selectedStepId === step.id && "border-primary shadow-md", dragFromIndex === index && "opacity-50")}
                  >
                    <div className="flex items-start gap-3">
                      <button type="button" onMouseDown={(event) => { event.preventDefault(); setDragFromIndex(index); setDragToIndex(index); }} className="mt-1 text-muted-foreground"><GripVertical className="h-5 w-5" /></button>
                      <Badge className="mt-0.5">S{index + 1}</Badge>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-medium">{step.name}</p>
                          {!step.is_active && <Badge variant="outline">Inactive</Badge>}
                        </div>
                        <p className="mt-1 text-sm text-muted-foreground">Assigned to: {assigneeText(step)}</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <Badge variant="outline">{step.step_type}</Badge>
                          {step.timeout_hours ? <Badge variant="outline">{step.timeout_hours}h - {step.timeout_action || "escalate"}</Badge> : null}
                          {step.condition_expression && <Badge variant="outline">if: {truncate(step.condition_expression, 34)}</Badge>}
                          {step.skip_if_condition && <Badge variant="outline">skip</Badge>}
                          {step.delegation_value && <Badge variant="outline">delegated</Badge>}
                          {step.action_type && <Badge variant="outline">action</Badge>}
                        </div>
                      </div>
                      <Button size="icon" variant="ghost" onClick={(event) => { event.stopPropagation(); setSelectedStepId(step.id); }}><Edit2 className="h-4 w-4" /></Button>
                      <Button size="icon" variant="ghost" className="text-destructive" onClick={(event) => { event.stopPropagation(); setStepToDelete(step); }}><Trash2 className="h-4 w-4" /></Button>
                    </div>
                  </div>
                  <Connector onAdd={() => createStep.mutate(index + 2)} active={dragToIndex === index + 1} />
                </div>
              ))}
              <div className="rounded-xl border-2 border-dashed bg-muted/50 p-4 text-center text-sm font-medium text-muted-foreground">Approved / Completed</div>
            </div>
          )}
        </div>
      </main>

      <aside className="w-[320px] shrink-0 overflow-y-auto border-l bg-card">
        <StepEditor definitionId={selectedDefinitionId} step={selectedStep} />
      </aside>

      {newOpen && <NewDefinitionDialog onClose={() => setNewOpen(false)} onCreate={(data) => createDefinition.mutate(data)} pending={createDefinition.isPending} />}
      {stepToDelete && (
        <ConfirmDialog
          title="Delete Step?"
          description={`This will permanently remove step ${stepToDelete.step_order} from the workflow.`}
          onCancel={() => setStepToDelete(null)}
          onConfirm={() => deleteStep.mutate(stepToDelete.id)}
          pending={deleteStep.isPending}
        />
      )}
    </div>
  );
}

function StepEditor({ definitionId, step }: { definitionId: number | null; step: WorkflowStep | null }) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState<WorkflowStep | null>(step);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [conditionsOpen, setConditionsOpen] = useState(false);
  const [delegationOpen, setDelegationOpen] = useState(false);
  const [actionOpen, setActionOpen] = useState(false);

  useEffect(() => setDraft(step), [step?.id]);

  const update = useMutation({
    mutationFn: (payload: WorkflowStep) => workflowDefinitionsApi.updateStep(definitionId!, payload.id, stepPayload(payload)),
    onMutate: () => { setSaving(true); setSaved(false); },
    onSuccess: () => {
      setSaving(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      qc.invalidateQueries({ queryKey: ["workflow-steps", definitionId] });
    },
    onError: () => {
      setSaving(false);
      toast({ title: "Save failed", variant: "destructive" });
    },
  });

  useEffect(() => {
    if (!draft || !step || JSON.stringify(draft) === JSON.stringify(step)) return;
    const timer = setTimeout(() => update.mutate(draft), 500);
    return () => clearTimeout(timer);
  }, [draft]);

  if (!step || !draft) return <div className="p-4 text-sm text-muted-foreground">Click a step to edit it, or press + to add a new step.</div>;

  const patch = (changes: Partial<WorkflowStep>) => setDraft((current) => current ? { ...current, ...changes } : current);

  return (
    <div className="space-y-5 p-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Step Editor</h2>
        <span className="text-xs text-muted-foreground">{saving ? "Saving..." : saved ? <span className="inline-flex items-center text-green-600"><Check className="mr-1 h-3 w-3" />Saved</span> : ""}</span>
      </div>
      <Section title="Basic">
        <Field label="Name"><Input value={draft.name} onChange={(e) => patch({ name: e.target.value })} /></Field>
        <Field label="Description"><textarea rows={3} className="w-full rounded-md border bg-background px-3 py-2 text-sm" value={draft.description || ""} onChange={(e) => patch({ description: e.target.value })} /></Field>
        <Field label="Step Type"><Select value={draft.step_type} options={STEP_TYPES} onChange={(value) => patch({ step_type: value })} /></Field>
      </Section>
      <Section title="Assignment">
        <Field label="Assignee Type"><Select value={draft.assignee_type} options={ASSIGNEE_TYPES} onChange={(value) => patch({ assignee_type: value })} /></Field>
        {draft.assignee_type === "role" && <Field label="Role Name"><Input value={draft.assignee_role || ""} onChange={(e) => patch({ assignee_role: e.target.value })} placeholder="hr_manager" /></Field>}
        {draft.assignee_type === "user" && <Field label="User ID"><Input type="number" value={draft.assignee_user_id || ""} onChange={(e) => patch({ assignee_user_id: e.target.value ? Number(e.target.value) : null })} /></Field>}
      </Section>
      <Section title="Timing">
        <Field label="Timeout (hours)"><Input type="number" value={draft.timeout_hours || ""} onChange={(e) => patch({ timeout_hours: e.target.value ? Number(e.target.value) : null })} /></Field>
        {draft.timeout_hours ? <Field label="Timeout Action"><Select value={draft.timeout_action || "escalate"} options={TIMEOUT_ACTIONS} onChange={(value) => patch({ timeout_action: value })} /></Field> : null}
        {draft.timeout_action === "escalate" ? (
          <div className="grid grid-cols-2 gap-2">
            <Field label="Escalate User ID"><Input type="number" value={draft.escalation_user_id || ""} onChange={(e) => patch({ escalation_user_id: e.target.value ? Number(e.target.value) : null })} /></Field>
            <Field label="Escalate Role"><Input value={draft.escalation_role || ""} onChange={(e) => patch({ escalation_role: e.target.value || null })} placeholder="hr_manager" /></Field>
          </div>
        ) : null}
        <Field label="Reminder (hours before timeout)"><Input type="number" value={draft.reminder_hours || ""} onChange={(e) => patch({ reminder_hours: e.target.value ? Number(e.target.value) : null })} /></Field>
      </Section>
      <div>
        <button type="button" className="mb-3 text-sm font-semibold" onClick={() => setConditionsOpen(!conditionsOpen)}>Conditions</button>
        {conditionsOpen && (
          <div className="space-y-3">
            <Field label="Condition Expression"><textarea rows={3} className="w-full rounded-md border bg-background px-3 py-2 text-sm" value={draft.condition_expression || ""} onChange={(e) => patch({ condition_expression: e.target.value })} placeholder="e.g. leave_days > 3 or department == 'Engineering'" /></Field>
            <Field label="Skip If Condition"><textarea rows={3} className="w-full rounded-md border bg-background px-3 py-2 text-sm" value={draft.skip_if_condition || ""} onChange={(e) => patch({ skip_if_condition: e.target.value })} placeholder="e.g. employee.probation == true" /></Field>
            <p className="text-xs text-muted-foreground">Allowed fields: {CONDITION_FIELDS.join(", ")}. Use comparisons joined with and/or.</p>
          </div>
        )}
      </div>
      <div>
        <button type="button" className="mb-3 text-sm font-semibold" onClick={() => setDelegationOpen(!delegationOpen)}>Delegation</button>
        {delegationOpen && (
          <div className="space-y-3">
            <Field label="Delegate Type"><Select value={draft.delegation_type || "Role"} options={["Role", "User"]} onChange={(value) => patch({ delegation_type: value })} /></Field>
            <Field label="Delegate Value"><Input value={draft.delegation_value || ""} onChange={(e) => patch({ delegation_value: e.target.value || null })} placeholder={draft.delegation_type === "User" ? "user id" : "backup_hr_manager"} /></Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Starts"><Input type="datetime-local" value={toLocalInput(draft.delegation_starts_at)} onChange={(e) => patch({ delegation_starts_at: fromLocalInput(e.target.value) })} /></Field>
              <Field label="Ends"><Input type="datetime-local" value={toLocalInput(draft.delegation_ends_at)} onChange={(e) => patch({ delegation_ends_at: fromLocalInput(e.target.value) })} /></Field>
            </div>
          </div>
        )}
      </div>
      <div>
        <button type="button" className="mb-3 text-sm font-semibold" onClick={() => setActionOpen(!actionOpen)}>Action Step</button>
        {actionOpen && (
          <ActionEditor draft={draft} patch={patch} />
        )}
      </div>
      <Section title="Status">
        <div className="flex items-center justify-between"><Label>Is Active</Label><Switch checked={draft.is_active} onChange={() => patch({ is_active: !draft.is_active })} /></div>
      </Section>
    </div>
  );
}

function ActionEditor({ draft, patch }: { draft: WorkflowStep; patch: (changes: Partial<WorkflowStep>) => void }) {
  const config = draft.action_config || { target_module: "leave", fields: {} };
  const module = config.target_module || "leave";
  const fields = config.fields || {};
  const safeFields = SAFE_ACTION_FIELDS[module] || [];
  const firstField = safeFields[0] || "status";
  const [fieldName, setFieldName] = useState(firstField);
  const [fieldValue, setFieldValue] = useState("");
  const updateConfig = (next: typeof config) => patch({ step_type: "action", action_type: "field_update", action_config: next });
  return (
    <div className="space-y-3">
      <Field label="Target Module"><Select value={module} options={Object.keys(SAFE_ACTION_FIELDS)} onChange={(value) => updateConfig({ ...config, target_module: value, fields: {} })} /></Field>
      <Field label="Target Record ID"><Input type="number" value={config.target_id || ""} onChange={(e) => updateConfig({ ...config, target_id: e.target.value ? Number(e.target.value) : undefined })} placeholder="Defaults to workflow entity" /></Field>
      <div className="grid grid-cols-[1fr_1fr_auto] gap-2">
        <Select value={fieldName} options={safeFields} onChange={setFieldName} />
        <Input value={fieldValue} onChange={(e) => setFieldValue(e.target.value)} placeholder="new value" />
        <Button type="button" variant="outline" onClick={() => { updateConfig({ ...config, fields: { ...fields, [fieldName]: fieldValue } }); setFieldValue(""); }}>Add</Button>
      </div>
      <div className="space-y-1">
        {Object.entries(fields).map(([key, value]) => (
          <div key={key} className="flex items-center justify-between rounded-md bg-muted/60 px-2 py-1 text-xs">
            <span>{key}: {String(value)}</span>
            <button type="button" className="text-destructive" onClick={() => {
              const nextFields = { ...fields };
              delete nextFields[key];
              updateConfig({ ...config, fields: nextFields });
            }}>Remove</button>
          </div>
        ))}
      </div>
    </div>
  );
}

function DefinitionCard({ definition, selected, onSelect, onDuplicate, onDelete, onToggle }: { definition: WorkflowDefinition; selected: boolean; onSelect: () => void; onDuplicate: () => void; onDelete: () => void; onToggle: () => void }) {
  const [menu, setMenu] = useState(false);
  return (
    <div className="relative">
      <button type="button" onClick={onSelect} className={cn("w-full rounded-lg border bg-card p-3 text-left hover:bg-muted/60", selected && "border-primary bg-primary/10")}>
        <div className="flex items-start justify-between gap-2">
          <p className="truncate text-sm font-medium">{definition.name}</p>
          <span className={cn("mt-1 h-2 w-2 rounded-full", definition.is_active ? "bg-green-500" : "bg-gray-400")} />
        </div>
        <div className="mt-2 flex items-center justify-between"><ModuleBadge module={definition.module} /><span className="text-xs text-muted-foreground">{definition.steps?.length || 0} steps</span></div>
      </button>
      <Button size="icon" variant="ghost" className="absolute right-1 top-1 h-7 w-7" onClick={() => setMenu(!menu)}><MoreHorizontal className="h-4 w-4" /></Button>
      {menu && <div className="absolute right-1 top-9 z-10 w-36 rounded-md border bg-popover p-1 shadow"><MenuItem icon={Edit2} label="Rename" onClick={onSelect} /><MenuItem icon={Copy} label="Duplicate" onClick={onDuplicate} /><MenuItem icon={GitBranch} label="Toggle Active" onClick={onToggle} /><MenuItem icon={Trash2} label="Delete" onClick={onDelete} danger /></div>}
    </div>
  );
}

function Connector({ onAdd, active }: { onAdd: () => void; active?: boolean }) {
  return <div className={cn("relative mx-auto h-10 w-px bg-border", active && "bg-blue-500")}><Button type="button" size="icon" variant="outline" className="absolute left-1/2 top-1/2 h-7 w-7 -translate-x-1/2 -translate-y-1/2 rounded-full bg-background" onClick={onAdd}><Plus className="h-3 w-3" /></Button></div>;
}

function NewDefinitionDialog({ onClose, onCreate, pending }: { onClose: () => void; onCreate: (data: Partial<WorkflowDefinition>) => void; pending: boolean }) {
  const [form, setForm] = useState({ name: "", module: "leave", trigger_event: "on_submit", description: "" });
  return (
    <Modal title="New Workflow" onClose={onClose}>
      <div className="space-y-4">
        <Field label="Name"><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <Field label="Module"><Select value={form.module} options={MODULES} onChange={(value) => setForm({ ...form, module: value })} /></Field>
        <Field label="Trigger Event"><Input value={form.trigger_event} onChange={(e) => setForm({ ...form, trigger_event: e.target.value })} /></Field>
        <Field label="Description"><textarea rows={3} className="w-full rounded-md border bg-background px-3 py-2 text-sm" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
        <div className="flex justify-end gap-2"><Button variant="outline" onClick={onClose}>Cancel</Button><Button disabled={!form.name || pending} onClick={() => onCreate(form)}>Save</Button></div>
      </div>
    </Modal>
  );
}

function ConfirmDialog({ title, description, onCancel, onConfirm, pending }: { title: string; description: string; onCancel: () => void; onConfirm: () => void; pending: boolean }) {
  return <Modal title={title} onClose={onCancel}><p className="text-sm text-muted-foreground">{description}</p><div className="mt-5 flex justify-end gap-2"><Button variant="outline" onClick={onCancel}>Cancel</Button><Button className="bg-destructive text-destructive-foreground hover:bg-destructive/90" disabled={pending} onClick={onConfirm}>Delete</Button></div></Modal>;
}

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"><div className="w-full max-w-md rounded-lg bg-background p-5 shadow-lg"><div className="mb-4 flex items-center justify-between"><h2 className="font-semibold">{title}</h2><Button variant="ghost" size="sm" onClick={onClose}>Close</Button></div>{children}</div></div>;
}

function Switch({ checked, onChange }: { checked: boolean; onChange: () => void }) {
  return <button type="button" onClick={onChange} className={cn("h-6 w-11 rounded-full p-0.5 transition-colors", checked ? "bg-primary" : "bg-muted-foreground/30")}><span className={cn("block h-5 w-5 rounded-full bg-background transition-transform", checked && "translate-x-5")} /></button>;
}

function Select({ value, options, onChange }: { value: string; options: string[]; onChange: (value: string) => void }) {
  return <select value={value || options[0]} onChange={(e) => onChange(e.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">{options.map((option) => <option key={option} value={option}>{option.replace(/_/g, " ")}</option>)}</select>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="space-y-1.5"><Label>{label}</Label>{children}</div>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="space-y-3"><h3 className="text-sm font-semibold">{title}</h3>{children}</section>;
}

function MenuItem({ icon: Icon, label, onClick, danger }: { icon: any; label: string; onClick: () => void; danger?: boolean }) {
  return <button type="button" onClick={onClick} className={cn("flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted", danger && "text-destructive")}><Icon className="h-4 w-4" />{label}</button>;
}

function ModuleBadge({ module }: { module: string }) {
  return <Badge className={cn("border-0 capitalize", moduleColors[module] || "bg-muted text-muted-foreground")}>{module}</Badge>;
}

function defaultStep(order: number) {
  return { step_order: order, name: `Approval Step ${order}`, step_type: "approval", assignee_type: "role", assignee_role: "hr_manager", timeout_hours: 48, timeout_action: "escalate", reminder_hours: 24, is_active: true };
}

function stepPayload(step: WorkflowStep) {
  return {
    step_order: step.step_order,
    name: step.name,
    step_type: step.step_type,
    assignee_type: step.assignee_type,
    assignee_role: step.assignee_role || null,
    assignee_user_id: step.assignee_user_id || null,
    timeout_hours: step.timeout_hours || null,
    timeout_action: step.timeout_action || "escalate",
    condition_expression: step.condition_expression || null,
    skip_if_condition: step.skip_if_condition || null,
    reminder_hours: step.reminder_hours || null,
    escalation_user_id: step.escalation_user_id || null,
    escalation_role: step.escalation_role || null,
    action_type: step.action_type || null,
    action_config: step.action_config || null,
    delegation_type: step.delegation_type || null,
    delegation_value: step.delegation_value || null,
    delegation_starts_at: step.delegation_starts_at || null,
    delegation_ends_at: step.delegation_ends_at || null,
    is_active: step.is_active,
    description: step.description || null,
  };
}

function assigneeText(step: WorkflowStep) {
  if (step.assignee_type === "role") return step.assignee_role || "role";
  if (step.assignee_type === "user") return `User #${step.assignee_user_id || "-"}`;
  return step.assignee_type.replace(/_/g, " ");
}

function truncate(value: string, length: number) {
  return value.length > length ? `${value.slice(0, length)}...` : value;
}

function workflowWarnings(definition: WorkflowDefinition | null, steps: WorkflowStep[]) {
  const warnings: string[] = [];
  if (!definition) return warnings;
  if (!steps.some((step) => step.is_active)) warnings.push("Add at least one active step before activation.");
  steps.forEach((step, index) => {
    const label = `Step ${index + 1}`;
    if (["approval", "review", "parallel"].includes(step.step_type) && !step.assignee_role && !step.assignee_user_id && ["role", "user"].includes(step.assignee_type)) {
      warnings.push(`${label} needs an approver role or user.`);
    }
    if (step.timeout_action === "escalate" && step.timeout_hours && !step.escalation_user_id && !step.escalation_role) {
      warnings.push(`${label} escalates on timeout but has no escalation target.`);
    }
    if (step.delegation_value && (!step.delegation_starts_at || !step.delegation_ends_at)) {
      warnings.push(`${label} delegation should include start and end dates.`);
    }
    if (step.step_type === "action" && (!step.action_config?.fields || !Object.keys(step.action_config.fields).length)) {
      warnings.push(`${label} action step needs at least one safe field update.`);
    }
  });
  return warnings;
}

function toLocalInput(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function fromLocalInput(value: string) {
  return value ? new Date(value).toISOString() : null;
}

import TemplateSteps from "./TemplateSteps";
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ClipboardCheck, Plus, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { employeeApi, onboardingApi } from "@/services/api";
import { toast } from "@/hooks/use-toast";
import { usePageTitle } from "@/hooks/use-page-title";
import { formatDate } from "@/lib/utils";

export default function OnboardingPage() {
  usePageTitle("Onboarding");
  const qc = useQueryClient();
  const [templateName, setTemplateName] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [startDate, setStartDate] = useState(new Date().toISOString().slice(0, 10));

  const templates = useQuery({ queryKey: ["onboarding-templates"], queryFn: () => onboardingApi.templates().then((r) => r.data) });
  const onboardings = useQuery({ queryKey: ["onboarding-employees"], queryFn: () => onboardingApi.employees().then((r) => r.data) });
  const employees = useQuery({ queryKey: ["onboarding-employee-options"], queryFn: () => employeeApi.list({ per_page: 100 }).then((r) => r.data.items) });

  const createTemplate = useMutation({
    mutationFn: () => onboardingApi.createTemplate({ name: templateName, description: "Created from onboarding page" }),
    onSuccess: () => {
      toast({ title: "Template created" });
      setTemplateName("");
      qc.invalidateQueries({ queryKey: ["onboarding-templates"] });
    },
    onError: () => toast({ title: "Could not create template", variant: "destructive" }),
  });

  const start = useMutation({
    mutationFn: () => onboardingApi.start({
      employee_id: Number(employeeId),
      template_id: templateId ? Number(templateId) : undefined,
      start_date: startDate,
    }),
    onSuccess: () => {
      toast({ title: "Onboarding started" });
      setEmployeeId("");
      qc.invalidateQueries({ queryKey: ["onboarding-employees"] });
    },
    onError: () => toast({ title: "Could not start onboarding", variant: "destructive" }),
  });

  const complete = useMutation({
    mutationFn: (id: number) => onboardingApi.complete(id),
    onSuccess: () => {
      toast({ title: "Onboarding completed" });
      qc.invalidateQueries({ queryKey: ["onboarding-employees"] });
    },
  });

  function submitTemplate(event: FormEvent) {
    event.preventDefault();
    createTemplate.mutate();
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 rounded-lg border bg-card p-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Onboarding</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">New hire onboarding</h1>
          <p className="mt-1 text-sm text-muted-foreground">Create templates, start onboarding, and complete joining workflows.</p>
        </div>
        <Button variant="outline" onClick={() => { templates.refetch(); onboardings.refetch(); }}><RefreshCw className="h-4 w-4" />Refresh</Button>
      </div>

      <div className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
        <div className="space-y-5">
          <Card>
            <CardHeader><CardTitle className="text-base">Template</CardTitle><CardDescription>Create reusable onboarding plans.</CardDescription></CardHeader>
            <CardContent>
              <form onSubmit={submitTemplate} className="flex gap-2">
                <Input value={templateName} onChange={(e) => setTemplateName(e.target.value)} placeholder="Engineering joining checklist" required />
                <Button type="submit"><Plus className="h-4 w-4" />Add</Button>
              </form>
              <div className="mt-4 space-y-2">
                {templates.data?.map((t: any) => <TemplateSteps key={t.id} template={t} refresh={() => templates.refetch()} />)}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Start onboarding</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <Label>Employee</Label>
                <select value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                  <option value="">Select employee</option>
                  {employees.data?.map((e: any) => <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>)}
                </select>
              </div>
              <div className="space-y-2">
                <Label>Template</Label>
                <select value={templateId} onChange={(e) => setTemplateId(e.target.value)} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                  <option value="">No template</option>
                  {templates.data?.map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </div>
              <div className="space-y-2"><Label>Start date</Label><Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></div>
              <Button onClick={() => start.mutate()} disabled={!employeeId || start.isPending}>Start</Button>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader><CardTitle className="text-base">Employee onboarding</CardTitle><CardDescription>{onboardings.data?.length ?? 0} records</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {onboardings.data?.map((item: any) => (
              <div key={item.id} className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary"><ClipboardCheck className="h-5 w-5" /></div>
                  <div>
                    <p className="font-medium">Employee #{item.employee_id}</p>
                    <p className="text-sm text-muted-foreground">Start {formatDate(item.start_date)} â€¢ Expected {formatDate(item.expected_completion_date)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={item.status === "Completed" ? "success" : "warning"}>{item.status}</Badge>
                  {item.status !== "Completed" && <Button size="sm" variant="outline" onClick={() => complete.mutate(item.id)}><CheckCircle2 className="h-4 w-4" />Complete</Button>}
                </div>
              </div>
            ))}
            {!onboardings.isLoading && !onboardings.data?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No onboarding records yet.</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

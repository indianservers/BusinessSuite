import { useMobile } from "@/components/mobile/useMobile";
import { SmartCreateModal } from "@/shared/creation/SmartCreateModal";
import "./onboarding-mobile.css";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import { standardRecordGroups } from "@/shared/data-grid/record-group-fields";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import TemplateSteps from "./TemplateSteps";
import { FormEvent, useRef, useState } from "react";
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
  const phone = useMobile(480);
  const [section, setSection] = useState("records");
  const [templateOpen, setTemplateOpen] = useState(false);
  const [startOpen, setStartOpen] = useState(false);
  const [templateError, setTemplateError] = useState("");
  const [startError, setStartError] = useState("");
  const [completeError, setCompleteError] = useState("");
  const templateOpener = useRef<HTMLButtonElement | null>(null);
  const startOpener = useRef<HTMLButtonElement | null>(null);
  const [templateName, setTemplateName] = useState("");
  const [employeeId, setEmployeeId] = useState(()=>new URLSearchParams(window.location.search).get("employeeId")||"");
  const [templateId, setTemplateId] = useState("");
  const [startDate, setStartDate] = useState(new Date().toISOString().slice(0, 10));
  const startSnapshot = useRef({ employeeId, templateId, startDate });

  const templates = useQuery({ queryKey: ["onboarding-templates"], queryFn: () => onboardingApi.templates().then((r) => r.data) });
  const onboardings = useQuery({ queryKey: ["onboarding-employees"], queryFn: () => onboardingApi.employees().then((r) => r.data) });
  const employees = useQuery({ queryKey: ["onboarding-employee-options"], queryFn: () => employeeApi.list({ per_page: 100 }).then((r) => r.data.items) });

  const createTemplate = useMutation({
    onMutate: () => {if(phone)setTemplateError("");},
    mutationFn: () => onboardingApi.createTemplate({ name: templateName, description: "Created from onboarding page" }),
    onSuccess: () => {
      toast({ title: "Template created" });
      if(phone)setTemplateOpen(false);
      setTemplateName("");
      qc.invalidateQueries({ queryKey: ["onboarding-templates"] });
    },
    onError: () => {if(phone)setTemplateError("Could not create template. Your name is retained; try Add again.");toast({ title: "Could not create template", variant: "destructive" });},
  });

  const start = useMutation({
    onMutate: () => {if(phone)setStartError("");},
    mutationFn: () => onboardingApi.start({
      employee_id: Number(employeeId),
      template_id: templateId ? Number(templateId) : undefined,
      start_date: startDate,
    }),
    onSuccess: () => {
      toast({ title: "Onboarding started" });
      if(phone)setStartOpen(false);
      setEmployeeId("");
      qc.invalidateQueries({ queryKey: ["onboarding-employees"] });
    },
    onError: () => {if(phone)setStartError("Could not start onboarding. Your choices are retained; try Start again.");toast({ title: "Could not start onboarding", variant: "destructive" });},
  });

  const complete = useMutation({
    onMutate: () => {if(phone)setCompleteError("");},
    onError: () => {if(phone)setCompleteError("Could not complete onboarding. Try Complete again.");},
    mutationFn: (id: number) => onboardingApi.complete(id),
    onSuccess: () => {
      toast({ title: "Onboarding completed" });
      qc.invalidateQueries({ queryKey: ["onboarding-employees"] });
    },
  });

  function submitTemplate(event: FormEvent) {
    event.preventDefault();
    if(!phone || !createTemplate.isPending)createTemplate.mutate();
  }

  const templateForm = (
<CompactForm compactTabs={phone?false:undefined} onSubmit={submitTemplate} className="hrms-onboarding-template-form flex gap-2">
                <Input aria-label={phone?"Template name":undefined} disabled={phone && createTemplate.isPending} value={templateName} onChange={(e) => setTemplateName(e.target.value)} placeholder="Engineering joining checklist" required />
                {phone && templateError && <p role="alert">{templateError}</p>}<Button data-save-action={phone||undefined} aria-busy={phone && createTemplate.isPending || undefined} disabled={phone && createTemplate.isPending} type="submit"><Plus className="h-4 w-4" />{phone && createTemplate.isPending?"Creating…":"Add"}</Button>
              </CompactForm>
  );
  const startForm = (
<Card className="hrms-onboarding-start">
            <CardHeader><CardTitle className="text-base">Start onboarding</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {phone && employees.isError && <p role="alert">Employee choices could not load. <Button disabled={employees.isFetching} variant="outline" onClick={() => void employees.refetch()}>Retry onboarding employees</Button></p>}
              {phone && templates.isError && <p role="alert">Template choices could not load. <Button disabled={templates.isFetching} variant="outline" onClick={() => void templates.refetch()}>Retry onboarding templates</Button></p>}
              <div className="space-y-2">
                <Label>Employee</Label>
                <NativeSelect aria-label={phone?"Onboarding employee":undefined} disabled={phone && start.isPending} loading={employees.isFetching} error={employees.isError} value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                  <option value="">Select employee</option>
                  {employees.data?.map((e: any) => <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>)}
                </NativeSelect>
              </div>
              <div className="space-y-2">
                <Label>Template</Label>
                <NativeSelect aria-label={phone?"Onboarding template":undefined} disabled={phone && start.isPending} loading={templates.isFetching} error={templates.isError} value={templateId} onChange={(e) => setTemplateId(e.target.value)} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                  <option value="">No template</option>
                  {templates.data?.map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </NativeSelect>
              </div>
              <div className="space-y-2"><Label>Start date</Label><Input aria-label={phone?"Onboarding start date":undefined} disabled={phone && start.isPending} type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></div>
              {phone && startError && <p role="alert">{startError}</p>}<Button data-save-action={phone||undefined} aria-busy={phone && start.isPending || undefined} onClick={() => {if(!phone || !start.isPending)start.mutate();}} disabled={!employeeId || start.isPending}>{phone && start.isPending?"Starting…":"Start"}</Button>
            </CardContent>
          </Card>
  );

  return (
    <div className="hrms-onboarding space-y-5">
      <div className="hrms-onboarding-header flex flex-col gap-3 rounded-lg border bg-card p-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Onboarding</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">New hire onboarding</h1>
          <p className="mt-1 text-sm text-muted-foreground">Create templates, start onboarding, and complete joining workflows.</p>
        </div>
        <Button aria-label="Refresh" disabled={phone && (templates.isFetching || onboardings.isFetching)} variant="outline" onClick={() => { templates.refetch(); onboardings.refetch(); }}><RefreshCw className="h-4 w-4" /><span>Refresh</span></Button>
      </div>

      {phone && <><Button onClick={event => {startOpener.current=event.currentTarget;startSnapshot.current={employeeId,templateId,startDate};setStartError("");setStartOpen(true);}}>Start onboarding</Button>{startOpen && <SmartCreateModal definition={{entity:"onboarding-start",title:"Start onboarding",presentation:"page",size:"compact"}} mobileSheet busy={start.isPending} returnFocus={startOpener.current} onClose={() => {setStartOpen(false);setStartError("");setEmployeeId(startSnapshot.current.employeeId);setTemplateId(startSnapshot.current.templateId);setStartDate(startSnapshot.current.startDate);}}>{startForm}</SmartCreateModal>}<nav className="hrms-onboarding-sections" aria-label="Onboarding sections">{[["records","Records"],["templates","Templates"]].map(([key,label]) => <Button key={key} aria-pressed={section===key} variant={section===key?"default":"outline"} onClick={() => setSection(key)}>{label}</Button>)}</nav></>}
      <div className="hrms-onboarding-layout grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
        <div className="space-y-5" style={phone && section!=="templates"?{display:"none"}:undefined}>
          <Card>
            <CardHeader><CardTitle className="text-base">Template</CardTitle><CardDescription>Create reusable onboarding plans.</CardDescription></CardHeader>
            <CardContent>
              {phone ? <><Button onClick={event => {templateOpener.current=event.currentTarget;setTemplateError("");setTemplateOpen(true);}}><Plus className="h-4 w-4"/>Create onboarding template</Button>{templateOpen && <SmartCreateModal definition={{entity:"onboarding-template",title:"Create onboarding template",presentation:"page",size:"compact"}} mobileSheet busy={createTemplate.isPending} returnFocus={templateOpener.current} onClose={() => {setTemplateOpen(false);setTemplateName("");setTemplateError("");}}>{templateForm}</SmartCreateModal>}</> : <SmartCreateSection title="Create onboarding template" size="compact">{templateForm}</SmartCreateSection>}
              {phone && templates.isLoading && <p role="status">Loading onboarding templates…</p>}
              {phone && templates.isError && <p role="alert">Templates could not load. <Button disabled={templates.isFetching} variant="outline" onClick={() => void templates.refetch()}>Retry templates</Button></p>}
              {!(phone && !templates.data && (templates.isLoading || templates.isError)) && <GroupedRecords scope="apps/hrms/pages/onboarding/OnboardingPage:cards-1" items={(templates.data) || []} fields={standardRecordGroups((templates.data) || [])} gridClassName="mt-4 space-y-2" renderItem={(t: any) => <TemplateSteps key={t.id} template={t} refresh={() => templates.refetch()} />}/>}
              {phone && templates.isSuccess && !templates.data?.length && <p>No onboarding templates yet.</p>}
            </CardContent>
          </Card>

          {!phone && <SmartCreateSection title={<>Start onboarding</>} size="compact">{startForm}</SmartCreateSection>}
        </div>

        <Card className="hrms-onboarding-records" style={phone && section!=="records"?{display:"none"}:undefined}>
          <CardHeader><CardTitle className="text-base">Employee onboarding</CardTitle><CardDescription>{phone && !onboardings.data?"—":onboardings.data?.length ?? 0} records</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {phone && onboardings.isLoading && <p role="status">Loading onboarding records…</p>}
            {phone && onboardings.isError && <p role="alert">Onboarding records could not load. <Button disabled={onboardings.isFetching} variant="outline" onClick={() => void onboardings.refetch()}>Retry onboarding records</Button></p>}
            {phone && completeError && <p role="alert">{completeError}</p>}
            {!(phone && !onboardings.data && (onboardings.isLoading || onboardings.isError)) && <GroupedRecords scope="apps/hrms/pages/onboarding/OnboardingPage:records-1" items={(onboardings.data) || []} fields={standardRecordGroups((onboardings.data) || [])} gridClassName="space-y-3" renderItem={(item: any) => (
              <div key={item.id} className="hrms-onboarding-record flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary"><ClipboardCheck className="h-5 w-5" /></div>
                  <div>
                    <p className="font-medium">Employee #{item.employee_id}</p>
                    <p className="text-sm text-muted-foreground">Start {formatDate(item.start_date)} • Expected {formatDate(item.expected_completion_date)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={item.status === "Completed" ? "success" : "warning"}>{item.status}</Badge>
                  {item.status !== "Completed" && <Button disabled={phone && complete.isPending} size="sm" variant="outline" onClick={() => {if(!phone || !complete.isPending)complete.mutate(item.id);}}><CheckCircle2 className="h-4 w-4" />Complete</Button>}
                </div>
              </div>
            )}/>}
            {!onboardings.isLoading && !(phone && onboardings.isError) && !onboardings.data?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No onboarding records yet.</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

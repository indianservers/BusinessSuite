import {useDefinitionPermission} from "@/components/RecordDefinitionActions";
import RecordMaintenance from "@/components/RecordMaintenance";
import { PhoneInput } from "@/lib/validation/PhoneInput";
import HiringCandidateDetails from "./HiringCandidateDetails";
import PipelineStageEditor, { type EditableStage } from "@/shared/pipeline/PipelineStageEditor";
import { PipelineDrawer } from "@/shared/pipeline/PipelineExperience";
import { api } from "@/services/api";
import GridTable from "@/shared/data-grid/GridTable";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import { recordPreviewProps } from "@/components/RecordQuickPreview";
import PipelineBoard, { PipelineViewSwitch } from "@/shared/pipeline/PipelineBoard";
import { useAuthStore } from "@/store/authStore";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import RichTextEditor, { RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Briefcase, Plus, Users, Calendar, CheckCircle2,
  XCircle, RefreshCw, Eye, ChevronDown
} from "lucide-react";
import { Controller, useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import AskAiButton from "@/components/ai-agents/AskAiButton";
import { recruitmentApi } from "@/services/api";
import { formatDate, statusColor } from "@/lib/utils";
import { usePageTitle } from "@/hooks/use-page-title";
import { toast } from "@/hooks/use-toast";

interface Job {
  id: number;
  title: string;
  department?: { name: string };
  employment_type: string;
  location?: string;
  status: string;
  openings: number;
  posted_date: string;
  applications_count?: number;
}

interface Candidate {
  id: number;
  name: string;
  email: string;
  phone?: string;
  job?: { title: string };
  status: string;
  applied_date: string;
  source?: string;
}

interface JobForm {
  title: string;
  employment_type: string;
  location?: string;
  openings: number;
  description?: string;
  requirements?: string;
}

const CANDIDATE_STATUSES = [
  "Applied","Screening","Interview","Assessment","Offer","Hired","Rejected","Withdrawn"
];

export default function RecruitmentPage() {
  usePageTitle("Recruitment");
  const user = useAuthStore(s=>s.user);
  const canCreate=useDefinitionPermission(["recruitment_manage"],"create"),canManage=useDefinitionPermission(["recruitment_manage"],"edit"),canDelete=useDefinitionPermission(["recruitment_manage"],"delete");
  const canConfigure=useDefinitionPermission(["recruitment_manage"],"configure"),canConvert=useDefinitionPermission(["employee_create"],"create");
  const [candidateView,setCandidateView] = useState<"board"|"list">("board");
  const [pendingMove,setPendingMove] = useState<{id:number;name:string;status:string}>();
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<"jobs" | "candidates">("jobs");
  const [showJobForm, setShowJobForm] = useState(false);
  const [selectedJob, setSelectedJob] = useState<number | "">("");
  const [statusFilter, setStatusFilter] = useState("");
  const [configure,setConfigure]=useState(false),[quickStage,setQuickStage]=useState<string>();
  const [candidateDraft,setCandidateDraft]=useState({first_name:"",last_name:"",email:"",phone:"",phone_country_code:"+91",source:""});
  const [candidateError,setCandidateError]=useState(""),[candidateSaving,setCandidateSaving]=useState(false);
  const hiringConfig=useQuery<{name:string;stages:EditableStage[];version:number}>({queryKey:["hiring-pipeline",selectedJob],enabled:!!selectedJob,queryFn:async()=>(await api.get(`/pipeline-workspaces/hrms/jobs/${selectedJob}/configuration`)).data});
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(null);
  const [converting,setConverting]=useState<Candidate|null>(null);

  const { data: jobs, isLoading: loadingJobs, refetch: refetchJobs } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => recruitmentApi.jobs().then((r) => r.data),
  });

  const { data: candidates, isLoading: loadingCandidates, refetch: refetchCandidates } = useQuery({
    queryKey: ["candidates", selectedJob, statusFilter],
    queryFn: () =>
      recruitmentApi.candidates({
        job_id: selectedJob || undefined,
        status: statusFilter === "Offer" ? undefined : statusFilter || undefined,
      }).then((r) => (r.data as Array<Candidate & {first_name?:string;last_name?:string;applied_at?:string}>).map(c=>({...c,applied_date:c.applied_date||c.applied_at||"",name:c.name || [c.first_name,c.last_name].filter(Boolean).join(" ")})).filter(c=>statusFilter!=="Offer" || c.status==="Offer" || c.status==="Offered")),
  });

  const { control: editorControl, register: registerJob, handleSubmit: handleJobSubmit, reset: resetJob, formState: { errors: jobErrors } } = useForm<JobForm>({
    defaultValues: { openings: 1, employment_type: "Full-time" },
  });

  const createJobMutation = useMutation({
    mutationFn: (data: JobForm) => recruitmentApi.createJob({ ...data, openings: Number(data.openings) }),
    onSuccess: () => {
      toast({ title: "Job posted successfully!" });
      resetJob();
      setShowJobForm(false);
      refetchJobs();
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to create job";
      toast({ title: "Error", description: msg, variant: "destructive" });
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      recruitmentApi.updateCandidateStatus(id, status),
    onError: (e: unknown) => toast({ title: "Could not move candidate", description: (e as {response?:{data?:{detail?:string}}})?.response?.data?.detail || "Please try again.", variant: "destructive" }),
    onSuccess: () => {
      toast({ title: "Status updated" });
      refetchCandidates();
      setSelectedCandidate(null);
    },
  });

  const convertCandidateMutation = useMutation({
    mutationFn: (id: number) => recruitmentApi.convertCandidate(id),
    onSuccess: () => {
      toast({ title: "Candidate converted to employee" });
      refetchCandidates();
      qc.invalidateQueries({ queryKey: ["employees"] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Conversion failed";
      toast({ title: "Error", description: msg, variant: "destructive" });
    },
  });

  const candidateToolbar=<><PipelineViewSwitch view={candidateView} onChange={setCandidateView}/><div className="pipeline-toolbar-end"><NativeSelect aria-label="Hiring job" value={selectedJob} onChange={e=>setSelectedJob(e.target.value?Number(e.target.value):"")}><option value="">All Jobs</option>{(jobs as Job[])?.map(job=><option key={job.id} value={job.id}>{job.title}</option>)}</NativeSelect><NativeSelect aria-label="Candidate status" value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}><option value="">All Statuses</option>{CANDIDATE_STATUSES.map(status=><option key={status} value={status}>{status}</option>)}</NativeSelect><button type="button" className="pipeline-icon-button" aria-label="Refresh candidates" onClick={()=>void refetchCandidates()}><RefreshCw size={15}/></button>{!!selectedJob&&canConfigure&&<button type="button" onClick={()=>setConfigure(true)}>Customize pipeline</button>}</div></>;
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="page-title">Recruitment</h1>
          <p className="page-description">Manage job postings, candidates, and hiring pipeline.</p>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <AskAiButton
            module="HRMS"
            relatedEntityType={activeTab === "candidates" ? "candidate" : "job"}
            relatedEntityId={selectedCandidate?.id || selectedJob || undefined}
            defaultAgentCode="hrms_recruitment_screening"
            defaultPrompt="Screen this candidate against the job requirement."
          />
          {activeTab === "jobs" && (
            <Button size="sm" disabled={!canCreate} onClick={() => setShowJobForm((v) => !v)}>
              <Plus className="h-4 w-4 mr-2" />
              Post Job
            </Button>
          )}
        </div>
      </div>

      {/* Stats */}
      {(activeTab!=="candidates"||candidateView!=="board")&&<div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: "Open Positions", value: (jobs as Job[])?.filter((j) => j.status === "Open").length ?? 0, color: "text-blue-600" },
          { label: "Total Candidates", value: (candidates as Candidate[])?.length ?? 0, color: "text-purple-600" },
          { label: "In Interview", value: (candidates as Candidate[])?.filter((c) => c.status === "Interview").length ?? 0, color: "text-orange-600" },
          { label: "Hired This Month", value: (candidates as Candidate[])?.filter((c) => c.status === "Hired").length ?? 0, color: "text-green-600" },
        ].map((s) => (
          <Card key={s.label}>
            <CardContent className="p-4 text-center">
              <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
              <p className="text-xs text-muted-foreground mt-1">{s.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>}

      {/* Tabs */}
      <div className="flex gap-2 border-b">
        {(["jobs", "candidates"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-2 px-1 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab === "jobs" ? "Job Openings" : "Candidates"}
          </button>
        ))}
      </div>

      {/* Create Job Form */}
      {activeTab === "jobs" && showJobForm && (
        <Card>
          <CardHeader><CardTitle className="text-base">New Job Posting</CardTitle></CardHeader>
          <CardContent>
            <CompactForm
              onSubmit={handleJobSubmit((data) => createJobMutation.mutate(data))}
              className="grid grid-cols-1 sm:grid-cols-2 gap-4"
            >
              <div className="space-y-1.5 sm:col-span-2">
                <Label>Job Title *</Label>
                <Input aria-label="Job title" {...registerJob("title", { required: "Required" })} placeholder="e.g. Senior Software Engineer" />
                {jobErrors.title && <div className="text-xs text-red-500"><RichTextContent legacyFormat="plain" value={jobErrors.title.message}/></div>}
              </div>
              <div className="space-y-1.5">
                <Label>Employment Type</Label>
                <NativeSelect
                  {...registerJob("employment_type")}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  {["Full-time", "Part-time", "Contract", "Internship"].map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </NativeSelect>
              </div>
              <div className="space-y-1.5">
                <Label>Openings</Label>
                <Input type="number" min={1} {...registerJob("openings")} />
              </div>
              <div className="space-y-1.5">
                <Label>Location</Label>
                <Input {...registerJob("location")} placeholder="e.g. Mumbai, Remote" />
              </div>
              <div className="space-y-1.5 sm:col-span-2">
                <Label>Job Description</Label>
                <Controller name="description" control={editorControl} render={({field}) => <RichTextEditor legacyFormat="plain" label="Description" value={field.value || ""} onChange={field.onChange} onBlur={field.onBlur} />}/>
              </div>
              <div className="space-y-1.5 sm:col-span-2">
                <Label>Requirements</Label>
                <Controller name="requirements" control={editorControl} render={({field}) => <RichTextEditor legacyFormat="plain" label="Requirements" value={field.value || ""} onChange={field.onChange} onBlur={field.onBlur} />}/>
              </div>
              <div className="sm:col-span-2 flex gap-3">
                <Button type="submit" disabled={!canCreate || createJobMutation.isPending}>
                  {createJobMutation.isPending ? "Posting..." : "Post Job"}
                </Button>
                <Button type="button" variant="outline" onClick={() => setShowJobForm(false)}>Cancel</Button>
              </div>
            </CompactForm>
          </CardContent>
        </Card>
      )}

      {/* Jobs list */}
      {activeTab === "jobs" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {loadingJobs ? (
            Array.from({ length: 6 }).map((_, i) => (
              <Card key={i}><CardContent className="p-5"><div className="h-24 skeleton rounded" /></CardContent></Card>
            ))
          ) : !(jobs as Job[])?.length ? (
            <Card className="sm:col-span-2 lg:col-span-3">
              <CardContent className="p-12 text-center text-muted-foreground">
                <Briefcase className="h-10 w-10 mx-auto mb-3 opacity-30" />
                <p>No job postings yet. Post your first job!</p>
              </CardContent>
            </Card>
          ) : (
            (jobs as Job[]).map((job) => (
              <Card key={job.id} className="hover:shadow-md transition-shadow">
                <CardContent className="p-5 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-semibold text-sm leading-tight">{job.title}</h3><RecordMaintenance record={job as unknown as Record<string,unknown>} name={job.title} endpoint={`/recruitment/jobs/${job.id}`} fields={[{key:"title",label:"Job title",required:true},{key:"description",label:"Description"},{key:"openings",label:"Openings",type:"number",required:true}]} queryKeys={["jobs"]} canEdit={canManage} canDelete={canDelete}/>
                    <span className={`shrink-0 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(job.status)}`}>
                      {job.status}
                    </span>
                  </div>
                  <div className="space-y-1 text-xs text-muted-foreground">
                    {job.department && <p>{job.department.name}</p>}
                    <p>{job.employment_type} {job.location ? `· ${job.location}` : ""}</p>
                    <p>{job.openings} opening{job.openings !== 1 ? "s" : ""}</p>
                  </div>
                  <div className="flex items-center justify-between pt-1">
                    <span className="text-xs text-muted-foreground">{formatDate(job.posted_date)}</span>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => { setSelectedJob(job.id); setActiveTab("candidates"); }}
                    >
                      <Users className="h-3.5 w-3.5 mr-1" />
                      Candidates
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}

      {/* Candidates tab */}
      {activeTab === "candidates" && (
        <div className="space-y-4">
          {candidateView === "list"&&<div className="flex flex-wrap items-center gap-3">{candidateToolbar}</div>}
          {candidateView === "board" && <PipelineBoard toolbar={candidateToolbar} title={hiringConfig.data?.name||"Hiring pipeline"} description="Bring the right people forward. Keep every candidate, conversation and hiring stage connected." label="Hiring pipeline" viewState={{job:String(selectedJob||""),status:statusFilter}} onApplyView={v=>{setSelectedJob(Number(v.job)||"");setStatusFilter(String(v.status||""));}} renderDetails={record=><HiringCandidateDetails candidate={((candidates||[]) as Candidate[]).find(c=>c.id===Number(record.id))!} canManage={canManage} onSaved={()=>{void refetchCandidates();void qc.invalidateQueries({queryKey:["employees"]});}}/>} context={{module:"hrms",scope:`job:${selectedJob||"all"}`,kind:"candidate"}} onAdd={canCreate&&selectedJob?stage=>{setQuickStage(stage);setCandidateError("");}:undefined} loading={loadingCandidates} disabled={(!canManage&&!canCreate) || updateStatusMutation.isPending} reorder={false}
            notice="Showing loaded candidates for the selected job and status. Hired is a status change; employee conversion remains a separate action."
            stages={hiringConfig.data?.stages?.length?hiringConfig.data.stages.map(s=>({id:s.name,name:s.name,canAdd:!s.require_interview&&!s.require_offer&&!(s.required||[]).includes("resume_url"),wipLimit:s.wip_limit||undefined,agingDays:s.aging_days||14})): [...new Set([...CANDIDATE_STATUSES,...((candidates||[]) as Candidate[]).map(c=>c.status==="Offered"?"Offer":c.status)])].map(status=>({id:status,name:status}))}
            records={((candidates||[]) as Candidate[]).map(c=>({id:String(c.id),disabled:!canManage,stageId:c.status==="Offered"&&!hiringConfig.data?.stages.some(s=>s.name==="Offered")?"Offer":c.status,title:c.name,isClosed:["Hired","Rejected","Withdrawn"].includes(c.status),subtitle:c.job?.title||c.email,value:c.source||"Applicant"}))}
            onOpen={record=>setSelectedCandidate(((candidates||[]) as Candidate[]).find(c=>c.id===Number(record.id))||null)}
            onMove={({record,stageId})=>setPendingMove({id:Number(record.id),name:record.title,status:stageId})}
            actions={canManage?[{id:"reject",label:"Reject",tone:"danger",onAction:record=>setPendingMove({id:Number(record.id),name:record.title,status:"Rejected"})},{id:"withdraw",label:"Withdraw",onAction:record=>setPendingMove({id:Number(record.id),name:record.title,status:"Withdrawn"})}]:[]}
          />}
          <PipelineDrawer wide open={configure} onClose={()=>setConfigure(false)} title="Job hiring pipeline">{hiringConfig.isError?<p role="alert">Could not load hiring configuration.</p>:hiringConfig.data?<PipelineStageEditor key={`${selectedJob}:${hiringConfig.data.version}`} name={hiringConfig.data.name} stages={hiringConfig.data.stages} hiring onSave={async draft=>{await api.put(`/pipeline-workspaces/hrms/jobs/${selectedJob}/configuration`,{...draft,expected_version:hiringConfig.data?.version});await hiringConfig.refetch();setConfigure(false);}}/>:<p>Loading hiring configuration…</p>}</PipelineDrawer>
          <PipelineDrawer open={!!quickStage} onClose={()=>{if(!candidateSaving)setQuickStage(undefined);}} title={`Add candidate to ${quickStage||"stage"}`}><form className="pipeline-settings-panel" onSubmit={async e=>{e.preventDefault();setCandidateSaving(true);setCandidateError("");try{await api.post(`/pipeline-workspaces/hrms/jobs/${selectedJob}/candidates`,{...candidateDraft,stage:quickStage});await refetchCandidates();setCandidateDraft({first_name:"",last_name:"",email:"",phone:"",phone_country_code:"+91",source:""});setQuickStage(undefined);}catch(e){setCandidateError((e as {response?:{data?:{detail?:string}}}).response?.data?.detail||"Could not add candidate. Check the fields and stage requirements.");}finally{setCandidateSaving(false);}}}>{(["first_name","last_name","email","source"] as const).map(field=><label key={field}>{field.replace(/_/g," ")}<input required={field!=="source"} type={field==="email"?"email":"text"} value={candidateDraft[field]} onChange={e=>setCandidateDraft(d=>({...d,[field]:e.target.value}))}/></label>)}<PhoneInput value={candidateDraft.phone} countryCode={candidateDraft.phone_country_code} onChange={phone=>setCandidateDraft(d=>({...d,phone}))} onCountryCodeChange={phone_country_code=>setCandidateDraft(d=>({...d,phone_country_code}))}/>{candidateError&&<p role="alert">{candidateError}</p>}<button type="submit" className="pipeline-primary" disabled={candidateSaving}>Add candidate</button></form></PipelineDrawer>
          <PipelineDrawer open={!!converting} onClose={()=>setConverting(null)} title="Create employee handoff">{converting&&<HiringCandidateDetails key={converting.id} candidate={converting} canManage={canManage} startConvert onSaved={()=>{void refetchCandidates();void qc.invalidateQueries({queryKey:["employees"]});}}/>}</PipelineDrawer>
          <Dialog open={!!pendingMove} onOpenChange={open=>{if(!open&&!updateStatusMutation.isPending)setPendingMove(undefined);}}><DialogContent><DialogTitle>Move candidate to {pendingMove?.status}</DialogTitle><p className="text-sm text-muted-foreground">Update {pendingMove?.name}'s hiring stage. This does not issue an offer or create an employee account.</p><div className="flex justify-end gap-2"><Button variant="outline" disabled={updateStatusMutation.isPending} onClick={()=>setPendingMove(undefined)}>Cancel</Button><Button disabled={updateStatusMutation.isPending} onClick={()=>{if(pendingMove)void updateStatusMutation.mutateAsync({id:pendingMove.id,status:pendingMove.status}).then(()=>setPendingMove(undefined)).catch(()=>undefined);}}>Confirm move</Button></div></DialogContent></Dialog>
          <Dialog open={!!selectedCandidate} onOpenChange={open=>{if(!open)setSelectedCandidate(null);}}><DialogContent><DialogTitle>{selectedCandidate?.name}</DialogTitle><dl className="grid grid-cols-2 gap-3 text-sm"><dt>Email</dt><dd>{selectedCandidate?.email}</dd><dt>Phone</dt><dd>{selectedCandidate?.phone||"—"}</dd><dt>Job</dt><dd>{selectedCandidate?.job?.title||"—"}</dd><dt>Status</dt><dd>{selectedCandidate?.status}</dd><dt>Source</dt><dd>{selectedCandidate?.source||"—"}</dd></dl>{canManage&&<Button onClick={()=>{setSelectedCandidate(null);setCandidateView("list");}}>Open candidate actions in list</Button>}</DialogContent></Dialog>
          {candidateView === "list" && <Card>

            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <GridTable gridId="apps/hrms/pages/recruitment/RecruitmentPage:table-1" className="w-full text-sm">
                  <thead className="border-b bg-muted/50">
                    <tr>
                      {["Candidate", "Job", "Source", "Applied", "Status", "Actions"].map((h) => (
                        <th key={h} className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wide">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {loadingCandidates ? (
                      Array.from({ length: 8 }).map((_, i) => (
                        <tr {...recordPreviewProps(_)} key={i} className="border-b">
                          <td colSpan={6} className="px-4 py-3"><div className="h-4 skeleton rounded" /></td>
                        </tr>
                      ))
                    ) : !(candidates as Candidate[])?.length ? (
                      <tr>
                        <td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">
                          <Users className="h-8 w-8 mx-auto mb-2 opacity-30" />
                          No candidates found
                        </td>
                      </tr>
                    ) : (
                      (candidates as Candidate[]).map((c) => (
                        <tr {...recordPreviewProps(c)} key={c.id} className="border-b hover:bg-muted/30">
                          <td className="px-4 py-3">
                            <p className="font-medium">{c.name}</p>
                            <p className="text-xs text-muted-foreground">{c.email}</p>
                          </td>
                          <td className="px-4 py-3 text-muted-foreground">{c.job?.title || "—"}</td>
                          <td className="px-4 py-3 text-muted-foreground">{c.source || "—"}</td>
                          <td className="px-4 py-3 text-muted-foreground">{formatDate(c.applied_date)}</td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(c.status)}`}>
                              {c.status}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <NativeSelect
                                value={c.status}
                                aria-label={`Hiring status for ${c.name}`}
                                disabled={!canManage || updateStatusMutation.isPending}
                                onChange={(e) => updateStatusMutation.mutate({ id: c.id, status: e.target.value })}
                                className="text-xs h-7 rounded border border-input bg-background px-2"
                              >
                                {CANDIDATE_STATUSES.map((s) => (
                                  <option key={s} value={s}>{s}</option>
                                ))}
                              </NativeSelect>
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 text-xs"
                                disabled={!canConvert || c.status !== "Hired" || convertCandidateMutation.isPending}
                                onClick={() => setConverting(c)}
                              >
                                Convert
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </GridTable>
              </div>
            </CardContent>
          </Card>}
        </div>
      )}
    </div>
  );
}

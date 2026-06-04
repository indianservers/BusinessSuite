import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Briefcase, Plus, Users, Calendar, CheckCircle2,
  XCircle, RefreshCw, Eye, ChevronDown
} from "lucide-react";
import { useForm } from "react-hook-form";
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
  "Applied","Screening","Interview","Assessment","Offer","Hired","Rejected"
];

export default function RecruitmentPage() {
  usePageTitle("Recruitment");
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<"jobs" | "candidates">("jobs");
  const [showJobForm, setShowJobForm] = useState(false);
  const [selectedJob, setSelectedJob] = useState<number | "">("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(null);

  const { data: jobs, isLoading: loadingJobs, refetch: refetchJobs } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => recruitmentApi.jobs().then((r) => r.data),
  });

  const { data: candidates, isLoading: loadingCandidates, refetch: refetchCandidates } = useQuery({
    queryKey: ["candidates", selectedJob, statusFilter],
    queryFn: () =>
      recruitmentApi.candidates({
        job_id: selectedJob || undefined,
        status: statusFilter || undefined,
      }).then((r) => r.data),
  });

  const { register: registerJob, handleSubmit: handleJobSubmit, reset: resetJob, formState: { errors: jobErrors } } = useForm<JobForm>({
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
            <Button size="sm" onClick={() => setShowJobForm((v) => !v)}>
              <Plus className="h-4 w-4 mr-2" />
              Post Job
            </Button>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
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
      </div>

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
            <form
              onSubmit={handleJobSubmit((data) => createJobMutation.mutate(data))}
              className="grid grid-cols-1 sm:grid-cols-2 gap-4"
            >
              <div className="space-y-1.5 sm:col-span-2">
                <Label>Job Title *</Label>
                <Input {...registerJob("title", { required: "Required" })} placeholder="e.g. Senior Software Engineer" />
                {jobErrors.title && <p className="text-xs text-red-500">{jobErrors.title.message}</p>}
              </div>
              <div className="space-y-1.5">
                <Label>Employment Type</Label>
                <select
                  {...registerJob("employment_type")}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  {["Full-time", "Part-time", "Contract", "Internship"].map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
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
                <textarea
                  {...registerJob("description")}
                  rows={3}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none"
                  placeholder="Describe the role..."
                />
              </div>
              <div className="space-y-1.5 sm:col-span-2">
                <Label>Requirements</Label>
                <textarea
                  {...registerJob("requirements")}
                  rows={3}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none"
                  placeholder="Skills and qualifications required..."
                />
              </div>
              <div className="sm:col-span-2 flex gap-3">
                <Button type="submit" disabled={createJobMutation.isPending}>
                  {createJobMutation.isPending ? "Posting..." : "Post Job"}
                </Button>
                <Button type="button" variant="outline" onClick={() => setShowJobForm(false)}>Cancel</Button>
              </div>
            </form>
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
                    <h3 className="font-semibold text-sm leading-tight">{job.title}</h3>
                    <span className={`shrink-0 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(job.status)}`}>
                      {job.status}
                    </span>
                  </div>
                  <div className="space-y-1 text-xs text-muted-foreground">
                    {job.department && <p>{job.department.name}</p>}
                    <p>{job.employment_type} {job.location ? `Â· ${job.location}` : ""}</p>
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
          <div className="flex flex-wrap gap-3">
            <select
              value={selectedJob}
              onChange={(e) => setSelectedJob(e.target.value ? Number(e.target.value) : "")}
              className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">All Jobs</option>
              {(jobs as Job[])?.map((j) => (
                <option key={j.id} value={j.id}>{j.title}</option>
              ))}
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">All Statuses</option>
              {CANDIDATE_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <Button variant="ghost" size="icon" className="h-10 w-10" onClick={() => refetchCandidates()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>

          {/* Pipeline kanban summary */}
          <div className="grid grid-cols-4 sm:grid-cols-7 gap-2">
            {CANDIDATE_STATUSES.map((s) => {
              const count = (candidates as Candidate[])?.filter((c) => c.status === s).length ?? 0;
              return (
                <button
                  key={s}
                  onClick={() => setStatusFilter(statusFilter === s ? "" : s)}
                  className={`p-2 rounded-lg border text-center transition-colors ${
                    statusFilter === s ? "border-primary bg-primary/10" : "border-border hover:bg-muted/50"
                  }`}
                >
                  <p className="text-lg font-bold">{count}</p>
                  <p className="text-xs text-muted-foreground truncate">{s}</p>
                </button>
              );
            })}
          </div>

          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
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
                        <tr key={i} className="border-b">
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
                        <tr key={c.id} className="border-b hover:bg-muted/30">
                          <td className="px-4 py-3">
                            <p className="font-medium">{c.name}</p>
                            <p className="text-xs text-muted-foreground">{c.email}</p>
                          </td>
                          <td className="px-4 py-3 text-muted-foreground">{c.job?.title || "â€”"}</td>
                          <td className="px-4 py-3 text-muted-foreground">{c.source || "â€”"}</td>
                          <td className="px-4 py-3 text-muted-foreground">{formatDate(c.applied_date)}</td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(c.status)}`}>
                              {c.status}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <select
                                value={c.status}
                                onChange={(e) => updateStatusMutation.mutate({ id: c.id, status: e.target.value })}
                                className="text-xs h-7 rounded border border-input bg-background px-2"
                              >
                                {CANDIDATE_STATUSES.map((s) => (
                                  <option key={s} value={s}>{s}</option>
                                ))}
                              </select>
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 text-xs"
                                disabled={c.status !== "Hired" || convertCandidateMutation.isPending}
                                onClick={() => convertCandidateMutation.mutate(c.id)}
                              >
                                Convert
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

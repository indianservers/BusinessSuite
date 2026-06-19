import { FormEvent, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { CheckCircle2, Flag, Plus, Send, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatDate, statusColor } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";
import { milestonesAPI } from "../services/api";
import type { MilestoneStatus, PMSMilestone } from "../types";

export default function MilestonesPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const id = Number(projectId || 0);
  const [milestones, setMilestones] = useState<PMSMilestone[]>([]);
  const [name, setName] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [status, setStatus] = useState<MilestoneStatus>("Not Started");
  const [error, setError] = useState<string | null>(null);
  const [busyMilestoneId, setBusyMilestoneId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!id) return;
    milestonesAPI.list(id).then(setMilestones).catch((err) => setError(apiError(err, "Unable to load milestones.")));
  }, [id]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    try {
      setSubmitting(true);
      setError(null);
      const created = await milestonesAPI.create(id, { name, due_date: dueDate || undefined, status });
      setMilestones((items) => [created, ...items]);
      setName("");
      setDueDate("");
      toast({ title: "Milestone created" });
    } catch (err: any) {
      setError(apiError(err, "Could not create milestone."));
    } finally {
      setSubmitting(false);
    }
  };

  const refreshMilestone = (updated: PMSMilestone) => {
    setMilestones((items) => items.map((item) => item.id === updated.id ? updated : item));
  };

  const runMilestoneAction = async (milestone: PMSMilestone, action: "submit" | "approve" | "reject") => {
    try {
      const rejectionReason = action === "reject" ? window.prompt("Reason for rejection") : null;
      if (action === "reject" && rejectionReason === null) return;
      setBusyMilestoneId(milestone.id);
      setError(null);
      const updated = action === "submit"
        ? await milestonesAPI.submitApproval(milestone.id)
        : action === "approve"
          ? await milestonesAPI.approve(milestone.id)
          : await milestonesAPI.reject(milestone.id, rejectionReason?.trim() || "Rejected");
      refreshMilestone(updated as PMSMilestone);
      toast({ title: action === "submit" ? "Approval requested" : action === "approve" ? "Milestone approved" : "Milestone rejected" });
    } catch (err: any) {
      setError(apiError(err, "Milestone action failed."));
    } finally {
      setBusyMilestoneId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Milestones</h1>
        <p className="page-description">Plan deliverables, approval gates, and client-visible outcomes.</p>
      </div>
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Plus className="h-5 w-5" />Create milestone</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="grid gap-4 md:grid-cols-[1fr_12rem_12rem_auto] md:items-end">
            <div className="space-y-2">
              <Label htmlFor="milestone-name">Name</Label>
              <Input id="milestone-name" value={name} onChange={(event) => setName(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="milestone-due">Due date</Label>
              <Input id="milestone-due" type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Status</Label>
              <select value={status} onChange={(event) => setStatus(event.target.value as MilestoneStatus)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                {["Not Started", "In Progress", "At Risk", "Completed", "Delayed"].map((item) => <option key={item}>{item}</option>)}
              </select>
            </div>
            <Button type="submit" disabled={submitting}>{submitting ? "Adding..." : "Add"}</Button>
          </form>
        </CardContent>
      </Card>
      {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {milestones.map((milestone) => (
          <Card key={milestone.id} className={approvalCardTone(milestone.client_approval_status)}>
            <CardContent className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-violet-100 p-2 text-violet-700"><Flag className="h-5 w-5" /></div>
                  <div>
                    <h2 className="font-semibold">{milestone.name}</h2>
                    <p className="text-sm text-muted-foreground">Due {formatDate(milestone.due_date || null)}</p>
                  </div>
                </div>
                <Badge className={statusColor(milestone.status)}>{milestone.status}</Badge>
              </div>
              <div className="mt-5">
                <div className="mb-2 flex justify-between text-xs text-muted-foreground"><span>Progress</span><span>{milestone.progress_percent}%</span></div>
                <div className="h-2 rounded-full bg-muted"><div className="h-2 rounded-full bg-violet-600" style={{ width: `${milestone.progress_percent}%` }} /></div>
              </div>
              <div className="mt-4 rounded-md border bg-background/70 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium">Client approval</p>
                    <p className="text-xs text-muted-foreground">{milestone.client_rejected_reason || approvalHelp(milestone.client_approval_status)}</p>
                  </div>
                  <Badge className={approvalBadgeTone(milestone.client_approval_status)}>{milestone.client_approval_status}</Badge>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={() => runMilestoneAction(milestone, "submit")} disabled={busyMilestoneId === milestone.id || milestone.client_approval_status === "Pending" || milestone.client_approval_status === "Approved"}>
                    <Send className="h-4 w-4" />Submit
                  </Button>
                  <Button size="sm" onClick={() => runMilestoneAction(milestone, "approve")} disabled={busyMilestoneId === milestone.id || milestone.client_approval_status === "Approved"}>
                    <CheckCircle2 className="h-4 w-4" />Approve
                  </Button>
                  <Button size="sm" variant="destructive" onClick={() => runMilestoneAction(milestone, "reject")} disabled={busyMilestoneId === milestone.id || milestone.client_approval_status === "Rejected"}>
                    <XCircle className="h-4 w-4" />Reject
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function approvalCardTone(status: string) {
  if (status === "Approved") return "border-emerald-200 bg-emerald-50/60 dark:bg-emerald-950/10";
  if (status === "Rejected") return "border-red-200 bg-red-50/70 dark:bg-red-950/10";
  if (status === "Pending") return "border-amber-200 bg-amber-50/60 dark:bg-amber-950/10";
  return "";
}

function approvalBadgeTone(status: string) {
  if (status === "Approved") return "bg-emerald-100 text-emerald-700";
  if (status === "Rejected") return "bg-red-100 text-red-700";
  if (status === "Pending") return "bg-amber-100 text-amber-700";
  return "bg-muted text-muted-foreground";
}

function approvalHelp(status: string) {
  if (status === "Approved") return "Approved milestones are locked from duplicate approval.";
  if (status === "Rejected") return "Rejected milestones can be resubmitted after changes.";
  if (status === "Pending") return "Waiting for client approval.";
  return "Submit when this milestone is ready for client approval.";
}

function apiError(err: any, fallback: string) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  return fallback;
}


import {useMobileContext} from "@/components/mobile/useMobileContext";
import {useMobileDraftGuard} from "@/components/mobile/useMobileDraftGuard";
import {syncScope} from "@/shared/record-sync/store";
import {useMobile} from "@/components/mobile/useMobile";
import "./milestones-mobile.css";
import {SmartCreateSection} from "@/shared/creation/SmartCreateSection";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import { useRefreshableEffect } from "@/lib/page-refresh";
import { FormEvent, useEffect, useRef, useState } from "react";
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
  const phone=useMobile(480),scope=useMobileContext();
  const {projectId}=useParams<{projectId:string}>();
  if(phone&&scope!==syncScope())return <p role="status">Updating milestone context…</p>;
  return <MilestonesContent key={phone?JSON.stringify([scope,projectId]):"desktop"}/>;
}

function MilestonesContent() {
  const phone=useMobile(480),locks=useRef(new Set<number>()),creating=useRef(false);
  const ownerScope=useRef(syncScope()),mounted=useRef(true);
  const owns=()=>mounted.current&&ownerScope.current===syncScope();
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  const [pending,setPending]=useState<number[]>([]),[savedRevision,setSavedRevision]=useState(0);
  const { projectId } = useParams<{ projectId: string }>();
  const id = Number(projectId || 0);
  const [milestones, setMilestones] = useState<PMSMilestone[]>([]);
  const [name, setName] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [status, setStatus] = useState<MilestoneStatus>("Not Started");
  const [error, setError] = useState<string | null>(null);
  const [busyMilestoneId, setBusyMilestoneId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const draftBaseline=useRef(JSON.stringify(["","","Not Started"]));
  const draftSignature=JSON.stringify([name,dueDate,status]);
  useMobileDraftGuard({enabled:phone,dirty:draftSignature!==draftBaseline.current,draftKey:ownerScope.current+":"+id+":"+draftSignature,pending:()=>creating.current||locks.current.size>0,onDiscard:()=>{draftBaseline.current=draftSignature;},message:"Discard this milestone draft and leave?"});

  const [sourcePhase,setSourcePhase]=useState<"loading"|"ready"|"error">("loading");
  const [sourceError,setSourceError]=useState("");
  const sourceOwner=useRef<number|null>(null),loaded=useRef(false),withheld=useRef(false);
  const retrySource=useRef<()=>void>(()=>{});
  const revision=useRef(0);
  const acknowledged=useRef(new Map<number,{revision:number;createdAt?:number;value:PMSMilestone}>());
  function acknowledge(value:PMSMilestone,created=false){
    if(!phone||!owns()||value.project_id!==sourceOwner.current)return;
    const previous=acknowledged.current.get(value.id),current=++revision.current;
    acknowledged.current.set(value.id,{revision:current,createdAt:created?current:previous?.createdAt,value});
  }
  const sourceReady=!phone||(owns()&&sourceOwner.current===id&&sourcePhase==="ready");
  useRefreshableEffect(() => {
    if(!phone){
      if (!id) return;
      milestonesAPI.list(id).then(setMilestones).catch((err) => setError(apiError(err, "Unable to load milestones.")));
      return;
    }
    let active=true,reading=false;
    if(sourceOwner.current!==id){sourceOwner.current=id;loaded.current=false;withheld.current=true;acknowledged.current.clear();revision.current=0;setMilestones([]);}
    async function load(){
      if(!active||!owns()||reading)return;
      reading=true;setSourcePhase("loading");setSourceError("");
      if(!id){loaded.current=false;setMilestones([]);setSourcePhase("error");setSourceError("Select a project to load milestones.");reading=false;return;}
      try{
        const startedRevision=revision.current;
        const rows=await milestonesAPI.list(id);
        if(!active||!owns())return;
        const returnedIds=new Set(rows.map(row=>row.id));
        const merged=rows.map(row=>{
          const completed=acknowledged.current.get(row.id);
          return completed&&completed.revision>startedRevision?completed.value:row;
        });
        // Only records created after this snapshot began may be absent from it.
        // A later read may legitimately omit a previously acknowledged record.
        const createdLater=[...acknowledged.current.values()].filter(entry=>(entry.createdAt??0)>startedRevision&&!returnedIds.has(entry.value.id));
        createdLater.sort((a,b)=>(b.createdAt??0)-(a.createdAt??0));
        setMilestones([...createdLater.map(entry=>entry.value),...merged]);loaded.current=true;withheld.current=false;setSourcePhase("ready");
      }catch(err:any){
        if(!active||!owns())return;
        if(err?.response?.status>=400&&err?.response?.status<500){loaded.current=false;withheld.current=true;setMilestones([]);}
        setSourceError(apiError(err,"Unable to load milestones."));setSourcePhase("error");
      }finally{reading=false;}
    }
    retrySource.current=()=>void load();void load();
    return()=>{active=false;};
  }, [id,phone]);
  const sourceNotice=()=>phone&&sourcePhase!=="ready"?<div className="pms-milestone-source" role={sourcePhase==="error"?"alert":"status"}>
    <p>{sourcePhase==="loading"?(loaded.current?"Refreshing milestones…":"Loading milestones…"):sourceError}</p>
    {sourcePhase==="error"&&loaded.current&&<p>Showing last loaded milestones. Reload before making changes.</p>}
    {sourcePhase==="error"&&<Button variant="outline" type="button" onClick={()=>retrySource.current()}>Retry milestones</Button>}
  </div>:null;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim() || (phone&&(!owns()||creating.current||!sourceReady))) return;
    if(phone)creating.current=true;
    try {
      setSubmitting(true);
      setError(null);
      const created = await milestonesAPI.create(id, { name, due_date: dueDate || undefined, status });
      if(phone&&!owns())return;
      acknowledge(created,true);
      if(!phone||(sourceOwner.current===id&&!withheld.current))setMilestones((items) => [created, ...items.filter(item=>!phone||item.id!==created.id)]);
      setName("");
      setDueDate("");
      if(phone){draftBaseline.current=JSON.stringify(["","",status]);setSavedRevision(value=>value+1);}
      toast({ title: "Milestone created" });
    } catch (err: any) {
      if(phone&&!owns())return;
      setError(apiError(err, "Could not create milestone."));
    } finally {
      if(!phone||owns()){if(phone)creating.current=false;setSubmitting(false);}
    }
  };

  const refreshMilestone = (updated: PMSMilestone) => {
    acknowledge(updated);
    setMilestones((items) => items.map((item) => item.id === updated.id ? updated : item));
  };

  const runMilestoneAction = async (milestone: PMSMilestone, action: "submit" | "approve" | "reject") => {
    if(phone&&(!owns()||!sourceReady||locks.current.has(milestone.id)))return;
    if(phone){locks.current.add(milestone.id);setPending([...locks.current]);}
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
      if(phone&&!owns())return;
      refreshMilestone(updated as PMSMilestone);
      toast({ title: action === "submit" ? "Approval requested" : action === "approve" ? "Milestone approved" : "Milestone rejected" });
    } catch (err: any) {
      if(phone&&!owns())return;
      setError(apiError(err, "Milestone action failed."));
    } finally {
      if(!phone||owns()){if(phone){locks.current.delete(milestone.id);setPending([...locks.current]);}setBusyMilestoneId(null);}
    }
  };

  return (
    <div className="pms-milestones space-y-6">
      <div>
        <h1 className="page-title">Milestones</h1>
        <p className="page-description">Plan deliverables, approval gates, and client-visible outcomes.</p>
      </div>
      {sourceNotice()}
      <SmartCreateSection title="Create milestone" mobileSheet={phone} savedRevision={phone?savedRevision:0} closeOnRecordSaved={!phone} completionRevision={phone?savedRevision:0} trigger={phone?<Button className="pms-milestone-create-trigger" type="button"><Plus className="h-4 w-4"/>Create milestone</Button>:undefined}><Card>
        <CardHeader className="pms-milestone-create-heading"><CardTitle className="flex items-center gap-2"><Plus className="h-5 w-5" />Create milestone</CardTitle></CardHeader>
        <CardContent>
          {sourceNotice()}
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <CompactForm onSubmit={submit} className="pms-milestone-form grid gap-4 md:grid-cols-[1fr_12rem_12rem_auto] md:items-end">
            <div className="pms-milestone-name space-y-2">
              <Label htmlFor="milestone-name">Name</Label>
              <Input disabled={phone&&submitting} required id="milestone-name" value={name} onChange={(event) => setName(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="milestone-due">Due date</Label>
              <Input disabled={phone&&submitting} id="milestone-due" type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor={phone?"milestone-status":undefined}>Status</Label>
              <NativeSelect disabled={phone&&submitting} id={phone?"milestone-status":undefined} value={status} onChange={(event) => setStatus(event.target.value as MilestoneStatus)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                {["Not Started", "In Progress", "At Risk", "Completed", "Delayed"].map((item) => <option key={item}>{item}</option>)}
              </NativeSelect>
            </div>
            <Button data-save-action type="submit" disabled={submitting||!sourceReady}>{submitting ? "Adding..." : "Add"}</Button>
          </CompactForm>
        </CardContent>
      </Card></SmartCreateSection>
      {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      {phone&&sourcePhase==="ready"&&!milestones.length&&<p role="status">No milestones yet.</p>}
      <div className="pms-milestone-list grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {(phone&&sourceOwner.current!==id?[]:milestones).map((milestone) => (
          <Card key={milestone.id} data-milestone-id={phone?milestone.id:undefined} aria-busy={phone?pending.includes(milestone.id):undefined} className={`pms-milestone-record ${approvalCardTone(milestone.client_approval_status)}`}>
            <CardContent className="pms-milestone-content p-5">
              <div className="pms-milestone-heading flex items-start justify-between gap-3">
                <div className="pms-milestone-identity flex items-center gap-3">
                  <div className="rounded-lg bg-violet-100 p-2 text-violet-700"><Flag className="h-5 w-5" /></div>
                  <div>
                    <h2 className="font-semibold">{milestone.name}</h2>
                    <p className="text-sm text-muted-foreground">Due {formatDate(milestone.due_date || null)}</p>
                  </div>
                </div>
                <Badge className={statusColor(milestone.status)}>{milestone.status}</Badge>
              </div>
              <div className="pms-milestone-progress mt-5">
                <div className="mb-2 flex justify-between text-xs text-muted-foreground"><span>Progress</span><span>{milestone.progress_percent}%</span></div>
                <div className="h-2 rounded-full bg-muted"><div className="h-2 rounded-full bg-violet-600" style={{ width: `${milestone.progress_percent}%` }} /></div>
              </div>
              <div className="pms-milestone-approval mt-4 rounded-md border bg-background/70 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="pms-milestone-approval-copy">
                    <p className="text-sm font-medium">Client approval</p>
                    <p className="text-xs text-muted-foreground">{milestone.client_rejected_reason || approvalHelp(milestone.client_approval_status)}</p>
                  </div>
                  <Badge className={approvalBadgeTone(milestone.client_approval_status)}>{milestone.client_approval_status}</Badge>
                </div>
                <div className="pms-milestone-actions mt-3 flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={() => runMilestoneAction(milestone, "submit")} disabled={(phone?(!sourceReady||pending.includes(milestone.id)):busyMilestoneId === milestone.id) || milestone.client_approval_status === "Pending" || milestone.client_approval_status === "Approved"}>
                    <Send className="h-4 w-4" />Submit
                  </Button>
                  <Button size="sm" onClick={() => runMilestoneAction(milestone, "approve")} disabled={(phone?(!sourceReady||pending.includes(milestone.id)):busyMilestoneId === milestone.id) || milestone.client_approval_status === "Approved"}>
                    <CheckCircle2 className="h-4 w-4" />Approve
                  </Button>
                  <Button size="sm" variant="destructive" onClick={() => runMilestoneAction(milestone, "reject")} disabled={(phone?(!sourceReady||pending.includes(milestone.id)):busyMilestoneId === milestone.id) || milestone.client_approval_status === "Rejected"}>
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


import {syncScope} from "@/shared/record-sync/store";
import {useMobile} from "@/components/mobile/useMobile";
import {moduleActionAllowed} from "@/hooks/use-module-action";
import {useAuthStore} from "@/store/authStore";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import {
  RichTextField,
  RichTextContent,
  richTextPlainText,
} from "@/components/rich-text/LazyRichText";
import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/hooks/use-toast";
type Row = Record<string, any>;
export default function WorkReviewPanel({
  taskId,
  submissionId,
  onReviewed,
  mobileReview=false,
}: {
  taskId?: number;
  submissionId?: number;
  onReviewed?: () => void;
  mobileReview?: boolean;
}) {
  const narrow=useMobile(480);
  const phone=mobileReview && narrow;
  const actor=useAuthStore(s=>s.user);
  const canApprove=moduleActionAllowed(actor,"/pms/reviews","approve");
  const qc = useQueryClient();
  const [selected, setSelected] = useState<number>();
  const [decision, setDecision] = useState("Approved");
  const [score, setScore] = useState("");
  const [rubricScores, setRubricScores] = useState<Record<string, string>>({});
  const [communication, setCommunication] = useState("");
  const [feedback, setFeedback] = useState("");
  const [strengths, setStrengths] = useState("");
  const [improvements, setImprovements] = useState("");
  const [inspected, setInspected] = useState(false);
  const [preview, setPreview] = useState("");
  const [dirty,setDirty]=useState(false);
  const source = useQuery<{ items: Row[]; total: number }>({
    queryKey: ["pms-work", taskId, submissionId],
    queryFn: () =>
      api
        .get("/project-management/work/submissions", {
          params: {
            task_id: taskId,
            submission_id: submissionId,
            per_page: 100,
          },
        })
        .then((r) => r.data),
  });
  const {data,isLoading,error}=source;
  const item =
    data?.items.find((i) => i.id === (submissionId || selected)) ||
    (!submissionId ? data?.items[0] : undefined);
  const evidenceOwned=useRef(false),evidencePending=useRef(false);
  const evidenceSequence=useRef(0),evidenceController=useRef<AbortController>();
  const evidenceItem=useRef(item?.id);evidenceItem.current=item?.id;
  const [loadingEvidence,setLoadingEvidence]=useState<number>();
  const [evidenceError,setEvidenceError]=useState("");
  useEffect(()=>{
    if(!mobileReview || !evidenceOwned.current)return;
    evidenceSequence.current++;evidencePending.current=false;evidenceController.current?.abort();setLoadingEvidence(undefined);setEvidenceError("");setPreview("");
    return()=>{evidenceSequence.current++;evidenceController.current?.abort();};
  },[mobileReview,item?.id,actor?.id,actor?.access?.companyId]);
  useEffect(()=>{
    if(!mobileReview)return;
    const reset=()=>{if(!evidenceOwned.current)return;evidenceSequence.current++;evidencePending.current=false;evidenceController.current?.abort();setLoadingEvidence(undefined);setEvidenceError("");setPreview("");};
    window.addEventListener("suite:organization-changed",reset);window.addEventListener("suite:branch-changed",reset);
    return()=>{evidenceSequence.current++;evidenceController.current?.abort();window.removeEventListener("suite:organization-changed",reset);window.removeEventListener("suite:branch-changed",reset);};
  },[mobileReview]);
  useEffect(() => {
    setInspected(false);
    setScore("");
    setRubricScores({});
    setFeedback("");
    setStrengths("");
    setImprovements("");
    setCommunication("");
    setPreview("");
    if(phone)setDirty(false);
  }, [item?.id]);
  useEffect(
    () => () => {
      if (preview) URL.revokeObjectURL(preview);
    },
    [preview],
  );
  const reviewSubmitting=useRef(false);
  const mutation = useMutation({
    onSettled: () => { reviewSubmitting.current=false; },
    mutationFn: () =>
      api.post(`/project-management/work/submissions/${item!.id}/review`, {
        status: decision,
        score: item?.evaluation_rubric?.length
          ? Object.values(rubricScores).reduce(
              (sum, value) => sum + Number(value),
              0,
            )
          : Number(score),
        rubric: item?.evaluation_rubric?.length
          ? Object.fromEntries(
              Object.entries(rubricScores).map(([key, value]) => [
                key,
                Number(value),
              ]),
            )
          : {},
        communication_score:
          communication === "" ? null : Number(communication),
        feedback,
        strengths,
        improvements,
        inspected,
      }),
    onSuccess: () => {
      if(phone)setDirty(false);
      qc.invalidateQueries({ queryKey: ["pms-work"] });
      qc.invalidateQueries({ queryKey: ["intern-management"] });
      onReviewed?.();
      toast({
        title: "PMS review recorded",
        description:
          "The task history and intern performance now use this same decision.",
      });
    },
    onError: (e: any) =>
      toast({
        title: "Review not saved",
        description:
          e.response?.data?.detail || "Check PMS review permissions.",
        variant: "destructive",
      }),
  });
  function leaveReview() {
    if(!phone)return true;
    if(mutation.isPending || reviewSubmitting.current)return false;
    if(dirty && !window.confirm("Discard unsaved review changes before leaving this submission?"))return false;
    setDirty(false);return true;
  }
  useEffect(()=>{
    if(!phone || !dirty && !mutation.isPending)return;
    const unload=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue="";};
    const click=(event:MouseEvent)=>{
      if(event.defaultPrevented || event.button!==0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)return;
      const link=(event.target as Element)?.closest?.("a[href]") as HTMLAnchorElement|null;
      if(!link || link.hasAttribute("download") || link.target && link.target!=="_self")return;
      const next=new URL(link.href,location.href);
      if(next.origin===location.origin && next.pathname===location.pathname && next.search===location.search)return;
      if(!leaveReview()){event.preventDefault();event.stopPropagation();}
    };
    window.addEventListener("beforeunload",unload);document.addEventListener("click",click,true);
    return()=>{window.removeEventListener("beforeunload",unload);document.removeEventListener("click",click,true);};
  },[phone,dirty,mutation.isPending]);
  async function openFile(id: number) {
    if(phone){
      if(evidencePending.current || !item?.files?.includes(id))return;
      evidenceOwned.current=true;evidencePending.current=true;
      const sequence=++evidenceSequence.current,context=JSON.stringify([syncScope(),item.id]);
      const controller=new AbortController();evidenceController.current=controller;
      const current=()=>sequence===evidenceSequence.current && context===JSON.stringify([syncScope(),evidenceItem.current]);
      setLoadingEvidence(id);setEvidenceError("");
      try {
        const response=await api.get(`/project-management/work/files/${id}`,{responseType:"blob",signal:controller.signal});
        if(current())setPreview(URL.createObjectURL(response.data));
      } catch {
        if(current() && !controller.signal.aborted)setEvidenceError(`Evidence #${id} is unavailable or access was denied. Please retry inspection.`);
      } finally {if(current()){evidencePending.current=false;setLoadingEvidence(undefined);}}
      return;
    }
    try {
      const result = await api.get(`/project-management/work/files/${id}`, {
        responseType: "blob",
      });
      if (preview) URL.revokeObjectURL(preview);
      setPreview(URL.createObjectURL(result.data));
    } catch {
      toast({
        title: "Evidence unavailable or access denied",
        variant: "destructive",
      });
    }
  }
  const sourceNotice=phone && (error || source.isFetching || source.fetchStatus==="paused") ? <div className="work-review-source">
    {error && <><p role="alert">Could not load PMS submissions.{data ? " Showing the last loaded submissions." : " Please retry to load submissions."}</p><Button variant="outline" type="button" disabled={source.isFetching || source.fetchStatus==="paused"} onClick={()=>void source.refetch()}>Retry submissions</Button></>}
    {(source.isFetching || source.fetchStatus==="paused") && <p role="status">{source.fetchStatus==="paused" ? "Waiting for a connection to load PMS submissions." : data ? "Refreshing PMS submissions…" : "Loading PMS submissions…"}</p>}
  </div> : null;
  if(phone && !data && source.fetchStatus==="paused")return sourceNotice;
  if (isLoading) return phone ? sourceNotice : <p>Loading PMS submissions…</p>;
  if (error && (!phone || !data)) return phone ? sourceNotice : <p role="alert">PMS access is required to read this evidence.</p>;
  if (!item && phone)return <div>{sourceNotice}<p role="status" className="text-sm text-muted-foreground">No PMS submission selected. Interns' submitted work appears here.</p></div>;
  if (!item)
    return (
      <p className="text-sm text-muted-foreground">
        No PMS submission selected. Interns' submitted work appears here.
      </p>
    );
  return (
    <div className="space-y-5">
      {sourceNotice}
      {phone && mutation.isPending && <p role="status">Saving PMS review…</p>}
      {phone && mutation.isError && <p role="alert">{String((mutation.error as {response?:{data?:{detail?:string}}})?.response?.data?.detail || "Review not saved. Your entries are retained; please retry.")}</p>}
      {!submissionId && (
        <label className="block text-sm">
          Submission version
          <NativeSelect
            disabled={phone && mutation.isPending}
            className="mt-2 w-full rounded-md border bg-background p-2"
            value={item.id}
            onChange={(e) => {if(Number(e.target.value)!==item.id && leaveReview()){if(phone)mutation.reset();setSelected(Number(e.target.value));}}}
          >
            {data?.items.map((i) => (
              <option key={i.id} value={i.id}>
                {i.user_name || `User ${i.user_id}`} ·{" "}
                {i.task_title || `Task ${i.task_id}`} · Version {i.version} ·{" "}
                {i.status}
              </option>
            ))}
          </NativeSelect>
        </label>
      )}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold">
            {item.task_title || `PMS Task #${item.task_id}`}
          </h3>
          <p className="text-xs text-muted-foreground">
            Version {item.version} · {item.user_name || `User ${item.user_id}`}{" "}
            · {new Date(item.created_at).toLocaleString()}
          </p>
        </div>
        <Badge variant="outline">{item.status}</Badge>
      </div>
      <div className="whitespace-pre-wrap rounded-lg bg-muted/30 p-4 text-sm">
        <RichTextContent value={item.notes} />
      </div>
      {item.revision_note && (
        <p className="text-sm">
          <b>Revision note:</b> {item.revision_note}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {item.files.map((id: number) => (
          <Button
            key={id}
            disabled={phone && loadingEvidence!==undefined}
            variant="outline"
            size="sm"
            onClick={() => openFile(id)}
          >
            Inspect Evidence #{id}
          </Button>
        ))}
      </div>
      {phone && loadingEvidence!==undefined && <p role="status">Loading evidence #{loadingEvidence}…</p>}
      {phone && evidenceError && <p role="alert">{evidenceError}</p>}
      {item.links.map((link: string) => (
        <a
          className="block break-all text-sm text-primary underline"
          href={link}
          target="_blank"
          rel="noreferrer"
          key={link}
        >
          {link}
        </a>
      ))}
      {preview && (
        <div className="rounded-lg border p-3">
          <Button asChild variant="outline"><a
            href={preview}
            download={`pms-evidence-${item.id}`}
            className="text-sm text-primary underline"
          >
            Download opened evidence
          </a></Button>
          <iframe
            title="Submitted evidence preview"
            src={preview}
            className="mt-2 h-80 w-full rounded border"
            sandbox="allow-same-origin"
          />
        </div>
      )}
      {item.feedback && (
        <div className="rounded-lg border bg-emerald-50/30 p-4 text-sm">
          <b>
            Recorded PMS decision: {item.status} · {item.raw_score}/
            {item.maximum_score}
          </b>
          <div className="mt-2 whitespace-pre-wrap">
            <RichTextContent value={item.feedback} />
          </div>
          {item.strengths && <p>Strengths: {item.strengths}</p>}
          {item.improvements && <p>Improvements: {item.improvements}</p>}
          {item.evaluation_rubric?.map((criterion: Row) => (
            <p key={criterion.key}>
              {criterion.label}: {item.rubric_scores?.[criterion.key] ?? "—"}/
              {criterion.points}
            </p>
          ))}
        </div>
      )}
      {item.status === "Pending Review" && item.can_review !== false && canApprove ? (
        <CompactForm
          aria-busy={phone ? mutation.isPending : undefined}
          className="work-review-form grid gap-4 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            if(phone) {
              if(reviewSubmitting.current || mutation.isPending || !canApprove || item.can_review===false || item.status!=="Pending Review" || !inspected || (item.evaluation_rubric?.length ? item.evaluation_rubric.some((criterion:Row)=>rubricScores[criterion.key]===undefined || rubricScores[criterion.key]==="") : score==="")) return;
              reviewSubmitting.current=true;
            }
            if(canApprove)mutation.mutate();
          }}
        >
          <Label>
            Decision
            <NativeSelect
            disabled={phone && mutation.isPending}
              className="mt-2 w-full rounded-md border bg-background p-2"
              value={decision}
              onChange={(e) => {const value=e.target.value;setDecision(value);if(phone)setDirty(true);}}
            >
              {["Approved", "Needs Revision", "Rejected"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </NativeSelect>
          </Label>
          <Label>
            Score (maximum {item.maximum_score || 100})
            <Input
              disabled={phone && mutation.isPending}
              required={!item.evaluation_rubric?.length}
              readOnly={!!item.evaluation_rubric?.length}
              min={0}
              max={item.maximum_score || 100}
              type="number"
              value={
                item.evaluation_rubric?.length
                  ? Object.values(rubricScores).reduce(
                      (sum, value) => sum + Number(value),
                      0,
                    )
                  : score
              }
              onChange={(e) => {const value=e.target.value;setScore(value);if(phone)setDirty(true);}}
            />
          </Label>
          {!!item.evaluation_rubric?.length && (
            <fieldset className="space-y-3 rounded-lg border p-3 sm:col-span-2">
              <legend className="px-2 text-sm font-semibold">
                Task pack evaluation rubric · {item.skill_level}
              </legend>
              {item.evaluation_rubric.map((criterion: Row) => (
                <label key={criterion.key} className="grid gap-1 text-sm">
                  {criterion.label} (maximum {criterion.points})
                  <span className="text-xs text-muted-foreground">
                    {criterion.description}
                  </span>
                  <Input
              disabled={phone && mutation.isPending}
                    aria-label={`Rubric score: ${criterion.label}`}
                    required
                    type="number"
                    step={1}
                    min={0}
                    max={criterion.points}
                    value={rubricScores[criterion.key] ?? ""}
                    onChange={(e) => {
                      const value=e.target.value;
                      setRubricScores((current) => ({...current,[criterion.key]:value}));
                      if(phone)setDirty(true);
                    }}
                  />
                </label>
              ))}
            </fieldset>
          )}
          <Label>
            Communication score / 100 (optional)
            <Input
              disabled={phone && mutation.isPending}
              min={0}
              max={100}
              type="number"
              value={communication}
              onChange={(e) => {const value=e.target.value;setCommunication(value);if(phone)setDirty(true);}}
            />
          </Label>
          <Label className="sm:col-span-2">
            Feedback
            <RichTextField
              disabled={phone && mutation.isPending}
              data-legacy-format="markdown"
              required
              maxLength={5000}
              className="mt-2 w-full rounded-md border bg-background p-3 text-sm"
              rows={3}
              value={feedback}
              onChange={(e) => {const value=e.target.value;setFeedback(value);if(phone)setDirty(true);}}
            />
          </Label>
          <Label>
            Strengths
            <Input
              disabled={phone && mutation.isPending}
              value={strengths}
              onChange={(e) => {const value=e.target.value;setStrengths(value);if(phone)setDirty(true);}}
            />
          </Label>
          <Label>
            Improvements
            <Input
              disabled={phone && mutation.isPending}
              value={improvements}
              onChange={(e) => {const value=e.target.value;setImprovements(value);if(phone)setDirty(true);}}
            />
          </Label>
          <label className="flex items-start gap-2 text-sm sm:col-span-2">
            <input
              disabled={phone && mutation.isPending}
              type="checkbox"
              checked={inspected}
              onChange={(e) => {const value=e.target.checked;setInspected(value);if(phone)setDirty(true);}}
            />
            I have inspected this version's evidence and notes before making
            this decision.
          </label>
          <Button
            disabled={
              mutation.isPending ||
              !inspected ||
              (item.evaluation_rubric?.length
                ? item.evaluation_rubric.some(
                    (c: Row) =>
                      rubricScores[c.key] === undefined ||
                      rubricScores[c.key] === "",
                  )
                : score === "")
            }
          >
            Save PMS Review
          </Button>
        </CompactForm>
      ) : item.status === "Pending Review" ? (
        <p className="text-sm text-muted-foreground">
          PMS approval permission and reviewer delegation are required. HRMS
          does not override them.
        </p>
      ) : null}
    </div>
  );
}

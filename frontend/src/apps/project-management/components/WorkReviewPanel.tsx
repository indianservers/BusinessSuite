import { RichTextField, RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import { useEffect, useState } from "react";
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
}: {
  taskId?: number;
  submissionId?: number;
  onReviewed?: () => void;
}) {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<number>();
  const [decision, setDecision] = useState("Approved");
  const [score, setScore] = useState("");
  const [communication, setCommunication] = useState("");
  const [feedback, setFeedback] = useState("");
  const [strengths, setStrengths] = useState("");
  const [improvements, setImprovements] = useState("");
  const [inspected, setInspected] = useState(false);
  const [preview, setPreview] = useState("");
  const { data, isLoading, error } = useQuery<{ items: Row[]; total: number }>({
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
  const item =
    data?.items.find((i) => i.id === (submissionId || selected)) ||
    (!submissionId ? data?.items[0] : undefined);
  useEffect(() => {
    setInspected(false);
    setScore("");
    setFeedback("");
    setStrengths("");
    setImprovements("");
    setCommunication("");
    setPreview("");
  }, [item?.id]);
  useEffect(
    () => () => {
      if (preview) URL.revokeObjectURL(preview);
    },
    [preview],
  );
  const mutation = useMutation({
    mutationFn: () =>
      api.post(`/project-management/work/submissions/${item!.id}/review`, {
        status: decision,
        score: Number(score),
        communication_score:
          communication === "" ? null : Number(communication),
        feedback,
        strengths,
        improvements,
        inspected,
      }),
    onSuccess: () => {
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
  async function openFile(id: number) {
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
  if (isLoading) return <p>Loading PMS submissions…</p>;
  if (error)
    return <p role="alert">PMS access is required to read this evidence.</p>;
  if (!item)
    return (
      <p className="text-sm text-muted-foreground">
        No PMS submission selected. Interns' submitted work appears here.
      </p>
    );
  return (
    <div className="space-y-5">
      {!submissionId && (
        <label className="block text-sm">
          Submission version
          <select
            className="mt-2 w-full rounded-md border bg-background p-2"
            value={item.id}
            onChange={(e) => setSelected(Number(e.target.value))}
          >
            {data?.items.map((i) => (
              <option key={i.id} value={i.id}>
                {i.user_name || `User ${i.user_id}`} ·{" "}
                {i.task_title || `Task ${i.task_id}`} · Version {i.version} ·{" "}
                {i.status}
              </option>
            ))}
          </select>
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
      <div className="whitespace-pre-wrap rounded-lg bg-muted/30 p-4 text-sm"><RichTextContent value={item.notes}/></div>
      {item.revision_note && (
        <p className="text-sm">
          <b>Revision note:</b> {item.revision_note}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {item.files.map((id: number) => (
          <Button
            key={id}
            variant="outline"
            size="sm"
            onClick={() => openFile(id)}
          >
            Inspect Evidence #{id}
          </Button>
        ))}
      </div>
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
          <a
            href={preview}
            download={`pms-evidence-${item.id}`}
            className="text-sm text-primary underline"
          >
            Download opened evidence
          </a>
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
          <div className="mt-2 whitespace-pre-wrap"><RichTextContent value={item.feedback}/></div>
          {item.strengths && <p>Strengths: {item.strengths}</p>}
          {item.improvements && <p>Improvements: {item.improvements}</p>}
        </div>
      )}
      {item.status === "Pending Review" && item.can_review !== false ? (
        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
        >
          <Label>
            Decision
            <select
              className="mt-2 w-full rounded-md border bg-background p-2"
              value={decision}
              onChange={(e) => setDecision(e.target.value)}
            >
              {["Approved", "Needs Revision", "Rejected"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Label>
          <Label>
            Score (maximum {item.maximum_score || 100})
            <Input
              required
              min={0}
              max={item.maximum_score || 100}
              type="number"
              value={score}
              onChange={(e) => setScore(e.target.value)}
            />
          </Label>
          <Label>
            Communication score / 100 (optional)
            <Input
              min={0}
              max={100}
              type="number"
              value={communication}
              onChange={(e) => setCommunication(e.target.value)}
            />
          </Label>
          <Label className="sm:col-span-2">
            Feedback
            <RichTextField data-legacy-format="markdown"
              required
              maxLength={5000}
              className="mt-2 w-full rounded-md border bg-background p-3 text-sm"
              rows={3}
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
            />
          </Label>
          <Label>
            Strengths
            <Input
              value={strengths}
              onChange={(e) => setStrengths(e.target.value)}
            />
          </Label>
          <Label>
            Improvements
            <Input
              value={improvements}
              onChange={(e) => setImprovements(e.target.value)}
            />
          </Label>
          <label className="flex items-start gap-2 text-sm sm:col-span-2">
            <input
              type="checkbox"
              checked={inspected}
              onChange={(e) => setInspected(e.target.checked)}
            />
            I have inspected this version's evidence and notes before making
            this decision.
          </label>
          <Button disabled={mutation.isPending || !inspected || score === ""}>
            Save PMS Review
          </Button>
        </form>
      ) : item.status === "Pending Review" ? (
        <p className="text-sm text-muted-foreground">
          PMS approval permission and reviewer delegation are required. HRMS
          does not override them.
        </p>
      ) : null}
    </div>
  );
}

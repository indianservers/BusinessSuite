import { useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { toast } from "@/hooks/use-toast";
import { aiAgentsApi, type AiApproval } from "@/services/aiAgentsApi";

type ApprovalLike = Partial<AiApproval> & {
  approval_id?: number | string;
  proposed_action?: Record<string, unknown>;
};

export default function ProposedActionCard({
  approval,
  onStatusChange,
}: {
  approval: ApprovalLike;
  onStatusChange?: () => void;
}) {
  const approvalId = approval.id ?? approval.approval_id;
  const [status, setStatus] = useState(approval.status || "pending");
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [executionResult, setExecutionResult] = useState<Record<string, unknown> | null>(
    approval.execution_result_json || null
  );
  const proposed = approval.proposed_action_json || approval.proposed_action || {};

  const approve = async () => {
    if (!approvalId) return;
    const confirmed = window.confirm("Are you sure you want to approve and execute this AI proposed action?");
    if (!confirmed) return;
    setSaving(true);
    try {
      const response = await aiAgentsApi.approveAiAction(approvalId);
      setStatus(response.data.status);
      setExecutionResult(response.data.execution_result_json || null);
      if (response.data.status === "failed") {
        toast({
          title: "AI action execution failed",
          description: String(response.data.execution_result_json?.message || "Review the execution result."),
          variant: "destructive",
        });
      } else {
        toast({ title: "AI action approved and executed" });
      }
      onStatusChange?.();
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      toast({
        title: "Could not approve action",
        description: typeof detail === "string" ? detail : detail?.message || "The approved action could not be executed.",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const reject = async () => {
    if (!approvalId || !reason.trim()) return;
    setSaving(true);
    try {
      const response = await aiAgentsApi.rejectAiAction(approvalId, { rejected_reason: reason.trim() });
      setStatus(response.data.status);
      setRejecting(false);
      toast({ title: "AI action rejected" });
      onStatusChange?.();
    } catch (error: any) {
      toast({ title: "Could not reject action", description: error?.response?.data?.detail, variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="border-amber-200 bg-amber-50/50 dark:border-amber-900/60 dark:bg-amber-950/20">
      <CardContent className="space-y-3 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold">Approval required</p>
            <p className="text-xs text-muted-foreground">
              {approval.module || "AI"} / {approval.action_type || "proposed_action"}
              {approval.related_entity_type ? ` / ${approval.related_entity_type} #${approval.related_entity_id || ""}` : ""}
            </p>
          </div>
          <Badge variant={status === "pending" ? "warning" : status === "approved" ? "success" : status === "failed" ? "destructive" : "secondary"}>{status}</Badge>
        </div>

        <pre className="max-h-56 overflow-auto rounded-md border bg-background p-3 text-xs">
          {JSON.stringify(proposed, null, 2)}
        </pre>

        {executionResult ? (
          <div className="rounded-md border bg-background p-3">
            <p className="mb-2 text-xs font-semibold text-muted-foreground">Execution result</p>
            <pre className="max-h-44 overflow-auto text-xs">{JSON.stringify(executionResult, null, 2)}</pre>
          </div>
        ) : null}

        {status === "pending" ? (
          <div className="space-y-2">
            {rejecting ? (
              <textarea
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                rows={3}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                placeholder="Reason for rejection"
              />
            ) : null}
            <div className="flex flex-wrap justify-end gap-2">
              <Button type="button" size="sm" onClick={approve} disabled={saving}>
                <CheckCircle2 className="h-4 w-4" />
                Approve
              </Button>
              {rejecting ? (
                <Button type="button" size="sm" variant="destructive" onClick={reject} disabled={saving || !reason.trim()}>
                  Reject action
                </Button>
              ) : (
                <Button type="button" size="sm" variant="outline" onClick={() => setRejecting(true)} disabled={saving}>
                  <XCircle className="h-4 w-4" />
                  Reject
                </Button>
              )}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

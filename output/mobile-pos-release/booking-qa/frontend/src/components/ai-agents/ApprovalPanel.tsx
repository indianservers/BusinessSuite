import ProposedActionCard from "@/components/ai-agents/ProposedActionCard";
import type { AiApproval } from "@/services/aiAgentsApi";

export default function ApprovalPanel({
  approvals,
  onStatusChange,
}: {
  approvals: AiApproval[];
  onStatusChange?: () => void;
}) {
  if (!approvals.length) {
    return <div className="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">No pending AI approvals.</div>;
  }

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {approvals.map((approval) => (
        <ProposedActionCard key={approval.id} approval={approval} onStatusChange={onStatusChange} />
      ))}
    </div>
  );
}


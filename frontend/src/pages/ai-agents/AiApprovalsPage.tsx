import { useInitialLoading } from "@/hooks/use-initial-loading";
import { useEffect, useState } from "react";
import ApprovalPanel from "@/components/ai-agents/ApprovalPanel";
import { aiAgentsApi, type AiApproval, type AiModule } from "@/services/aiAgentsApi";

const filters: Array<AiModule | "ALL"> = ["ALL", "CRM", "PMS", "HRMS", "CROSS"];

export default function AiApprovalsPage() {
  const [approvals, setApprovals] = useState<AiApproval[]>([]);
  const [filter, setFilter] = useState<AiModule | "ALL">("ALL");
  const [loading, setLoading] = useState(true);
  const initialLoading = useInitialLoading(loading);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    aiAgentsApi
      .getPendingApprovals(filter === "ALL" ? undefined : { module: filter })
      .then((response) => setApprovals(response.data))
      .catch((err) => setError(err?.response?.data?.detail || "Pending AI approvals could not be loaded."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [filter]);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Pending AI Approvals</h1>
        <p className="text-sm text-muted-foreground">Review AI-proposed actions before anything risky is executed.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {filters.map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => setFilter(item)}
            className={`rounded-full border px-3 py-1 text-xs font-medium ${filter === item ? "border-primary bg-primary text-primary-foreground" : "bg-background text-muted-foreground hover:text-foreground"}`}
          >
            {item === "ALL" ? "All" : item === "CROSS" ? "Cross-module" : item}
          </button>
        ))}
      </div>
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div> : null}
      {initialLoading ? <div className="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">Pending approvals loading...</div> : <ApprovalPanel approvals={approvals} onStatusChange={load} />}
    </div>
  );
}


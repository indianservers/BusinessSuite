import { NativeSelect } from "@/components/ui/native-select";
import { useEffect, useMemo, useState } from "react";
import AuditLogTable from "@/components/ai-agents/AuditLogTable";
import { aiAgentsApi, type AiAuditLog, type AiModule } from "@/services/aiAgentsApi";

const modules: Array<AiModule | "ALL"> = ["ALL", "CRM", "PMS", "HRMS", "CROSS"];

export default function AiAuditLogsPage() {
  const [logs, setLogs] = useState<AiAuditLog[]>([]);
  const [moduleFilter, setModuleFilter] = useState<AiModule | "ALL">("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    aiAgentsApi
      .getAiLogs(moduleFilter === "ALL" ? undefined : { module: moduleFilter })
      .then((response) => setLogs(response.data))
      .catch((err) => setError(err?.response?.data?.detail || "AI activity logs could not be loaded."))
      .finally(() => setLoading(false));
  }, [moduleFilter]);

  const visibleLogs = useMemo(() => {
    return statusFilter === "ALL" ? logs : logs.filter((log) => log.status === statusFilter);
  }, [logs, statusFilter]);

  const statuses = ["ALL", ...Array.from(new Set(logs.map((log) => log.status).filter(Boolean)))];

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">AI Activity Logs</h1>
        <p className="text-sm text-muted-foreground">Audit trail for AI conversations, tool calls, approvals, and failures.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {modules.map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => setModuleFilter(item)}
            className={`rounded-full border px-3 py-1 text-xs font-medium ${moduleFilter === item ? "border-primary bg-primary text-primary-foreground" : "bg-background text-muted-foreground hover:text-foreground"}`}
          >
            {item === "ALL" ? "All modules" : item}
          </button>
        ))}
        <NativeSelect value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="h-8 rounded-full border bg-background px-3 text-xs">
          {statuses.map((status) => <option key={status} value={status}>{status === "ALL" ? "All statuses" : status}</option>)}
        </NativeSelect>
      </div>
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div> : null}
      {loading ? <div className="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">AI logs loading...</div> : <AuditLogTable logs={visibleLogs} />}
    </div>
  );
}


import { Badge } from "@/components/ui/badge";
import type { AiAuditLog } from "@/services/aiAgentsApi";

export default function AuditLogTable({ logs }: { logs: AiAuditLog[] }) {
  if (!logs.length) {
    return <div className="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">No AI audit logs found.</div>;
  }

  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      <div className="hidden grid-cols-[12rem_7rem_1fr_7rem_12rem] gap-3 border-b bg-muted/40 px-4 py-3 text-xs font-semibold uppercase text-muted-foreground md:grid">
        <span>Date/time</span>
        <span>Module</span>
        <span>Action</span>
        <span>Status</span>
        <span>Related entity</span>
      </div>
      <div className="divide-y">
        {logs.map((log) => (
          <details key={log.id} className="group">
            <summary className="grid cursor-pointer gap-2 px-4 py-3 text-sm hover:bg-muted/35 md:grid-cols-[12rem_7rem_1fr_7rem_12rem]">
              <span className="text-muted-foreground">{log.created_at ? new Date(log.created_at).toLocaleString() : "-"}</span>
              <span>{log.module || "-"}</span>
              <span className="font-medium">{log.action}</span>
              <Badge className="w-fit" variant={log.status === "success" ? "success" : "warning"}>{log.status}</Badge>
              <span className="text-muted-foreground">{log.related_entity_type ? `${log.related_entity_type} #${log.related_entity_id || ""}` : "-"}</span>
            </summary>
            <div className="grid gap-3 bg-muted/20 px-4 pb-4 text-xs md:grid-cols-2">
              <pre className="max-h-64 overflow-auto rounded-md border bg-background p-3">{JSON.stringify(log.input_json || {}, null, 2)}</pre>
              <pre className="max-h-64 overflow-auto rounded-md border bg-background p-3">{JSON.stringify(log.output_json || {}, null, 2)}</pre>
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}


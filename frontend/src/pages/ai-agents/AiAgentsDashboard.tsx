import {useAuthStore} from "@/store/authStore";
import {useAiAdministration} from "@/hooks/use-ai-administration";
import { useInitialLoading } from "@/hooks/use-initial-loading";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, Bot, CheckCircle2, Clock, Filter, ShieldCheck } from "lucide-react";
import AgentList from "@/components/ai-agents/AgentList";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/hooks/use-toast";
import { aiAgentsApi, type AiAgent, type AiApproval, type AiAuditLog, type AiConversation, type AiModule } from "@/services/aiAgentsApi";

const filters: Array<AiModule | "ALL"> = ["ALL", "CRM", "PMS", "HRMS", "CROSS"];

export default function AiAgentsDashboard() {
  const canAdmin=useAiAdministration();
  const canToggleCatalog=useAuthStore(state=>!!state.user?.is_superuser);
  const [agents, setAgents] = useState<AiAgent[]>([]);
  const [approvals, setApprovals] = useState<AiApproval[]>([]);
  const [logs, setLogs] = useState<AiAuditLog[]>([]);
  const [conversations, setConversations] = useState<AiConversation[]>([]);
  const [filter, setFilter] = useState<AiModule | "ALL">("ALL");
  const [loading, setLoading] = useState(true);
  const initialLoading = useInitialLoading(loading);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      aiAgentsApi.getAgents(),
      aiAgentsApi.getPendingApprovals().catch(() => ({ data: [] as AiApproval[] })),
      aiAgentsApi.getAiLogs().catch(() => ({ data: [] as AiAuditLog[] })),
      aiAgentsApi.getConversations().catch(() => ({ data: [] as AiConversation[] })),
    ])
      .then(([agentResponse, approvalResponse, logResponse, conversationResponse]) => {
        setAgents(agentResponse.data);
        setApprovals(approvalResponse.data);
        setLogs(logResponse.data);
        setConversations(conversationResponse.data);
      })
      .catch((err) => setError(err?.response?.data?.detail || "AI Agents could not be loaded."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const today = new Date().toISOString().slice(0, 10);
  const stats = useMemo(() => ({
    total: agents.length,
    active: agents.filter((agent) => agent.is_active).length,
    pending: approvals.length,
    actionsToday: logs.filter((log) => (log.created_at || "").startsWith(today)).length,
    conversationsToday: conversations.filter((conversation) => (conversation.created_at || "").startsWith(today)).length,
  }), [agents, approvals.length, conversations, logs, today]);

  const toggleAgentStatus = async (agent: AiAgent) => {
    try {
      const response = await aiAgentsApi.updateAgentStatus(agent.id, { is_active: !agent.is_active });
      setAgents((items) => items.map((item) => item.id === agent.id ? response.data : item));
      toast({ title: response.data.is_active ? "Agent enabled" : "Agent disabled" });
    } catch (err: any) {
      toast({ title: "Could not update agent", description: err?.response?.data?.detail, variant: "destructive" });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">AI Agents</h1>
          <p className="text-sm text-muted-foreground">Assistants that use safe backend tools across CRM, PMS, and HRMS.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline"><Link to="/ai-agents/approvals">Pending approvals</Link></Button>
          <Button asChild variant="outline"><Link to="/ai-agents/logs">Activity logs</Link></Button>
          <Button asChild><Link to="/ai-agents/config">Configuration</Link></Button>
        </div>
      </div>

      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div> : null}
      {initialLoading ? <div className="rounded-md border bg-card p-8 text-center text-sm text-muted-foreground">AI Agent dashboard is loading...</div> : null}

      {!initialLoading ? (
        <>
          <div className="grid gap-3 md:grid-cols-5">
            <SummaryCard icon={Bot} label="Total agents" value={stats.total} />
            <SummaryCard icon={CheckCircle2} label="Active agents" value={stats.active} />
            <SummaryCard icon={ShieldCheck} label="Pending approvals" value={stats.pending} />
            <SummaryCard icon={Activity} label="AI actions today" value={stats.actionsToday} />
            <SummaryCard icon={Clock} label="Conversations today" value={stats.conversationsToday} />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
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

          <AgentList agents={agents} moduleFilter={filter} canConfigure={canAdmin} onToggleStatus={canToggleCatalog?toggleAgentStatus:undefined} />

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader><CardTitle>Recent Conversations</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {conversations.slice(0, 6).map((conversation) => (
                  <Link key={conversation.id} to={`/ai-agents/chat/${conversation.agent_id}?conversation_id=${conversation.id}`} className="block rounded-md border p-3 text-sm hover:bg-muted/40">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium">{conversation.title || "AI conversation"}</span>
                      <Badge variant="outline">{conversation.module}</Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{conversation.created_at ? new Date(conversation.created_at).toLocaleString() : ""}</p>
                  </Link>
                ))}
                {!conversations.length ? <p className="text-sm text-muted-foreground">No conversations yet.</p> : null}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Recent AI Activity</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {logs.slice(0, 6).map((log) => (
                  <div key={log.id} className="rounded-md border p-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium">{log.action}</span>
                      <Badge variant={log.status === "success" ? "success" : "warning"}>{log.status}</Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{log.module || "AI"} / {log.created_at ? new Date(log.created_at).toLocaleString() : ""}</p>
                  </div>
                ))}
                {!logs.length ? <p className="text-sm text-muted-foreground">No AI activity logged yet.</p> : null}
              </CardContent>
            </Card>
          </div>
        </>
      ) : null}
    </div>
  );
}

function SummaryCard({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: number }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <div className="rounded-lg bg-primary/10 p-2 text-primary"><Icon className="h-4 w-4" /></div>
        <div>
          <p className="text-2xl font-semibold">{value}</p>
          <p className="text-xs text-muted-foreground">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}


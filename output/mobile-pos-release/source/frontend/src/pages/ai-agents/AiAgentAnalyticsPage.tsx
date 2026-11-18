import { useEffect, useState } from "react";
import type { ElementType } from "react";
import { BarChart3, DollarSign, MessageSquare, ShieldCheck, ThumbsUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { aiAgentsApi } from "@/services/aiAgentsApi";

export default function AiAgentAnalyticsPage() {
  const [summary, setSummary] = useState<Record<string, any>>({});
  const [byAgent, setByAgent] = useState<any[]>([]);
  const [byModule, setByModule] = useState<any[]>([]);
  const [cost, setCost] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      aiAgentsApi.getAnalyticsSummary(),
      aiAgentsApi.getAnalyticsByAgent(),
      aiAgentsApi.getAnalyticsByModule(),
      aiAgentsApi.getAnalyticsCost(),
    ])
      .then(([summaryResponse, agentResponse, moduleResponse, costResponse]) => {
        setSummary(summaryResponse.data);
        setByAgent(agentResponse.data);
        setByModule(moduleResponse.data);
        setCost(costResponse.data);
      })
      .catch((err) => setError(err?.response?.data?.detail || "AI analytics could not be loaded."));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">AI Analytics</h1>
        <p className="text-sm text-muted-foreground">Usage, approvals, feedback, failures, and cost across AI Agents.</p>
      </div>
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div> : null}
      <div className="grid gap-3 md:grid-cols-5">
        <Metric icon={MessageSquare} label="Conversations" value={summary.conversations || 0} />
        <Metric icon={BarChart3} label="Messages" value={summary.messages || 0} />
        <Metric icon={ShieldCheck} label="Approvals" value={summary.approvals || 0} />
        <Metric icon={ThumbsUp} label="Feedback" value={summary.feedback || 0} />
        <Metric icon={DollarSign} label="Failed tools" value={summary.failed_tool_calls || 0} />
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <ListCard title="By Agent" rows={byAgent.map((row) => [row.agent, row.conversations])} />
        <ListCard title="By Module" rows={byModule.map((row) => [row.module || "Unknown", row.conversations])} />
        <ListCard title="Cost" rows={cost.map((row) => [row.model || "Unknown", `${row.total_tokens || 0} tokens / ₹${Number(row.estimated_cost || 0).toFixed(4)}`])} />
      </div>
    </div>
  );
}

function Metric({ icon: Icon, label, value }: { icon: ElementType; label: string; value: number }) {
  return (
    <Card><CardContent className="flex items-center gap-3 p-4"><Icon className="h-5 w-5 text-primary" /><div><p className="text-2xl font-semibold">{value}</p><p className="text-xs text-muted-foreground">{label}</p></div></CardContent></Card>
  );
}

function ListCard({ title, rows }: { title: string; rows: Array<[string, any]> }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent className="space-y-2">
        {rows.map(([label, value]) => <div key={`${label}-${value}`} className="flex items-center justify-between rounded-md border p-3 text-sm"><span>{label}</span><Badge variant="outline">{value}</Badge></div>)}
        {!rows.length ? <p className="text-sm text-muted-foreground">No analytics available yet.</p> : null}
      </CardContent>
    </Card>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AgentConfigForm from "@/components/ai-agents/AgentConfigForm";
import { toast } from "@/hooks/use-toast";
import { aiAgentsApi, type AiAgentConfigRow, type AiModule } from "@/services/aiAgentsApi";

const filters: Array<AiModule | "ALL"> = ["ALL", "CRM", "PMS", "HRMS", "CROSS"];

export default function AiAgentConfigPage() {
  const [rows, setRows] = useState<AiAgentConfigRow[]>([]);
  const [filter, setFilter] = useState<AiModule | "ALL">("ALL");
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    aiAgentsApi
      .getAgentConfig()
      .then((response) => setRows(response.data))
      .catch((err) => setError(err?.response?.data?.detail || "AI Agent configuration could not be loaded."))
      .finally(() => setLoading(false));
  }, []);

  const updateRow = (next: AiAgentConfigRow) => {
    setRows((items) => items.map((item) => item.agent.id === next.agent.id ? next : item));
  };

  const save = async (row: AiAgentConfigRow) => {
    setSavingId(row.agent.id);
    try {
      await aiAgentsApi.updateAgentConfig(row.agent.id, row.setting);
      toast({ title: "Agent configuration saved" });
    } catch (err: any) {
      toast({ title: "Could not save configuration", description: err?.response?.data?.detail, variant: "destructive" });
    } finally {
      setSavingId(null);
    }
  };

  const visibleRows = filter === "ALL" ? rows : rows.filter((row) => row.agent.module === filter);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">AI Agent Configuration</h1>
        <p className="text-sm text-muted-foreground">Enable agents, approval policy, and data access scope.</p>
        <Link className="text-primary underline" to="/pms/settings/ai/openai">Configure OpenAI, Gemini and Claude APIs · usage analytics and logs</Link>
      </div>
      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div> : null}
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
      {loading ? <div className="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">Configuration loading...</div> : null}
      {!loading ? (
        <div className="space-y-3">
          {visibleRows.map((row) => (
            <AgentConfigForm key={row.agent.id} row={row} onChange={updateRow} onSave={save} saving={savingId === row.agent.id} />
          ))}
        </div>
      ) : null}
    </div>
  );
}


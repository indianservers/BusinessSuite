import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import type { GridColumn } from "@/shared/data-grid/types";
import { Bot, Layers, CircleDot, Zap, BadgeCheck, Shield } from "lucide-react";
import {useAiAdministration,AiAdministrativeNotice} from "@/hooks/use-ai-administration";
import { useInitialLoading } from "@/hooks/use-initial-loading";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AgentConfigForm from "@/components/ai-agents/AgentConfigForm";
import { toast } from "@/hooks/use-toast";
import { aiAgentsApi, type AiAgentConfigRow, type AiModule } from "@/services/aiAgentsApi";

const filters: Array<AiModule | "ALL"> = ["ALL", "CRM", "PMS", "HRMS", "CROSS"];
const configColumns: GridColumn<AiAgentConfigRow>[] = [
  {id:"agent",title:"Agent",icon:Bot,accessor:row=>row.agent.name},
  {id:"module",title:"Module",icon:Layers,accessor:row=>row.agent.module},
  {id:"status",title:"Status",icon:CircleDot,accessor:row=>row.setting.is_enabled?"Enabled":"Disabled"},
  {id:"auto_action",title:"Auto action",icon:Zap,accessor:row=>row.setting.auto_action_enabled?"Enabled":"Disabled"},
  {id:"approval",title:"Approval required",icon:BadgeCheck,accessor:row=>row.setting.approval_required?"Required":"Not required"},
  {id:"scope",title:"Data access scope",icon:Shield,accessor:row=>row.setting.data_access_scope.replace(/_/g," ")},
];

export default function AiAgentConfigPage() {
  const canAdmin=useAiAdministration();
  const [rows, setRows] = useState<AiAgentConfigRow[]>([]);
  const [filter, setFilter] = useState<AiModule | "ALL">("ALL");
  const [loading, setLoading] = useState(true);
  const initialLoading = useInitialLoading(loading);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if(!canAdmin){setLoading(false);return;}
    setLoading(true);
    aiAgentsApi
      .getAgentConfig()
      .then((response) => setRows(response.data))
      .catch((err) => setError(err?.response?.data?.detail || "AI Agent configuration could not be loaded."))
      .finally(() => setLoading(false));
  }, [canAdmin]);

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

  if(!canAdmin)return <AiAdministrativeNotice/>;
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
      {initialLoading ? <div className="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">Configuration loading...</div> : null}
      {!initialLoading ? (
        <GroupedRecords scope="pages/ai-agents/AiAgentConfigPage:cards-1" items={visibleRows} tableColumns={configColumns} fields={[{id:"module",label:"Module",value:row=>row.agent.module},{id:"status",label:"Status",value:row=>row.setting.is_enabled?"Enabled":"Disabled"}]} gridClassName="space-y-3" renderItem={(row) => (
            <AgentConfigForm key={row.agent.id} row={row} onChange={updateRow} onSave={save} saving={savingId === row.agent.id} />
          )}/>
      ) : null}
    </div>
  );
}


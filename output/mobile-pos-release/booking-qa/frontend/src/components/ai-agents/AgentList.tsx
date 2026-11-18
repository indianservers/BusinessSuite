import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import AgentCard from "@/components/ai-agents/AgentCard";
import type { AiAgent, AiModule } from "@/services/aiAgentsApi";

export default function AgentList({
  agents,
  moduleFilter = "ALL",
  canConfigure = true,
  onToggleStatus,
}: {
  agents: AiAgent[];
  moduleFilter?: AiModule | "ALL";
  canConfigure?:boolean;
  onToggleStatus?: (agent: AiAgent) => void;
}) {
  const visibleAgents = moduleFilter === "ALL" ? agents : agents.filter((agent) => agent.module === moduleFilter);

  if (!visibleAgents.length) {
    return (
      <div className="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">
        No AI agents match this module filter.
      </div>
    );
  }

  return (
    <GroupedRecords scope="ai-agents" items={visibleAgents} gridClassName="grid gap-3 md:grid-cols-2 xl:grid-cols-3" fields={[
      {id:"module",label:"Module",value:agent=>agent.module},
      {id:"status",label:"Status",value:agent=>agent.is_active?"Active":"Paused"},
      {id:"approval",label:"Approval",value:agent=>agent.requires_approval?"Requires approval":"Automatic"},
    ]} renderItem={agent=><AgentCard key={agent.id} agent={agent} canConfigure={canConfigure} onToggleStatus={onToggleStatus}/>}/>
  );
}


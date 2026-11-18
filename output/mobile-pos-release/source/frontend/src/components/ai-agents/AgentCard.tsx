import { Link } from "react-router-dom";
import { Bot, MessageSquare, Settings, ShieldCheck, ToggleLeft, ToggleRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { AiAgent } from "@/services/aiAgentsApi";

export function moduleBadgeClass(module?: string) {
  if (module === "CRM") return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300";
  if (module === "PMS") return "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300";
  if (module === "HRMS") return "bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-300";
  return "bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-300";
}

export default function AgentCard({
  agent,
  onToggleStatus,
  canConfigure = true,
}: {
  agent: AiAgent;
  onToggleStatus?: (agent: AiAgent) => void;
  canConfigure?: boolean;
}) {
  return (
    <Card className="h-full">
      <CardContent className="flex h-full flex-col gap-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Bot className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <h3 className="truncate text-base font-semibold">{agent.name}</h3>
              <p className="mt-1 text-xs text-muted-foreground">{agent.code}</p>
            </div>
          </div>
          <Badge className={moduleBadgeClass(agent.module)}>{agent.module === "CROSS" ? "Cross-module" : agent.module}</Badge>
        </div>

        <p className="line-clamp-3 min-h-[3.75rem] text-sm text-muted-foreground">
          {agent.description || "Configured AI agent for safe business-suite assistance."}
        </p>

        <div className="flex flex-wrap gap-2">
          <Badge variant={agent.is_active ? "success" : "secondary"}>{agent.is_active ? "Active" : "Inactive"}</Badge>
          <Badge variant={agent.requires_approval ? "warning" : "info"}>
            <ShieldCheck className="mr-1 h-3 w-3" />
            {agent.requires_approval ? "Approval Required" : "Auto Safe"}
          </Badge>
        </div>

        <div className="mt-auto flex flex-wrap gap-2">
          <Button asChild size="sm">
            <Link to={`/ai-agents/chat/${agent.id}`}>
              <MessageSquare className="h-4 w-4" />
              Chat
            </Link>
          </Button>
          {canConfigure ? (
            <Button asChild size="sm" variant="outline">
              <Link to="/ai-agents/config">
                <Settings className="h-4 w-4" />
                Configure
              </Link>
            </Button>
          ) : null}
          {onToggleStatus ? (
            <Button type="button" size="sm" variant="ghost" onClick={() => onToggleStatus(agent)}>
              {agent.is_active ? <ToggleRight className="h-4 w-4" /> : <ToggleLeft className="h-4 w-4" />}
              {agent.is_active ? "Disable" : "Enable"}
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}


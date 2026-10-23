import { useNavigate } from "react-router-dom";
import { useRef, useState } from "react";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "@/hooks/use-toast";
import { aiAgentsApi, type AiModule } from "@/services/aiAgentsApi";

export default function AskAiButton({
  module,
  relatedEntityType,
  relatedEntityId,
  defaultAgentCode,
  defaultPrompt,
  buttonLabel = "Ask AI",
  size = "sm",
  variant = "outline",
}: {
  module: AiModule;
  relatedEntityType?: string;
  relatedEntityId?: string | number;
  defaultAgentCode?: string;
  defaultPrompt?: string;
  buttonLabel?: string;
  size?: "sm" | "default";
  variant?: "outline" | "default" | "ghost";
}) {
  const navigate = useNavigate();
  const openingRef = useRef(false);
  const [opening, setOpening] = useState(false);

  const openAi = async () => {
    if (openingRef.current) return;
    openingRef.current = true;
    setOpening(true);
    try {
      const response = await aiAgentsApi.getAgents({ module });
      const agents = response.data;
      const activeAgents = agents.filter(item => item.is_active);
      const agent = activeAgents.find((item) => item.code === defaultAgentCode) || activeAgents[0];
      if (!agent) {
        toast({ title: "No AI agent is available", description: "AI Agents are not configured for this module yet.", variant: "destructive" });
        return;
      }
      const params = new URLSearchParams();
      params.set("module", module);
      if (relatedEntityType) params.set("related_entity_type", relatedEntityType);
      if (relatedEntityId !== undefined && relatedEntityId !== null) params.set("related_entity_id", String(relatedEntityId));
      if (defaultPrompt) params.set("prompt", defaultPrompt);
      navigate(`/ai-agents/chat/${agent.id}?${params.toString()}`);
    } catch (error: any) {
      toast({ title: "Could not open AI Agent", description: error?.response?.data?.detail || "Please try again.", variant: "destructive" });
    } finally {
      openingRef.current = false;
      setOpening(false);
    }
  };

  return (
    <Button type="button" size={size} variant={variant} onClick={openAi} disabled={opening} aria-busy={opening}>
      <Sparkles className="h-4 w-4" />
      {opening ? "Opening agent…" : buttonLabel}
    </Button>
  );
}


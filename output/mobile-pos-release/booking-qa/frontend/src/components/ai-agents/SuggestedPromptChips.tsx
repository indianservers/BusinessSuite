import type { AiAgent, AiModule } from "@/services/aiAgentsApi";

const prompts: Record<AiModule, string[]> = {
  CRM: [
    "Qualify this lead",
    "Summarize this customer",
    "Analyze this deal",
    "Find overdue follow-ups",
    "Draft follow-up message",
  ],
  PMS: [
    "Summarize this project",
    "Identify delayed tasks",
    "Find blockers",
    "Create task plan",
    "Generate weekly status report",
  ],
  HRMS: [
    "Explain leave policy",
    "Check leave balance",
    "Screen this candidate",
    "Analyze attendance issue",
    "Draft HR letter",
  ],
  CROSS: [
    "Give today's business summary",
    "Show pending approvals",
    "What needs my attention today?",
    "Search across business suite",
    "Show major risks this week",
  ],
};

export default function SuggestedPromptChips({
  agent,
  onPick,
}: {
  agent?: AiAgent | null;
  onPick: (prompt: string) => void;
}) {
  const items = prompts[agent?.module || "CROSS"] || prompts.CROSS;
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((prompt) => (
        <button
          key={prompt}
          type="button"
          onClick={() => onPick(prompt)}
          className="rounded-full border bg-background px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-primary hover:text-primary"
        >
          {prompt}
        </button>
      ))}
    </div>
  );
}


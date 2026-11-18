import { Bot, ChevronDown, ChevronRight, ThumbsDown, ThumbsUp, UserRound, Wrench } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { aiAgentsApi, type AiMessage } from "@/services/aiAgentsApi";

function renderPlainMarkdown(text: string) {
  return text
    .split("\n")
    .map((line, index) => {
      if (line.startsWith("### ")) return <h3 key={index} className="mt-3 font-semibold">{line.slice(4)}</h3>;
      if (line.startsWith("## ")) return <h2 key={index} className="mt-3 text-base font-semibold">{line.slice(3)}</h2>;
      if (line.startsWith("# ")) return <h1 key={index} className="mt-3 text-lg font-semibold">{line.slice(2)}</h1>;
      if (line.startsWith("- ")) return <li key={index} className="ml-5 list-disc">{line.slice(2)}</li>;
      if (!line.trim()) return <br key={index} />;
      return <p key={index} className="whitespace-pre-wrap">{line}</p>;
    });
}

export default function MessageBubble({ message }: { message: AiMessage }) {
  const [expanded, setExpanded] = useState(false);
  const [feedbackSent, setFeedbackSent] = useState(false);
  const isUser = message.role === "user";
  const isTool = message.role === "tool";
  const isAssistant = message.role === "assistant";
  const content = message.content || (isTool ? "Tool result received." : "");

  const submitFeedback = async (rating: "thumbs_up" | "thumbs_down") => {
    try {
      await aiAgentsApi.submitFeedback(message.id, {
        rating,
        feedback_type: rating === "thumbs_up" ? "helpful" : "other",
      });
      setFeedbackSent(true);
      toast({ title: "AI feedback saved" });
    } catch (err: any) {
      toast({ title: "Could not save feedback", description: err?.response?.data?.detail, variant: "destructive" });
    }
  };

  return (
    <div className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}>
      {!isUser ? (
        <div className={cn("mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full", isTool ? "bg-muted text-muted-foreground" : "bg-primary/10 text-primary")}>
          {isTool ? <Wrench className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
        </div>
      ) : null}
      <div
        className={cn(
          "max-w-[min(44rem,85vw)] rounded-lg border px-4 py-3 text-sm",
          isUser ? "bg-primary text-primary-foreground" : "bg-card",
          isTool && "border-dashed bg-muted/35"
        )}
      >
        <div className="mb-1 flex items-center gap-2">
          <Badge variant={isUser ? "secondary" : isTool ? "outline" : "info"}>{message.role}</Badge>
          {message.created_at ? <span className="text-xs opacity-70">{new Date(message.created_at).toLocaleString()}</span> : null}
        </div>
        <div className="space-y-1">{renderPlainMarkdown(content)}</div>
        {(message.tool_call_json || message.tool_result_json) ? (
          <div className="mt-3">
            <button
              type="button"
              className="inline-flex items-center gap-1 text-xs font-medium opacity-80 hover:opacity-100"
              onClick={() => setExpanded((value) => !value)}
            >
              {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
              Technical preview
            </button>
            {expanded ? (
              <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-background/70 p-3 text-xs text-foreground">
                {JSON.stringify(message.tool_call_json || message.tool_result_json, null, 2)}
              </pre>
            ) : null}
          </div>
        ) : null}
        {isAssistant ? (
          <div className="mt-3 flex items-center gap-2 border-t pt-2">
            <span className="text-xs text-muted-foreground">{feedbackSent ? "Feedback saved" : "Rate response"}</span>
            <Button size="icon" variant="ghost" className="h-7 w-7" disabled={feedbackSent} onClick={() => submitFeedback("thumbs_up")}><ThumbsUp className="h-3.5 w-3.5" /></Button>
            <Button size="icon" variant="ghost" className="h-7 w-7" disabled={feedbackSent} onClick={() => submitFeedback("thumbs_down")}><ThumbsDown className="h-3.5 w-3.5" /></Button>
          </div>
        ) : null}
      </div>
      {isUser ? (
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <UserRound className="h-4 w-4" />
        </div>
      ) : null}
    </div>
  );
}

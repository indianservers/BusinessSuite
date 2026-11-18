import { Link } from "react-router-dom";
import { MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AiConversation } from "@/services/aiAgentsApi";

export default function ConversationSidebar({
  conversations,
  activeConversationId,
  agentId,
}: {
  conversations: AiConversation[];
  activeConversationId?: number | null;
  agentId: number | string;
}) {
  return (
    <aside className="rounded-lg border bg-card">
      <div className="border-b p-4">
        <p className="text-sm font-semibold">Conversations</p>
        <p className="text-xs text-muted-foreground">Your recent AI chats</p>
      </div>
      <div className="max-h-[34rem] overflow-y-auto p-2">
        {conversations.map((conversation) => (
          <Link
            key={conversation.id}
            to={`/ai-agents/chat/${agentId}?conversation_id=${conversation.id}`}
            className={cn(
              "mb-1 flex items-start gap-2 rounded-md px-3 py-2 text-sm hover:bg-muted",
              activeConversationId === conversation.id && "bg-muted"
            )}
          >
            <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="min-w-0">
              <span className="block truncate font-medium">{conversation.title || "AI conversation"}</span>
              <span className="block truncate text-xs text-muted-foreground">
                {conversation.related_entity_type ? `${conversation.related_entity_type} #${conversation.related_entity_id || ""}` : conversation.module}
              </span>
            </span>
          </Link>
        ))}
        {!conversations.length ? (
          <p className="px-3 py-6 text-center text-xs text-muted-foreground">No conversations yet.</p>
        ) : null}
      </div>
    </aside>
  );
}


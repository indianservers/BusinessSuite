import CompactForm from "@/components/forms/CompactForm";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, Download, Send, Sparkles } from "lucide-react";
import ConversationSidebar from "@/components/ai-agents/ConversationSidebar";
import MessageBubble from "@/components/ai-agents/MessageBubble";
import ModuleContextPanel from "@/components/ai-agents/ModuleContextPanel";
import ProposedActionCard from "@/components/ai-agents/ProposedActionCard";
import SuggestedPromptChips from "@/components/ai-agents/SuggestedPromptChips";
import ToolCallPreview from "@/components/ai-agents/ToolCallPreview";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { aiAgentsApi, type AiAgent, type AiChatResponse, type AiConversation, type AiMessage, type AiModule } from "@/services/aiAgentsApi";

export default function AiAgentChatPage() {
  const { agentId = "" } = useParams<{ agentId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const [agent, setAgent] = useState<AiAgent | null>(null);
  const [conversations, setConversations] = useState<AiConversation[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(() => Number(searchParams.get("conversation_id")) || null);
  const [messages, setMessages] = useState<AiMessage[]>([]);
  const [input, setInput] = useState(searchParams.get("prompt") || "");
  const [loading, setLoading] = useState(true);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [responding, setResponding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResponse, setLastResponse] = useState<AiChatResponse | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const module = (searchParams.get("module") || agent?.module || "CROSS") as AiModule;
  const relatedEntityType = searchParams.get("related_entity_type");
  const relatedEntityId = searchParams.get("related_entity_id");

  useEffect(() => {
    setLoading(true);
    Promise.all([
      aiAgentsApi.getAgent(agentId),
      aiAgentsApi.getConversations({ agent_id: agentId }),
    ])
      .then(([agentResponse, conversationResponse]) => {
        setAgent(agentResponse.data);
        setConversations(conversationResponse.data);
      })
      .catch((err) => setError(err?.response?.data?.detail || "AI Agent could not be loaded."))
      .finally(() => setLoading(false));
  }, [agentId]);

  useEffect(() => {
    const idFromUrl = Number(searchParams.get("conversation_id")) || null;
    setConversationId(idFromUrl);
  }, [searchParams]);

  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      return;
    }
    setMessagesLoading(true);
    aiAgentsApi
      .getConversationMessages(conversationId)
      .then((response) => setMessages(response.data))
      .catch((err) => setError(err?.response?.data?.detail || "Conversation messages could not be loaded."))
      .finally(() => setMessagesLoading(false));
  }, [conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, responding]);

  const currentConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === conversationId),
    [conversationId, conversations]
  );

  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    const message = input.trim();
    if (!message || responding) return;
    setResponding(true);
    setError(null);
    setLastResponse(null);
    const optimistic: AiMessage = {
      id: -Date.now(),
      conversation_id: conversationId || 0,
      role: "user",
      content: message,
      created_at: new Date().toISOString(),
    };
    setMessages((items) => [...items, optimistic]);
    setInput("");

    try {
      const payload: Record<string, unknown> = {
        conversation_id: conversationId || undefined,
        message,
        module,
        related_entity_type: relatedEntityType || undefined,
        related_entity_id: relatedEntityId || undefined,
      };
      const response = await aiAgentsApi.sendChatMessage(agentId, payload);
      const data = response.data;
      setLastResponse(data);
      setConversationId(Number(data.conversation_id));
      setSearchParams((current) => {
        const next = new URLSearchParams(current);
        next.set("conversation_id", String(data.conversation_id));
        next.delete("prompt");
        return next;
      });
      const messageResponse = await aiAgentsApi.getConversationMessages(data.conversation_id);
      setMessages(messageResponse.data);
      const conversationResponse = await aiAgentsApi.getConversations({ agent_id: agentId });
      setConversations(conversationResponse.data);
    } catch (err: any) {
      setMessages((items) => items.filter((item) => item.id !== optimistic.id));
      setInput(message);
      setError(err?.response?.data?.detail || "AI service is not available. Please try again.");
    } finally {
      setResponding(false);
    }
  };

  const startNewConversation = () => {
    const next = new URLSearchParams(searchParams);
    next.delete("conversation_id");
    setSearchParams(next);
    setConversationId(null);
    setMessages([]);
    setLastResponse(null);
  };

  const exportConversation = async (format: "pdf" | "csv" | "json") => {
    if (!conversationId) return;
    const response = await aiAgentsApi.exportConversation(conversationId, format);
    const url = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = `ai-conversation-${conversationId}.${format}`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (loading) return <div className="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">AI Agent is loading...</div>;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <Link to="/ai-agents" className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
            AI Agents
          </Link>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold">{agent?.name || "AI Agent Chat"}</h1>
            {agent ? <Badge variant={agent.is_active ? "success" : "secondary"}>{agent.is_active ? "Active" : "Inactive"}</Badge> : null}
          </div>
          <p className="text-sm text-muted-foreground">{agent?.description || "Chat with a backend-connected AI Agent."}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {conversationId ? (
            <>
              <Button type="button" variant="outline" onClick={() => exportConversation("pdf")}><Download className="h-4 w-4" /> PDF</Button>
              <Button type="button" variant="outline" onClick={() => exportConversation("csv")}><Download className="h-4 w-4" /> CSV</Button>
              <Button type="button" variant="outline" onClick={() => exportConversation("json")}><Download className="h-4 w-4" /> JSON</Button>
            </>
          ) : null}
          <Button type="button" variant="outline" onClick={startNewConversation}>
            <Sparkles className="h-4 w-4" />
            New chat
          </Button>
        </div>
      </div>

      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div> : null}
      {agent && !agent.is_active ? <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">This agent is inactive.</div> : null}

      <div className="grid gap-4 xl:grid-cols-[17rem_minmax(0,1fr)_20rem]">
        <ConversationSidebar conversations={conversations} activeConversationId={conversationId} agentId={agentId} />

        <Card className="min-h-[42rem]">
          <CardContent className="flex min-h-[42rem] flex-col p-0">
            <div className="border-b p-4">
              <p className="text-sm font-medium">{currentConversation?.title || "New conversation"}</p>
              <p className="text-xs text-muted-foreground">Messages are saved to AI conversation history.</p>
            </div>
            <div className="flex-1 space-y-4 overflow-y-auto p-4">
              {messagesLoading ? <p className="text-sm text-muted-foreground">Messages loading...</p> : null}
              {!messages.length && !messagesLoading ? (
                <div className="rounded-lg border bg-muted/30 p-6 text-center">
                  <Sparkles className="mx-auto h-8 w-8 text-primary" />
                  <h2 className="mt-3 font-semibold">Ask a business question</h2>
                  <p className="mt-1 text-sm text-muted-foreground">The agent will use backend tools when it needs CRM, PMS, or HRMS data.</p>
                </div>
              ) : null}
              {messages.map((message) => <MessageBubble key={message.id} message={message} />)}
              {responding ? <div className="text-sm text-muted-foreground">AI response is being prepared...</div> : null}
              <div ref={bottomRef} />
            </div>
            <CompactForm onSubmit={submit} className="border-t p-4">
              <SuggestedPromptChips agent={agent} onPick={setInput} />
              <div className="mt-3 grid gap-2 md:grid-cols-[1fr_auto]">
                <textarea
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  rows={3}
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                  placeholder="Ask the agent..."
                  disabled={responding || !agent?.is_active}
                />
                <Button type="submit" disabled={responding || !input.trim() || !agent?.is_active} className="md:self-end">
                  <Send className="h-4 w-4" />
                  Send
                </Button>
              </div>
            </CompactForm>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <ModuleContextPanel agent={agent} module={module} relatedEntityType={relatedEntityType} relatedEntityId={relatedEntityId} />
          <ToolCallPreview toolCalls={lastResponse?.tool_calls} />
          {lastResponse?.approvals?.map((approval, index) => (
            <ProposedActionCard key={String(approval.approval_id || approval.id || index)} approval={approval} />
          ))}
        </div>
      </div>
    </div>
  );
}

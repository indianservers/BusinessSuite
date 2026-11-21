import CompactForm from "@/components/forms/CompactForm";
import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Bot, Send, Sparkles, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { aiApi } from "@/services/api";
import { usePageTitle } from "@/hooks/use-page-title";
import { toast } from "@/hooks/use-toast";

type Message = { role: "user" | "assistant"; content: string };

export default function AIAssistantPage() {
  usePageTitle("AI Assistant");
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Ask me about HR policy, leave, payroll, onboarding, or employee operations." },
  ]);

  const chat = useMutation({
    mutationFn: (text: string) => aiApi.chat(text, messages.map((m) => ({ role: m.role, content: m.content }))),
    onSuccess: (response) => {
      setMessages((items) => [...items, { role: "assistant", content: response.data.response }]);
    },
    onError: () => toast({ title: "AI assistant failed", description: "Check AI API key/configuration.", variant: "destructive" }),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const text = message.trim();
    if (!text || chat.isPending) return;
    setMessages((items) => [...items, { role: "user", content: text }]);
    setMessage("");
    chat.mutate(text);
  }

  return (
    <div className="mx-auto min-w-0 max-w-5xl space-y-4">
      <div className="rounded-lg border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight">HR Assistant</h1>
        <p className="mt-1 text-sm text-muted-foreground">Policy Q&A, HR guidance, drafting help, and operational answers.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base"><Sparkles className="h-4 w-4" /> Conversation</CardTitle>
          <CardDescription>Responses depend on configured AI keys and published policies.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div role="log" aria-label="Conversation messages" className="max-h-[min(45dvh,520px)] space-y-3 overflow-y-auto rounded-lg border bg-muted/20 p-3 sm:p-4">
            {messages.map((item, index) => (
              <div key={index} className={`flex gap-3 ${item.role === "user" ? "justify-end" : "justify-start"}`}>
                {item.role === "assistant" && <Bot className="mt-1 h-5 w-5 shrink-0 text-primary" />}
                <div className={`min-w-0 max-w-[min(85%,780px)] whitespace-pre-wrap break-words rounded-lg p-3 text-sm ${item.role === "user" ? "bg-primary text-primary-foreground" : "border bg-background"}`}>
                  {item.content}
                </div>
                {item.role === "user" && <UserRound className="mt-1 h-5 w-5 shrink-0 text-muted-foreground" />}
              </div>
            ))}
            {chat.isPending && <p className="text-sm text-muted-foreground">Thinking...</p>}
          </div>

          <CompactForm onSubmit={submit} className="flex gap-2">
            <Input aria-label="HR question" className="min-h-11 min-w-0 text-base" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Ask an HR question…" />
            <Button type="submit" className="min-h-11 shrink-0" disabled={chat.isPending || !message.trim()}>
              <Send className="h-4 w-4" />
              Send
            </Button>
          </CompactForm>
        </CardContent>
      </Card>
    </div>
  );
}

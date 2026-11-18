import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/hooks/use-toast";
import { aiAgentsApi } from "@/services/aiAgentsApi";

export default function AiAgentFeedbackPage() {
  const [rows, setRows] = useState<any[]>([]);

  useEffect(() => {
    aiAgentsApi.getFeedback()
      .then((response) => setRows(response.data))
      .catch((err) => toast({ title: "AI feedback unavailable", description: err?.response?.data?.detail, variant: "destructive" }));
  }, []);

  return (
    <div className="space-y-6">
      <div><h1 className="text-2xl font-semibold">AI Feedback</h1><p className="text-sm text-muted-foreground">User ratings and quality notes for assistant responses.</p></div>
      <Card>
        <CardHeader><CardTitle>Recent Feedback</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {rows.map((row) => (
            <div key={row.id} className="rounded-md border p-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-3"><span>Message #{row.message_id}</span><Badge variant={row.rating === "thumbs_up" ? "success" : "warning"}>{row.rating}</Badge><span className="text-xs text-muted-foreground">{row.created_at ? new Date(row.created_at).toLocaleString() : ""}</span></div>
              <p className="mt-1 text-xs text-muted-foreground">{row.feedback_type || "other"} {row.feedback_text ? `- ${row.feedback_text}` : ""}</p>
            </div>
          ))}
          {!rows.length ? <p className="text-sm text-muted-foreground">No feedback submitted yet.</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}

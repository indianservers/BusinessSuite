import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/hooks/use-toast";
import { aiAgentsApi, type AiHandoffNote } from "@/services/aiAgentsApi";

export default function AiAgentHandoffPage() {
  const [saving,setSaving]=useState<number|null>(null);
  const [notes, setNotes] = useState<AiHandoffNote[]>([]);

  const load = () => {
    aiAgentsApi.getHandoffNotes()
      .then((response) => setNotes(response.data))
      .catch((err) => toast({ title: "Handoff notes unavailable", description: err?.response?.data?.detail, variant: "destructive" }));
  };
  useEffect(load, []);

  const updateStatus = async (note: AiHandoffNote, status: AiHandoffNote["status"]) => {
    if(saving!==null)return;setSaving(note.id);try{await aiAgentsApi.updateHandoffStatus(note.id,{status});toast({title:"Handoff note updated"});load();}catch(error){const detail=(error as {response?:{data?:{detail?:unknown}}}).response?.data?.detail;toast({title:"Could not update handoff",description:typeof detail==="string"?detail:"Your note is retained. Try again.",variant:"destructive"});}finally{setSaving(null);}
  };

  return (
    <div className="space-y-6">
      <div><h1 className="text-2xl font-semibold">AI Handoff Notes</h1><p className="text-sm text-muted-foreground">Human review items created when AI needs help or escalation.</p></div>
      <Card>
        <CardHeader><CardTitle>Open Work</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {notes.map((note) => (
            <div data-priority-row data-priority={note.priority} key={note.id} className="rounded-md border p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div><p className="font-medium">{note.summary}</p><p className="text-xs text-muted-foreground">{note.module} / {note.related_entity_type || "general"} {note.related_entity_id || ""}</p></div>
                <div className="flex gap-2"><Badge data-priority-badge data-priority={note.priority} variant={note.priority === "urgent" || note.priority === "high" ? "warning" : "outline"}>{note.priority}</Badge><Badge>{note.status}</Badge></div>
              </div>
              {note.reason ? <p className="mt-2 text-sm text-muted-foreground">{note.reason}</p> : null}
              {note.recommended_action ? <p className="mt-2 text-sm">{note.recommended_action}</p> : null}
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" variant="outline" disabled={saving!==null} onClick={() => updateStatus(note, "in_review")}>Review</Button>
                <Button size="sm" variant="outline" disabled={saving!==null} onClick={() => updateStatus(note, "resolved")}>Resolve</Button>
                <Button size="sm" variant="outline" disabled={saving!==null} onClick={() => updateStatus(note, "cancelled")}>Cancel</Button>
              </div>
            </div>
          ))}
          {!notes.length ? <p className="text-sm text-muted-foreground">No handoff notes found.</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}

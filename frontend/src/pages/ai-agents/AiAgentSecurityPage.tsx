import {useAiAdministration,AiAdministrativeNotice} from "@/hooks/use-ai-administration";
import { useEffect, useState } from "react";
import { AlertTriangle, Power, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { aiAgentsApi, type AiSecuritySettings } from "@/services/aiAgentsApi";

const defaultSettings: AiSecuritySettings = {
  ai_enabled: true,
  crm_ai_enabled: true,
  pms_ai_enabled: true,
  hrms_ai_enabled: true,
  cross_ai_enabled: true,
  emergency_message: "",
};

export default function AiAgentSecurityPage() {
  const canAdmin=useAiAdministration();
  const [summary, setSummary] = useState<any>({});
  const [events, setEvents] = useState<any[]>([]);
  const [settings, setSettings] = useState<AiSecuritySettings>(defaultSettings);
  const [saving, setSaving] = useState(false);

  const load = () => {
    if(!canAdmin)return;
    Promise.all([aiAgentsApi.getSecuritySummary(), aiAgentsApi.getSecurityEvents(), aiAgentsApi.getSecuritySettings()])
      .then(([summaryResponse, eventsResponse, settingsResponse]) => {
        setSummary(summaryResponse.data);
        setEvents(eventsResponse.data);
        setSettings({ ...defaultSettings, ...settingsResponse.data });
      })
      .catch((err) => toast({ title: "Security dashboard unavailable", description: err?.response?.data?.detail, variant: "destructive" }));
  };

  useEffect(load, [canAdmin]);

  const save = async () => {if(saving||!canAdmin)return;setSaving(true);try{await aiAgentsApi.updateSecuritySettings(settings);toast({title:"AI security settings saved"});load();}catch(error){const detail=(error as {response?:{data?:{detail?:unknown}}}).response?.data?.detail;toast({title:"Could not save security controls",description:typeof detail==="string"?detail:"Your controls are kept for retry.",variant:"destructive"});}finally{setSaving(false);}};

  if(!canAdmin)return <AiAdministrativeNotice/>;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">AI Security</h1>
        <p className="text-sm text-muted-foreground">Prompt protection, blocked responses, and emergency AI controls.</p>
      </div>
      <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Power className="h-4 w-4" /> Emergency Controls</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {(["ai_enabled", "crm_ai_enabled", "pms_ai_enabled", "hrms_ai_enabled", "cross_ai_enabled"] as const).map((key) => (
              <label key={key} className="flex items-center justify-between rounded-md border p-3 text-sm">
                <span>{key.replace(/_/g, " ").replace("enabled", "").trim().toUpperCase() || "AI"}</span>
                <input type="checkbox" checked={Boolean(settings[key])} onChange={(event) => setSettings((current) => ({ ...current, [key]: event.target.checked }))} />
              </label>
            ))}
            <Input value={settings.emergency_message || ""} onChange={(event) => setSettings((current) => ({ ...current, emergency_message: event.target.value }))} placeholder="Emergency disabled message" />
            <Button onClick={save} disabled={saving} className="w-full">{saving ? "Saving..." : "Save controls"}</Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck className="h-4 w-4" /> Security Summary</CardTitle></CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2">
            {Object.entries(summary.events || {}).map(([action, count]) => (
              <div key={action} className="rounded-md border p-3"><p className="text-xs text-muted-foreground">{action}</p><p className="mt-1 text-xl font-semibold">{String(count)}</p></div>
            ))}
            {!Object.keys(summary.events || {}).length ? <p className="text-sm text-muted-foreground">No blocked or risky AI events recorded.</p> : null}
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><AlertTriangle className="h-4 w-4" /> Recent Security Events</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {events.map((event) => <div key={event.id} className="flex flex-wrap items-center justify-between gap-3 rounded-md border p-3 text-sm"><span>{event.action}</span><Badge variant={event.status === "success" ? "success" : "warning"}>{event.status}</Badge><span className="text-xs text-muted-foreground">{event.created_at ? new Date(event.created_at).toLocaleString() : ""}</span></div>)}
          {!events.length ? <p className="text-sm text-muted-foreground">No security events found.</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}

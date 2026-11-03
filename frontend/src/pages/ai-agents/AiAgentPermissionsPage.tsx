import { NativeSelect } from "@/components/ui/native-select";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { aiAgentsApi, type AiAgent, type AiPermissionRule } from "@/services/aiAgentsApi";

export default function AiAgentPermissionsPage() {
  const [agents, setAgents] = useState<AiAgent[]>([]);
  const [rules, setRules] = useState<AiPermissionRule[]>([]);

  useEffect(() => {
    Promise.all([aiAgentsApi.getAgents(), aiAgentsApi.getPermissions()])
      .then(([agentsResponse, rulesResponse]) => {
        setAgents(agentsResponse.data);
        setRules(rulesResponse.data);
      })
      .catch((err) => toast({ title: "Permission matrix unavailable", description: err?.response?.data?.detail, variant: "destructive" }));
  }, []);

  const update = (index: number, patch: Partial<AiPermissionRule>) => setRules((items) => items.map((item, current) => current === index ? { ...item, ...patch } : item));
  const add = () => setRules((items) => [...items, { agent_id: agents[0]?.id || 0, can_use: true, can_configure: false, can_approve_actions: false, can_view_logs: false, can_export_conversations: false }]);
  const save = async () => {
    await aiAgentsApi.updatePermissions(rules.filter((rule) => rule.agent_id));
    toast({ title: "AI permission matrix saved" });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">AI Permission Matrix</h1>
          <p className="text-sm text-muted-foreground">Control who can use, configure, approve, view logs, and export conversations.</p>
        </div>
        <div className="flex gap-2"><Button variant="outline" onClick={add}>Add rule</Button><Button onClick={save}>Save</Button></div>
      </div>
      <Card>
        <CardHeader><CardTitle>Rules</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {rules.map((rule, index) => (
            <div key={rule.id || index} className="grid gap-3 rounded-md border p-3 md:grid-cols-[1.5fr_1fr_1fr_2fr]">
              <NativeSelect className="rounded-md border bg-background px-3 py-2 text-sm" value={rule.agent_id} onChange={(event) => update(index, { agent_id: Number(event.target.value) })}>
                {agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
              </NativeSelect>
              <Input placeholder="Role ID" value={rule.role_id || ""} onChange={(event) => update(index, { role_id: event.target.value ? Number(event.target.value) : null })} />
              <Input placeholder="User ID" value={rule.user_id || ""} onChange={(event) => update(index, { user_id: event.target.value ? Number(event.target.value) : null })} />
              <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-5">
                {(["can_use", "can_configure", "can_approve_actions", "can_view_logs", "can_export_conversations"] as const).map((field) => (
                  <label key={field} className="flex items-center gap-1 rounded border p-2"><input type="checkbox" checked={Boolean(rule[field])} onChange={(event) => update(index, { [field]: event.target.checked })} /> {field.replace("can_", "").replace(/_/g, " ")}</label>
                ))}
              </div>
            </div>
          ))}
          {!rules.length ? <p className="text-sm text-muted-foreground">No permission rules yet. Defaults apply until a rule is saved.</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}

import {useAiAdministration,AiAdministrativeNotice} from "@/hooks/use-ai-administration";
import { NativeSelect } from "@/components/ui/native-select";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { aiAgentsApi, type AiUsageLimit } from "@/services/aiAgentsApi";

export default function AiAgentUsagePage() {
  const canAdmin=useAiAdministration();
  const [saving,setSaving]=useState(false);
  const [summary, setSummary] = useState<any>({});
  const [limits, setLimits] = useState<AiUsageLimit[]>([]);

  const load = () => {
    if(!canAdmin)return;
    Promise.all([aiAgentsApi.getUsageSummary(), aiAgentsApi.getUsageLimits()])
      .then(([summaryResponse, limitsResponse]) => {
        setSummary(summaryResponse.data);
        setLimits(limitsResponse.data);
      })
      .catch((err) => toast({ title: "AI usage data unavailable", description: err?.response?.data?.detail, variant: "destructive" }));
  };
  useEffect(load, [canAdmin]);

  const add = () => setLimits((items) => [...items, { limit_type: "per_user", max_requests: 30, period: "hourly", is_active: true }]);
  const update = (index: number, patch: Partial<AiUsageLimit>) => setLimits((items) => items.map((item, current) => current === index ? { ...item, ...patch } : item));
  const save = async () => {if(saving)return;setSaving(true);try{await aiAgentsApi.updateUsageLimits(limits);const response=await aiAgentsApi.getUsageLimits();setLimits(response.data);toast({title:"AI usage limits saved"});}catch(error){const detail=(error as {response?:{data?:{detail?:unknown}}}).response?.data?.detail;toast({title:"Could not save usage limits",description:typeof detail==="string"?detail:"Your entries are kept for retry.",variant:"destructive"});}finally{setSaving(false);}};

  if(!canAdmin)return <AiAdministrativeNotice/>;
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div><h1 className="text-2xl font-semibold">AI Usage</h1><p className="text-sm text-muted-foreground">Usage counters, token tracking, and active request limits.</p></div>
        <div className="flex gap-2"><Button variant="outline" onClick={add} disabled={saving}>Add limit</Button><Button onClick={save} disabled={saving}>Save limits</Button></div>
      </div>
      <Card>
        <CardHeader><CardTitle>Last 30 Days</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          {(summary.events || []).map((event: any) => <div key={event.event_type} className="rounded-md border p-3"><p className="text-xs text-muted-foreground">{event.event_type}</p><p className="mt-1 text-xl font-semibold">{event.count}</p><p className="text-xs text-muted-foreground">{event.token_input} in / {event.token_output} out</p></div>)}
          {!(summary.events || []).length ? <p className="text-sm text-muted-foreground">No usage events recorded yet.</p> : null}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Limits</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {limits.map((limit, index) => (
            <div key={limit.id || index} className="grid gap-3 rounded-md border p-3 md:grid-cols-6">
              <NativeSelect className="rounded-md border bg-background px-3 py-2 text-sm" value={limit.limit_type} onChange={(event) => update(index, { limit_type: event.target.value as AiUsageLimit["limit_type"] })}>
                <option value="per_user">Per user</option><option value="per_agent">Per agent</option><option value="per_company">Per company</option><option value="per_module">Per module</option>
              </NativeSelect>
              <Input aria-label={`Maximum requests ${index+1}`} type="number" min="1" value={limit.max_requests} onChange={(event) => update(index, { max_requests: Number(event.target.value) })} />
              <NativeSelect className="rounded-md border bg-background px-3 py-2 text-sm" value={limit.period} onChange={(event) => update(index, { period: event.target.value as AiUsageLimit["period"] })}>
                <option value="hourly">Hourly</option><option value="daily">Daily</option><option value="monthly">Monthly</option>
              </NativeSelect>
              <Input placeholder="Module" value={limit.module || ""} onChange={(event) => update(index, { module: event.target.value as any || null })} />
              <Input placeholder="Agent ID" value={limit.agent_id || ""} onChange={(event) => update(index, { agent_id: event.target.value ? Number(event.target.value) : null })} />
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={limit.is_active} onChange={(event) => update(index, { is_active: event.target.checked })} /> Active</label>
            </div>
          ))}
          {!limits.length ? <p className="text-sm text-muted-foreground">No usage limits configured.</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}

import GridTable from "@/shared/data-grid/GridTable";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import { recordPreviewProps } from "@/components/RecordQuickPreview";
import { FormEvent, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { type OperatorProviderName, type OperatorProvider, type OperatorAnalytics } from "@/services/aiOperatorApi";

const labels = { openai: "OpenAI / ChatGPT", gemini: "Google Gemini", claude: "Anthropic Claude" };
const saveProvider=(provider:OperatorProviderName,data:unknown,workspace?:number)=>api.put(`/ai-operator/suite/providers/${provider}`,data,{params:{workspace_id:workspace}});
const names: OperatorProviderName[] = ["openai", "gemini", "claude"];
const message = (e: any) => typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "The request failed. Check your permissions and settings.";

export default function OperatorProviderSettings() {
  const { provider: routeProvider } = useParams();
  const [params] = useSearchParams();
  const provider = names.includes(routeProvider as OperatorProviderName) ? routeProvider as OperatorProviderName : "openai";
  const [workspaces, setWorkspaces] = useState<{ id: number; name: string }[]>([]);
  const [workspace, setWorkspace] = useState<number | undefined>(Number(params.get("workspace")) || undefined);
  const [rows, setRows] = useState<OperatorProvider[]>([]);
  const [analytics, setAnalytics] = useState<OperatorAnalytics | null>(null);
  const [model, setModel] = useState("");
  const [key, setKey] = useState("");
  const [enabled, setEnabled] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [inherit, setInherit] = useState(false);
  const [imageEnabled,setImageEnabled]=useState(false);
  const [imageModel,setImageModel]=useState('gemini-3.1-flash-image');
  const [transcriptionEnabled,setTranscriptionEnabled]=useState(false);
  const [maxTokens, setMaxTokens] = useState(3000);
  const [inputPrice, setInputPrice] = useState("");
  const [outputPrice, setOutputPrice] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const saved = rows.find(r => r.provider === provider);
  useEffect(() => { api.get<{ id: number; name: string }[]>("/project-management/workspaces").then(r => setWorkspaces(r.data)).catch(() => setWorkspaces([])); }, []);
  async function load() {
    const [settings, stats] = await Promise.all([api.get<{items:OperatorProvider[]}>('/ai-operator/suite/providers',{params:{workspace_id:workspace}}), api.get<OperatorAnalytics>('/ai-operator/suite/analytics',{params:{workspace_id:workspace}}).catch(()=>null)]);
    setRows(settings.data.items); setAnalytics(stats?.data||null);
  }
  useEffect(() => {
    let active = true; setLoading(true); setError(""); setRows([]); setAnalytics(null);
    Promise.all([api.get<{items:OperatorProvider[]}>('/ai-operator/suite/providers',{params:{workspace_id:workspace}}), api.get<OperatorAnalytics>('/ai-operator/suite/analytics',{params:{workspace_id:workspace}}).catch(()=>null)]).then(([s, a]) => {
      if (active) { setRows(s.data.items); setAnalytics(a?.data||null); }
    }).catch(e => { if (active) setError(message(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [workspace]);
  useEffect(() => {
    setModel(saved?.model || ""); setKey(""); setEnabled(saved?.enabled || false); setSharing(saved?.data_sharing_allowed || false);
    setInherit(saved?.allow_workspace_inheritance || false);
    setImageEnabled(saved?.media?.image_enabled||false);setImageModel(saved?.media?.image_model||'gemini-3.1-flash-image');
    setTranscriptionEnabled(saved?.media?.transcription_enabled||false);
    setMaxTokens(saved?.max_tokens || 3000); setInputPrice(saved?.input_price == null ? "" : String(saved.input_price));
    setOutputPrice(saved?.output_price == null ? "" : String(saved.output_price));
  }, [saved, provider]);
  useEffect(() => { setNotice(""); }, [provider, workspace]);
  async function save(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      await saveProvider(provider, { model, enabled, data_sharing_allowed: sharing, max_tokens: maxTokens,
        input_price: inputPrice === "" ? null : Number(inputPrice), output_price: outputPrice === "" ? null : Number(outputPrice), allow_workspace_inheritance: !workspace && inherit,
        ...(provider==='gemini'?{media:{image_enabled:imageEnabled,image_model:imageModel,transcription_enabled:transcriptionEnabled,transcription_model:'gemini-3.5-flash-lite'}}:{}),
        ...(key ? { api_key: key } : {}) }, workspace);
      setKey(""); await load(); setNotice("Provider settings saved. Run a connection test to verify the key and model.");
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  async function test() {
    setBusy(true); setError(""); setNotice("");
    try { await api.post(`/ai-operator/suite/providers/${provider}/test`,{}, {params:{workspace_id:workspace},timeout:60000}); await load(); setNotice("Connection verified using the saved model and key."); }
    catch (e) { setError(message(e)); try { await load(); } catch { /* Retain connection error. */ } }
    finally { setBusy(false); }
  }
  return <div className="space-y-6 max-w-6xl">
    <header><h1 className="page-title">AI provider settings</h1><p className="page-description">Configure Business Suite intelligence. Admin access is required. Keys are encrypted on the server and never returned.</p><Button asChild variant="outline"><Link className="text-primary underline" to="/pms/operator">Open AI operator</Link></Button></header>
    <label className="block">Configuration scope<NativeSelect aria-label="Provider configuration scope" className="ml-3 rounded border bg-background p-2" disabled={busy} value={workspace || ""} onChange={e => setWorkspace(e.target.value ? Number(e.target.value) : undefined)}><option value="">Company / personal legacy projects</option>{workspaces.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}</NativeSelect></label>
    <p className="text-sm text-muted-foreground">Workspace projects use their workspace configuration. Company settings apply to legacy projects; accounts without a company use private settings.</p>
    <nav className="flex gap-4">{names.map(n => <Link key={n} aria-current={provider === n ? "page" : undefined} className={provider === n ? "font-semibold underline" : "text-primary"} to={`/ai-agents/providers/${n}${workspace ? `?workspace=${workspace}` : ""}`}>{labels[n]}</Link>)}</nav>
    {error && <p role="alert" className="text-destructive">{error}</p>}{notice && <p role="status">{notice}</p>}
    {loading ? <p>Loading provider settings…</p> : <CompactForm compactTabs={false} onSubmit={save} className="rounded-lg border p-5 space-y-4 max-w-2xl"><h2 className="text-lg font-semibold">{labels[provider]}</h2><fieldset disabled={busy} className="space-y-4">
      {saved?.inherited && <p role="status">Using inherited Gemini configuration. Enter a workspace API key to create an override. A disabled override blocks inheritance.</p>}
      <label className="block">Model ID<Input aria-label="Model ID" required maxLength={120} value={model} onChange={e => setModel(e.target.value)} placeholder="Enter a model available to your API account" /></label>
      <label className="block">API key<Input aria-label="Provider API key" type="password" autoComplete="new-password" value={key} onChange={e => setKey(e.target.value)} required={!saved?.has_key || !!saved?.inherited} placeholder={saved?.inherited ? "Enter a workspace key to override inheritance" : saved?.has_key ? "Key configured; leave blank to keep it" : "Enter API key"} /></label>
      <label className="block"><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} /> Enable this provider</label>
      <label className="block"><input type="checkbox" checked={sharing} onChange={e => setSharing(e.target.checked)} /> Allow authorized task context to be sent to this provider</label>
      {provider==='gemini'&&!workspace&&<label className="block"><input type="checkbox" checked={inherit} onChange={e=>setInherit(e.target.checked)}/> Allow owned/company workspaces to inherit Gemini settings</label>}
      {provider==='gemini'&&<section aria-label="Gemini media capabilities" className="rounded border p-3 space-y-3">
        <h3 className="font-semibold">Media capabilities</h3>
        <p className="text-sm text-muted-foreground">Separate from the text model. Each media request requires its own review; saving does not generate images, transcribe files or send uploads. Provider access and data sharing must also be enabled. Media costs remain unknown until separate pricing is configured.</p>
        <label className="block"><input aria-label="Enable Gemini image processing" type="checkbox" checked={imageEnabled} onChange={e=>setImageEnabled(e.target.checked)}/> Allow reviewed image creation and editing</label>
        <label className="block">Image model<NativeSelect aria-label="Gemini image model" value={imageModel} onChange={e=>setImageModel(e.target.value)}>{['gemini-3.1-flash-image','gemini-3.1-flash-lite-image','gemini-3-pro-image'].map(value=><option key={value} value={value}>{value}</option>)}</NativeSelect></label>
        <label className="block"><input aria-label="Enable Gemini transcription" type="checkbox" checked={transcriptionEnabled} onChange={e=>setTranscriptionEnabled(e.target.checked)}/> Allow reviewed audio transcription</label>
        <p className="text-sm">Transcription model: gemini-3.5-flash-lite. Availability depends on this API account. Text connection tests do not verify media capabilities.</p>
      </section>}
      <label className="block">Maximum output tokens<Input type="number" min={512} max={8192} value={maxTokens} onChange={e => setMaxTokens(Number(e.target.value))} /></label>
      <p className="text-sm">Optional USD rates per million tokens. Use your provider contract; unknown costs stay blank in analytics.</p>
      <div className="grid grid-cols-2 gap-4"><label>Input rate<Input aria-label="Input token rate" type="number" min={0} max={10000} step="any" value={inputPrice} onChange={e => setInputPrice(e.target.value)} /></label><label>Output rate<Input aria-label="Output token rate" type="number" min={0} max={10000} step="any" value={outputPrice} onChange={e => setOutputPrice(e.target.value)} /></label></div>
      <div className="flex gap-3"><Button type="submit">{busy ? "Working…" : "Save settings"}</Button><Button type="button" variant="outline" disabled={!saved?.has_key || !saved.data_sharing_allowed} onClick={() => void test()}>Test saved connection</Button></div>
    </fieldset></CompactForm>}
    {analytics && <section className="space-y-3"><h2 className="text-xl font-semibold">API usage · last 30 days</h2><p className="text-sm">Server plans: {analytics.server_plans ?? analytics.local_plans ?? "Unavailable"} · no LLM planning calls. Counts include previews, whether approved or cancelled.</p><p className="text-sm text-muted-foreground">{analytics.cost_note}</p>{analytics.visibility&&<p className="text-sm text-muted-foreground">Visibility: {analytics.visibility.record_scope}. {analytics.visibility.note}</p>}
      <div className="overflow-auto"><GridTable gridId="pages/ai-agents/OperatorProviderSettings:table-1" className="w-full text-sm"><thead><tr>{["Provider / model", "Status", "Requests", "Input tokens", "Output tokens", "Avg latency", "Estimated USD"].map(h => <th className="p-2 text-left" key={h}>{h}</th>)}</tr></thead><tbody>{analytics.groups.map((g, i) => <tr {...recordPreviewProps(g)} className="border-t" key={i}><td className="p-2">{g.provider} / {g.model}</td><td>{g.status}</td><td>{g.requests}</td><td>{g.input_tokens ?? "Unknown"}</td><td>{g.output_tokens ?? "Unknown"}</td><td>{Math.round(g.average_latency_ms)} ms</td><td>{g.estimated_cost == null ? "Unknown" : `${Number(g.estimated_cost).toFixed(6)} (${g.priced_requests}/${g.requests} priced)`}</td></tr>)}</tbody></GridTable></div>
      <h3 className="font-semibold">Latest API requests · up to 200</h3><div className="overflow-auto"><GridTable gridId="pages/ai-agents/OperatorProviderSettings:table-2" className="w-full text-sm"><thead><tr>{["Time", "Provider / model", "Purpose", "User / run", "Status", "Latency", "Error"].map(h => <th className="p-2 text-left" key={h}>{h}</th>)}</tr></thead><tbody>{analytics.logs.map(l => <tr {...recordPreviewProps(l)} className="border-t" key={l.id}><td className="p-2">{new Date(l.created_at).toLocaleString()}</td><td>{l.provider} / {l.model}</td><td>{l.purpose}</td><td>{l.user_id} / {l.run_id ?? "test"}</td><td>{l.status}</td><td>{l.duration_ms} ms</td><td>{l.error_code || "—"}</td></tr>)}</tbody></GridTable></div>
    </section>}
  </div>;
}

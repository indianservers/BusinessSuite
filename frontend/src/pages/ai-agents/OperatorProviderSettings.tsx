import { FormEvent, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { operatorApi, type OperatorProviderName, type OperatorProvider, type OperatorAnalytics } from "@/services/aiOperatorApi";

const labels = { openai: "OpenAI / ChatGPT", gemini: "Google Gemini", claude: "Anthropic Claude" };
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
    const [settings, stats] = await Promise.all([operatorApi.providers(workspace), operatorApi.analytics(workspace)]);
    setRows(settings.data.items); setAnalytics(stats.data);
  }
  useEffect(() => {
    let active = true; setLoading(true); setError(""); setRows([]); setAnalytics(null);
    Promise.all([operatorApi.providers(workspace), operatorApi.analytics(workspace)]).then(([s, a]) => {
      if (active) { setRows(s.data.items); setAnalytics(a.data); }
    }).catch(e => { if (active) setError(message(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [workspace]);
  useEffect(() => {
    setModel(saved?.model || ""); setKey(""); setEnabled(saved?.enabled || false); setSharing(saved?.data_sharing_allowed || false);
    setMaxTokens(saved?.max_tokens || 3000); setInputPrice(saved?.input_price == null ? "" : String(saved.input_price));
    setOutputPrice(saved?.output_price == null ? "" : String(saved.output_price));
  }, [saved, provider]);
  useEffect(() => { setNotice(""); }, [provider, workspace]);
  async function save(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      await operatorApi.saveProvider(provider, { model, enabled, data_sharing_allowed: sharing, max_tokens: maxTokens,
        input_price: inputPrice === "" ? null : Number(inputPrice), output_price: outputPrice === "" ? null : Number(outputPrice),
        ...(key ? { api_key: key } : {}) }, workspace);
      setKey(""); await load(); setNotice("Provider settings saved. Run a connection test to verify the key and model.");
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  async function test() {
    setBusy(true); setError(""); setNotice("");
    try { await operatorApi.testProvider(provider, workspace); await load(); setNotice("Connection verified using the saved model and key."); }
    catch (e) { setError(message(e)); try { await load(); } catch { /* Retain connection error. */ } }
    finally { setBusy(false); }
  }
  return <div className="space-y-6 max-w-6xl">
    <header><h1 className="page-title">AI provider settings</h1><p className="page-description">Configure the PMS operator. Admin access is required. Keys are encrypted on the server and never returned.</p><Link className="text-primary underline" to="/pms/operator">Open AI operator</Link></header>
    <label className="block">Configuration scope<select aria-label="Provider configuration scope" className="ml-3 rounded border bg-background p-2" disabled={busy} value={workspace || ""} onChange={e => setWorkspace(e.target.value ? Number(e.target.value) : undefined)}><option value="">Company / personal legacy projects</option>{workspaces.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}</select></label>
    <p className="text-sm text-muted-foreground">Workspace projects use their workspace configuration. Company settings apply to legacy projects; accounts without a company use private settings.</p>
    <nav className="flex gap-4">{names.map(n => <Link key={n} aria-current={provider === n ? "page" : undefined} className={provider === n ? "font-semibold underline" : "text-primary"} to={`/pms/settings/ai/${n}${workspace ? `?workspace=${workspace}` : ""}`}>{labels[n]}</Link>)}</nav>
    {error && <p role="alert" className="text-destructive">{error}</p>}{notice && <p role="status">{notice}</p>}
    {loading ? <p>Loading provider settings…</p> : <form onSubmit={save} className="rounded-lg border p-5 space-y-4 max-w-2xl"><h2 className="text-lg font-semibold">{labels[provider]}</h2><fieldset disabled={busy} className="space-y-4">
      <label className="block">Model ID<Input aria-label="Model ID" required maxLength={120} value={model} onChange={e => setModel(e.target.value)} placeholder="Enter a model available to your API account" /></label>
      <label className="block">API key<Input aria-label="Provider API key" type="password" autoComplete="new-password" value={key} onChange={e => setKey(e.target.value)} required={!saved?.has_key} placeholder={saved?.has_key ? "Key configured; leave blank to keep it" : "Enter API key"} /></label>
      <label className="block"><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} /> Enable this provider</label>
      <label className="block"><input type="checkbox" checked={sharing} onChange={e => setSharing(e.target.checked)} /> Allow authorized task context to be sent to this provider</label>
      <label className="block">Maximum output tokens<Input type="number" min={512} max={8192} value={maxTokens} onChange={e => setMaxTokens(Number(e.target.value))} /></label>
      <p className="text-sm">Optional USD rates per million tokens. Use your provider contract; unknown costs stay blank in analytics.</p>
      <div className="grid grid-cols-2 gap-4"><label>Input rate<Input aria-label="Input token rate" type="number" min={0} max={10000} step="any" value={inputPrice} onChange={e => setInputPrice(e.target.value)} /></label><label>Output rate<Input aria-label="Output token rate" type="number" min={0} max={10000} step="any" value={outputPrice} onChange={e => setOutputPrice(e.target.value)} /></label></div>
      <div className="flex gap-3"><Button type="submit">{busy ? "Working…" : "Save settings"}</Button><Button type="button" variant="outline" disabled={!saved?.has_key || !saved.data_sharing_allowed} onClick={() => void test()}>Test saved connection</Button></div>
    </fieldset></form>}
    {analytics && <section className="space-y-3"><h2 className="text-xl font-semibold">API usage · last 30 days</h2><p className="text-sm">Local plans: {analytics.local_plans ?? 0} · no LLM planning calls. Counts include previews, whether approved or cancelled.</p><p className="text-sm text-muted-foreground">{analytics.cost_note}</p>
      <div className="overflow-auto"><table className="w-full text-sm"><thead><tr>{["Provider / model", "Status", "Requests", "Input tokens", "Output tokens", "Avg latency", "Estimated USD"].map(h => <th className="p-2 text-left" key={h}>{h}</th>)}</tr></thead><tbody>{analytics.groups.map((g, i) => <tr className="border-t" key={i}><td className="p-2">{g.provider} / {g.model}</td><td>{g.status}</td><td>{g.requests}</td><td>{g.input_tokens ?? "Unknown"}</td><td>{g.output_tokens ?? "Unknown"}</td><td>{Math.round(g.average_latency_ms)} ms</td><td>{g.estimated_cost == null ? "Unknown" : `${Number(g.estimated_cost).toFixed(6)} (${g.priced_requests}/${g.requests} priced)`}</td></tr>)}</tbody></table></div>
      <h3 className="font-semibold">Latest API requests · up to 200</h3><div className="overflow-auto"><table className="w-full text-sm"><thead><tr>{["Time", "Provider / model", "Purpose", "User / run", "Status", "Latency", "Error"].map(h => <th className="p-2 text-left" key={h}>{h}</th>)}</tr></thead><tbody>{analytics.logs.map(l => <tr className="border-t" key={l.id}><td className="p-2">{new Date(l.created_at).toLocaleString()}</td><td>{l.provider} / {l.model}</td><td>{l.purpose}</td><td>{l.user_id} / {l.run_id ?? "test"}</td><td>{l.status}</td><td>{l.duration_ms} ms</td><td>{l.error_code || "—"}</td></tr>)}</tbody></table></div>
    </section>}
  </div>;
}

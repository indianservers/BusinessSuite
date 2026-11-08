import GridTable from "@/shared/data-grid/GridTable";
import AdminVerification, { administratorStepUp } from "@/features/access/AdminVerification";
import { useEffect, useState } from 'react';
import { useAuthStore } from '@/store/authStore';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { NativeSelect } from '@/components/ui/native-select';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';

type Asset = { kind: string; key: string; id: number };
export type InstalledPack = { pack_key: string; status: string; version: number; assets: Asset[]; run_as_user_id: number; modules: string[] };
type Pack = { key: string; name: string; version: number; requiredModules: string[]; recommendedModules: string[]; automations: string[]; reports: string[] };
const moduleNames: Record<string, string> = { crm: 'CRM', srm: 'Sales & inventory', fam: 'Finance & accounting', hrms: 'People & payroll', project_management: 'Project delivery' };
const errorMessage = (error: unknown) => { const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail; return typeof detail === 'string' ? detail : typeof detail === 'object' && detail && 'message' in detail ? String(detail.message) : 'The operation could not be completed. Check your permissions and pack configuration.'; };

export default function IndustryPackOnboarding({ packKey, open, close, onInstalled }: { packKey: string; open: boolean; close: () => void; onInstalled: (pack: InstalledPack) => void }) {
  const user = useAuthStore(s => s.user);
  const companyKey = user?.access?.companyId;
  const catalog = useQuery({ queryKey: ['industry-pack-catalog'], enabled: open, queryFn: () => api.get<{ items: Pack[] }>('/industry-packs/catalog').then(r => r.data.items) });
  const installed = useQuery({ queryKey: ['industry-packs-installed', companyKey, user?.id], enabled: open, queryFn: () => api.get<{ items: InstalledPack[] }>('/industry-packs/installed', { recordCache: false }).then(r => r.data.items) });
  const identities = useQuery({ queryKey: ['industry-pack-identities', companyKey, user?.id], enabled: open, retry: false, queryFn: () => api.get<{ items: { id: number; name: string }[] }>('/industry-packs/execution-identities', { recordCache: false }).then(r => r.data.items) });
  const pack = catalog.data?.find(p => p.key === packKey), current = installed.data?.find(p => p.pack_key === packKey);
  const [verification, setVerification] = useState('');
  async function verifiedHeaders() { const response = await administratorStepUp(verification); setVerification(''); return { headers: { 'X-Access-Step-Up': response.data.token } }; }
  const [who, setWho] = useState(''), [modules, setModules] = useState<string[]>(['crm']), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [result, setResult] = useState<InstalledPack | null>(null), [notice, setNotice] = useState('');
  const [report, setReport] = useState<{ fields: string[]; items: Record<string, unknown>[]; total: number } | null>(null);
  useEffect(() => { setResult(null); setReport(null); setNotice(''); setError(''); setWho(''); setModules(['crm']); }, [companyKey, user?.id]);
  const effective = result || current;
  async function install() {
    setBusy(true); setError(''); setNotice('');
    try {
      const payload = { run_as_user_id: Number(who || current?.run_as_user_id), modules, expected_version: current?.version };
      await api.post(`/industry-packs/${packKey}/preflight`, payload);
      const { data } = await api.post<InstalledPack>(`/industry-packs/${packKey}/install`, payload, await verifiedHeaders());
      setResult(data); onInstalled(data); await installed.refetch();
      setNotice(`Version ${data.version} enabled. Workflows, reports and private intake are ready. No sample customers or deals were added.`);
    } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  }
  return <Dialog open={open} onOpenChange={next => { if (!next && !busy) close(); }}><DialogContent className="max-w-3xl"><DialogTitle>{pack?.name || 'Industry pack'} setup</DialogTitle>
    <p className="text-sm text-muted-foreground">Install CRM stages, fields, follow-up workflows, reports, a private intake form and role presets. Specialist booking, repair, filing and dispatch engines are separate phases.</p>
    {(catalog.isError || installed.isError || identities.isError) && <p role="alert" className="text-sm text-destructive">Setup needs organization administration, CRM, automation and report-building access.</p>}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}{notice && <p role="status" className="text-sm">{notice}</p>}
    {pack && <><div className="grid gap-5 sm:grid-cols-2"><section><h3 className="font-medium">Workflows that will run</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{pack.automations.map(name => <li key={name}>{name}</li>)}</ul><p className="mt-2 text-xs text-muted-foreground">Tasks use the selected CRM identity. Reminders are in-app; no SMS or email is sent.</p></section><section><h3 className="font-medium">Reports using your data</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{pack.reports.map(name => <li key={name}>{name}</li>)}</ul></section></div>
      <label className="block space-y-1 text-sm">Workflow execution identity<NativeSelect aria-label="Workflow execution identity" value={who || String(current?.run_as_user_id || '')} disabled={busy || !!current} onChange={e => setWho(e.target.value)}><option value="">Choose a managed CRM identity</option>{identities.data?.map(person => <option key={person.id} value={person.id}>{person.name}</option>)}</NativeSelect></label>
      {identities.data?.length === 0 && <p className="text-sm text-muted-foreground">Configure an active managed user with CRM viewing and task-creation access in Access Management. Global administrators cannot be workflow identities.</p>}
      <fieldset disabled={busy || !!current} className="space-y-2"><legend className="text-sm font-medium">Modules for this setup</legend>{[...pack.requiredModules, ...pack.recommendedModules].map(key => <label key={key} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={modules.includes(key)} disabled={pack.requiredModules.includes(key)} onChange={e => setModules(old => e.target.checked ? [...old, key] : old.filter(x => x !== key))} />{key === 'crm' ? 'CRM (required)' : moduleNames[key] || key}</label>)}</fieldset>
      <p className="text-xs text-muted-foreground">Role presets are created without assigning users or widening access. The intake form stays private. Installation does not remove other enabled modules.</p>
      <AdminVerification value={verification} onChange={setVerification} />
      <div className="flex flex-wrap gap-2"><Button disabled={busy || !identities.data?.length || !(who || current?.run_as_user_id)} onClick={() => void install()}>{busy ? 'Applying setup…' : current?.status === 'Enabled' ? 'Check / upgrade pack' : current ? 'Enable pack' : 'Install industry pack'}</Button>
        {effective && <><Button variant="outline" disabled={busy || effective.status === 'Disabled'} onClick={async () => { setBusy(true); setError(''); try { const { data } = await api.post<InstalledPack>(`/industry-packs/${packKey}/disable`, {}, await verifiedHeaders()); setResult(data); await installed.refetch(); setNotice('Pack disabled. Business records were preserved.'); } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); } }}>Disable pack</Button>
          <Button variant="outline" disabled={busy || effective.status !== 'Enabled'} onClick={async () => { setBusy(true); setError(''); try { const { data } = await api.post<{ ids: number[]; created: boolean }>(`/industry-packs/${packKey}/sample-data`, {}, await verifiedHeaders()); setNotice(`${data.ids.length} labelled sample records ${data.created ? 'added' : 'already exist'}. They do not trigger staff workflows.`); } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); } }}>Add optional sample records</Button></>}
      </div>
      {effective && <section className="space-y-3"><h3 className="font-medium">Installed reports</h3><div className="flex flex-wrap gap-2">{effective.assets.filter(a => a.kind === 'report').map(asset => <Button key={asset.id} size="sm" variant="outline" disabled={busy || effective.status !== 'Enabled'} onClick={async () => { setBusy(true); setError(''); try { const { data } = await api.post(`/analytics/reports/${asset.id}/run`, { page: 1, page_size: 20 }); setReport(data); } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); } }}>{pack.reports[Number(asset.key)]}</Button>)}</div>
        {report && <div className="max-w-full overflow-x-auto"><p className="text-xs text-muted-foreground">{report.total} results · first 20 shown</p><GridTable gridId="apps/crm/templates/IndustryPackOnboarding:table-1" className="w-full text-left text-sm"><thead><tr>{report.fields.map(field => <th className="border-b p-2" key={field}>{field}</th>)}</tr></thead><tbody>{report.items.map((item, index) => <tr key={index}>{report.fields.map(field => <td className="border-b p-2" key={field}>{String(item[field] ?? '—')}</td>)}</tr>)}</tbody></GridTable></div>}
      </section>}
    </>}
  </DialogContent></Dialog>;
}

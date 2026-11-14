import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import { defaultsScope } from '@/lib/form-defaults';
import { businessProfileCatalog as catalog, resolveBusinessProfile, type ProfileValues, type ResolvedProfile, type TermKey, type TermPair } from '@/lib/business-profile';
import { Button } from '@/components/ui/button';
import { registerSettingsDraftGuard } from './settingsNavigationGuard';

const endpoint = '/access/settings/business-profile/configuration';
const workspaceApis: Record<string, string> = { crm: 'crm', srm: 'srm', fam: 'fam', hrms: 'hrms', pms: 'project-management' };
type Configuration = { overrides: ProfileValues; inherited: ResolvedProfile & { custom_terms: ProfileValues['terms'] }; version: number; branches: { id: number; name: string }[] };
const errorText = (error: any) => typeof error?.response?.data?.detail === 'string' ? error.response.data.detail : 'Could not save business profile. Please try again.';

export default function BusinessProfileSettings() {
  const [branch, setBranch] = useState('');
  const [module, setModule] = useState('');
  const [workspace, setWorkspace] = useState('');
  return <ProfileEditor key={`${defaultsScope()}:${branch}:${module}:${workspace}`} branch={branch} module={module} workspace={workspace} changeScope={(b, m, w) => { setBranch(b); setModule(m); setWorkspace(w); }}/>;
}

function ProfileEditor({ branch, module, workspace, changeScope }: { branch: string; module: string; workspace: string; changeScope: (branch: string, module: string, workspace: string) => void }) {
  const cache = useQueryClient();
  const [draft, setDraft] = useState<ProfileValues>({});
  const [saved, setSaved] = useState<ProfileValues>({});
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const params = { branch_id: branch ? Number(branch) : undefined, workspace_module: workspace ? module : undefined, workspace_id: workspace || undefined };
  const headers = branch ? { 'X-Suite-Branch': branch } : undefined;
  const workspaces = useQuery({ queryKey: ['business-profile-workspaces', defaultsScope(), branch, module], enabled: !!branch && !!module, retry: false, queryFn: async () => (await api.get<{ items: { id: string; name: string; status?: string }[] }>(`/${workspaceApis[module]}/workspace-directory`, { headers })).data });
  const query = useQuery({ queryKey: ['business-profile-configuration', defaultsScope(), branch, module, workspace], queryFn: () => api.get<Configuration>(endpoint, { params, headers }).then(r => r.data), refetchOnWindowFocus: false });
  useEffect(() => { if (query.data) { setDraft(query.data.overrides); setSaved(query.data.overrides); setVersion(query.data.version); } }, [query.data]);
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);
  useEffect(() => {
    const release = registerSettingsDraftGuard(() => dirty || busy);
    const unload = (event: BeforeUnloadEvent) => { if (dirty || busy) event.preventDefault(); };
    const context = (event: Event) => { if (busy || (dirty && !window.confirm('Discard unsaved business profile changes?'))) event.preventDefault(); };
    const click = (event: MouseEvent) => {
      const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>('a[href]') : null;
      if (link && link.href !== location.href && (busy || (dirty && !window.confirm('Discard unsaved business profile changes?')))) { event.preventDefault(); event.stopPropagation(); }
    };
    window.addEventListener('beforeunload', unload);
    window.addEventListener('suite:before-context-change', context);
    document.addEventListener('click', click, true);
    return () => { release(); window.removeEventListener('beforeunload', unload); window.removeEventListener('suite:before-context-change', context); document.removeEventListener('click', click, true); };
  }, [dirty, busy]);
  if (query.isPending) return <p role="status">Loading business profile…</p>;
  if (!query.data || query.isError) return <div role="alert">Could not load business profile. <Button onClick={() => void query.refetch()}>Retry</Button></div>;
  const inherited = query.data.inherited;
  const preview = resolveBusinessProfile([{ business_type: inherited.business_type, terms: inherited.custom_terms }, draft]);
  const update = (value: ProfileValues) => { setDraft(value); setMessage(''); setError(''); };
  async function save() {
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await api.put(endpoint, { version, values: draft }, { params, headers });
      setVersion(result.data.version); setSaved(draft);
      await Promise.all([cache.invalidateQueries({ queryKey: ['business-profile'] }), cache.invalidateQueries({ queryKey: ['shared-settings'] })]);
      setMessage('Business profile saved. Existing records and pipelines are unchanged.');
    } catch (error) { setError(errorText(error)); } finally { setBusy(false); }
  }
  return <section className="settings-panel grid gap-5">
    <div><h2>Business Profile & Terminology</h2><p>Choose the terms used in your business. Appointments remain shared, and pipelines are configured separately.</p></div>
    <label>Scope<select className="w-full rounded border bg-background p-2" aria-label="Business profile scope" value={branch} disabled={busy} onChange={event => { if (!dirty || window.confirm('Discard unsaved business profile changes?')) changeScope(event.target.value, '', ''); }}><option value="">Company default</option>{query.data.branches.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
    {branch && <label>Workspace application<select className="w-full rounded border bg-background p-2" aria-label="Workspace application" value={module} disabled={busy} onChange={event => { if (!dirty || window.confirm('Discard unsaved business profile changes?')) changeScope(branch, event.target.value, ''); }}><option value="">Entire branch</option>{Object.keys(workspaceApis).map(key => <option key={key} value={key}>{key.toUpperCase()}</option>)}</select></label>}
    {branch && module && <label>Workspace<select className="w-full rounded border bg-background p-2" aria-label="Business profile workspace" value={workspace} disabled={busy || workspaces.isFetching} onChange={event => { if (!dirty || window.confirm('Discard unsaved business profile changes?')) changeScope(branch, module, event.target.value); }}><option value="">Entire branch</option>{workspaces.data?.items.filter(w => w.status !== 'Archived').map(w => <option key={w.id} value={w.id}>{w.name}</option>)}</select></label>}
    {workspaces.isError && <p role="alert">Workspaces could not load for this application. <Button variant="outline" onClick={() => void workspaces.refetch()}>Retry workspaces</Button></p>}
    <label>Business type<select className="w-full rounded border bg-background p-2" aria-label="Business type" value={draft.business_type ?? ''} disabled={busy} onChange={event => { const next = { ...draft }; if (event.target.value) next.business_type = event.target.value; else delete next.business_type; update(next); }}><option value="">{workspace ? 'Inherit branch business type' : branch ? 'Inherit company business type' : 'General business (default)'}</option>{catalog.profiles.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
    <p className="text-sm text-muted-foreground">Custom labels are preserved when switching business types. Reset to the selected template to use its suggested terms. Employee labels apply to the workforce; provider labels apply to appointment staff.</p>
    <fieldset className="grid gap-4" disabled={busy}><legend>Terminology</legend>{(Object.keys(catalog.terms) as TermKey[]).map(key => <div key={key} className="grid gap-2 rounded border p-3 sm:grid-cols-3"><strong>{catalog.terms[key][1]}</strong>{[0, 1].map(index => <label key={index}>{index ? 'Plural' : 'Singular'}<input className="w-full rounded border bg-background p-2" aria-label={`${key} ${index ? 'plural' : 'singular'}`} maxLength={60} value={draft.terms?.[key]?.[index] ?? ''} placeholder={preview.terms[key][index]} onChange={event => { const pair = [...(draft.terms?.[key] ?? preview.terms[key])] as TermPair; pair[index] = event.target.value; update({ ...draft, terms: { ...draft.terms, [key]: pair } }); }}/></label>)}{draft.terms?.[key] && <Button variant="outline" onClick={() => { const terms = { ...draft.terms }; delete terms[key]; update({ ...draft, terms }); }}>Use suggested terms</Button>}</div>)}</fieldset>
    <section className="rounded border p-4" aria-label="Business terminology preview"><h3>Preview</h3><p>{preview.terms.customer[1]} · {preview.terms.provider[1]} · {preview.terms.appointment[1]}</p><p>New {preview.terms.appointment[0].toLocaleLowerCase()} → {preview.terms.customer[0]} → {preview.terms.service[0]} → {preview.terms.provider[0]} → {preview.terms.resource[0]}</p></section>
    <div className="flex flex-wrap gap-3"><Button variant="outline" disabled={busy} onClick={() => update({ ...(draft.business_type ? { business_type: draft.business_type } : {}) })}>Reset to selected template</Button>{branch && <Button variant="outline" disabled={busy} onClick={() => update({})}>Use company profile</Button>}<Button variant="outline" disabled={busy || !dirty} onClick={() => { setDraft(saved); setError(''); }}>Discard changes</Button><Button disabled={busy || !dirty || Object.values(draft.terms ?? {}).some(pair => pair?.some(label => !label.trim()))} onClick={() => void save()}>{busy ? 'Saving…' : 'Save business profile'}</Button></div>
    {message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}
  </section>;
}

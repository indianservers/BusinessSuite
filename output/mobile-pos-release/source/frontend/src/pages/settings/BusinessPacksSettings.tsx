import BusinessThemeCards from './BusinessThemeCards';
import { useRecordScope } from '@/lib/record-scope';
import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { Button } from '@/components/ui/button';
import { NativeSelect } from '@/components/ui/native-select';
import { useRecordScopeOwner } from '@/hooks/use-record-scope-owner';
import { api } from '@/services/api';
import { defaultsScope } from '@/lib/form-defaults';
import { registerSettingsDraftGuard } from './settingsNavigationGuard';
import BusinessPackAccessSettings from './BusinessPackAccessSettings';

const base = '/access/settings/business-packs';
const moduleLabels: Record<string, string> = { hrms: 'HRMS', crm: 'CRM', project_management: 'Projects', srm: 'Sales & inventory', fam: 'Finance' };
const workflowLabels: Record<string, string> = { shared_service_exists: 'Shared service available', partial_domain_exists: 'Partially implemented', planned: 'Planned' };

type Manifest = {
  key: string; label: string; version: number; required_modules: string[]; optional_modules: string[];
  roles: { key: string; label: string; capabilities: string[]; grants_company_admin: false }[];
  workflows: { key: string; label: string; state: string; shared_service: string | null }[];
  foundation_state: string; activation_ready: boolean; isolation_ready: boolean; ui_integrated: boolean; exclusions: string[];
};
type Activation = { id: number; company_id: number; pack_key: string; pack_version: number; state: string; revision: number };
type PackContext = Activation & { branch_id: number; activation_id: number };
type Configuration = {
  company_id: number; schema_ready: boolean; missing_tables: string[]; branches: { id: number; name: string }[];
  activations: Activation[]; contexts: PackContext[]; runtime_note: string;
  has_more?: { activations?: boolean; contexts?: boolean; grants?: boolean; branches?: boolean };
};
type Readiness = {
  company_id: number; pack_key: string; branch_id: number | null; schema_ready: boolean; missing_tables: string[];
  required_modules: string[]; missing_modules: string[]; ready: boolean; isolation_ready: boolean; workflows_ready: boolean; reasons: string[];
};
type DraftAction =
  | { action: 'draft_activation'; pack_key: string; expected_revision: 0; reason: string }
  | { action: 'draft_context'; activation_id: number; activation_revision: number; branch_id: number; expected_revision: 0; reason: string };
type ActivateAction =
  | { action: 'activate'; activation_id: number; expected_revision: number; reason: string }
  | { action: 'activate_context'; context_id: number; activation_revision: number; expected_revision: number; reason: string };
type SetupAction = DraftAction | ActivateAction;
type Preview = { action: string; allowed: boolean; before: Record<string, unknown> | null; after: Record<string, unknown>; readiness: Readiness; reasons: string[]; persists: false };

function errorText(error: unknown, fallback: string): string {
  if (!isAxiosError(error)) return fallback;
  const detail: unknown = error.response?.data?.detail;
  const message = typeof detail === 'string' ? detail : detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string' ? detail.message : Array.isArray(detail)
    ? detail.map(item => typeof item?.msg === 'string' ? item.msg : '').filter(Boolean).join(' · ') : fallback;
  return error.response?.status === 409 ? `${message} Reload configuration, review the latest revision, and preview again.` : message || fallback;
}

export default function BusinessPacksSettings() {
  const generation = useRecordScope();
  return <PackEditor key={`${defaultsScope()}:${generation}`} scope={defaultsScope()}/>;
}

function PackEditor({ scope }: { scope: string }) {
  const owns = useRecordScopeOwner();
  const cache = useQueryClient();
  const [packKey, setPackKey] = useState('');
  const [branch, setBranch] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState<'preview' | 'save' | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [preview, setPreview] = useState<{ request: SetupAction; result: Preview } | null>(null);
  const requestVersion = useRef(0);
  const inFlight = useRef(false);
  const catalog = useQuery({
    queryKey: ['business-packs-catalog', scope],
    queryFn: ({ signal }) => api.get<{ company_id: number; items: Manifest[] }>(base + '/catalog', { signal }).then(result => result.data),
    retry: false,
  });
  const configuration = useQuery({
    queryKey: ['business-packs-configuration', scope],
    queryFn: ({ signal }) => api.get<Configuration>(base + '/configuration', { signal }).then(result => result.data),
    retry: false, refetchOnWindowFocus: false,
  });
  const readiness = useQuery({
    queryKey: ['business-packs-readiness', scope, packKey, branch],
    queryFn: ({ signal }) => api.get<Readiness>(base + '/readiness', { signal, params: { pack_key: packKey, branch_id: branch ? Number(branch) : undefined } }).then(result => result.data),
    enabled: !!packKey && configuration.isSuccess,
    retry: false,
  });
  useEffect(() => {
    if (!packKey && catalog.data && configuration.data) {
      const current = configuration.data.activations.find(item => item.state === 'active') || configuration.data.activations[0];
      setPackKey(catalog.data.items.find(item => item.key === current?.pack_key)?.key || catalog.data.items[0]?.key || '');
    }
  }, [catalog.data, configuration.data, packKey]);
  useEffect(() => { requestVersion.current += 1; setPreview(null); }, [configuration.dataUpdatedAt]);
  const dirty = !!reason.trim() || busy !== null;
  useEffect(() => {
    const release = registerSettingsDraftGuard(() => dirty);
    const unload = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault(); };
    const context = (event: Event) => { if (busy || (dirty && !window.confirm('Discard unsaved Business Pack setup?'))) event.preventDefault(); };
    const click = (event: MouseEvent) => {
      const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>('a[href]') : null;
      if (link && link.href !== location.href && (busy || (dirty && !window.confirm('Discard unsaved Business Pack setup?')))) { event.preventDefault(); event.stopPropagation(); }
    };
    window.addEventListener('beforeunload', unload);
    window.addEventListener('suite:before-context-change', context);
    document.addEventListener('click', click, true);
    return () => { release(); window.removeEventListener('beforeunload', unload); window.removeEventListener('suite:before-context-change', context); document.removeEventListener('click', click, true); };
  }, [dirty, busy]);

  const manifest = catalog.data?.items.find(item => item.key === packKey);
  const activation = configuration.data?.activations.find(item => item.pack_key === packKey && item.pack_version === manifest?.version);
  const context = configuration.data?.contexts.find(item => item.activation_id === activation?.id && String(item.branch_id) === branch);
  const currentAction: DraftAction | null = !manifest ? null : !activation
    ? { action: 'draft_activation', pack_key: manifest.key, expected_revision: 0, reason: reason.trim() }
    : branch && !context && ['draft', 'active'].includes(activation.state)
      ? { action: 'draft_context', activation_id: activation.id, activation_revision: activation.revision, branch_id: Number(branch), expected_revision: 0, reason: reason.trim() } : null;
  const currentSignature = JSON.stringify(currentAction);
  const activationAction: ActivateAction | null = activation?.state === 'draft'
    ? { action: 'activate', activation_id: activation.id, expected_revision: activation.revision, reason: reason.trim() }
    : activation?.state === 'active' && context?.state === 'draft'
      ? { action: 'activate_context', context_id: context.id, activation_revision: activation.revision, expected_revision: context.revision, reason: reason.trim() } : null;
  const previewMatches = !!preview && JSON.stringify(preview.request) === currentSignature;
  const activationPreviewMatches = !!preview && JSON.stringify(preview.request) === JSON.stringify(activationAction);
  const canReview = reason.trim().length >= 3 && configuration.data?.schema_ready && !busy && !configuration.isFetching;
  const draftLookupComplete = !configuration.data?.has_more?.activations && (currentAction?.action !== 'draft_context' || !configuration.data?.has_more?.contexts);
  const canPreview = !!currentAction && canReview && draftLookupComplete;
  const canActivate = !!activationAction && canReview && activationPreviewMatches && preview?.result.allowed && readiness.data?.ready === true && !readiness.isError && !readiness.isFetching;

  function change() { requestVersion.current += 1; setPreview(null); setMessage(''); setError(''); }
  function changePack(next: string) {
    if (!window.dispatchEvent(new Event('suite:before-context-change', { cancelable: true }))) return;
    change(); setReason(''); setBranch(''); setPackKey(next);
  }
  async function reload() {
    if (inFlight.current) return;
    change();
    await Promise.all([configuration.refetch(), catalog.refetch(), ...(packKey ? [readiness.refetch()] : [])]);
  }
  async function preparePreview(action: SetupAction | null) {
    if (!canReview || !action || inFlight.current) return;
    if ((action.action === 'draft_activation' || action.action === 'draft_context') && !canPreview) return;
    const request = action, version = requestVersion.current;
    inFlight.current = true; setBusy('preview'); setError(''); setMessage(''); setPreview(null);
    try {
      const { data } = await api.post<Preview>(base + '/preview', request, { readOnlyPreview: true });
      if (!owns() || version !== requestVersion.current) return;
      setPreview({ request, result: data });
    } catch (error) { if (owns()) setError(errorText(error, 'Could not preview Business Pack setup. Your draft is still here.')); }
    finally { inFlight.current = false; if (owns()) setBusy(null); }
  }
  async function saveDraft() {
    if (!preview?.result.allowed || !canReview || inFlight.current) return;
    if (!previewMatches && !canActivate) return;
    const request = preview.request;
    if ((request.action === 'draft_activation' || request.action === 'draft_context') && !canPreview) return;
    let path: string, payload: Record<string, string | number>;
    if (request.action === 'draft_activation' || request.action === 'draft_context') {
      const { action, ...values } = request;
      path = action === 'draft_activation' ? '/activations' : '/contexts'; payload = values;
    } else if (request.action === 'activate') {
      path = `/activations/${request.activation_id}/activate`; payload = { expected_revision: request.expected_revision, reason: request.reason };
    } else {
      path = `/contexts/${request.context_id}/activate`; payload = { activation_revision: request.activation_revision, expected_revision: request.expected_revision, reason: request.reason };
    }
    inFlight.current = true; setBusy('save'); setError(''); setMessage('');
    try {
      await api.post(base + path, payload);
      if (!owns()) return;
      requestVersion.current += 1; setPreview(null); setReason('');
      setMessage(request.action === 'draft_activation' ? 'Draft pack saved. It is not active and grants no pack access.'
        : request.action === 'draft_context' ? 'Draft branch context saved. It is not active and grants no pack access.'
          : request.action === 'activate' ? 'Pack activated after the server readiness checks. Branch contexts require their own activation.' : 'Branch pack context activated after the server readiness checks. Staff still need their own authorized pack role.');
      await Promise.all([configuration.refetch(), cache.invalidateQueries({ queryKey: ['business-packs-readiness'] }), cache.invalidateQueries({ queryKey: ['shared-settings'] })]);
    } catch (error) { if (owns()) { setError(errorText(error, 'Could not save Business Pack setup. Your draft is still here.')); setPreview(null); } }
    finally { inFlight.current = false; if (owns()) setBusy(null); }
  }

  if (catalog.isPending || configuration.isPending) return <section className="settings-panel" role="status">Loading Business Packs and company configuration…</section>;
  if (catalog.isError || configuration.isError || !catalog.data || !configuration.data) return <section className="settings-panel" role="alert"><h2>Business Packs could not load</h2><p>{errorText(catalog.error || configuration.error, 'Could not load Business Packs for this company.')}</p><Button type="button" variant="outline" onClick={() => void reload()}>Retry configuration</Button></section>;

  return <section className="settings-panel grid gap-5">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h2>Business Packs</h2><p>Review industry workflows, approved module dependencies, and setup for this company.</p></div><Button type="button" variant="outline" disabled={!!busy || configuration.isFetching || catalog.isFetching} onClick={() => void reload()}>Reload configuration</Button></div>
    <BusinessThemeCards scope={scope} companyId={configuration.data.company_id} catalog={catalog.data.items} beforeActivate={() => { if (!window.dispatchEvent(new Event('suite:before-context-change', { cancelable: true }))) return false; change(); setReason(''); return true; }} onActivated={key => { change(); setBranch(''); if (key !== 'general') setPackKey(key); }} />
    <details className="rounded border p-4"><summary className="cursor-pointer font-medium">Configure branch access / advanced setup</summary><div className="mt-4 grid gap-5">
    <p className="text-sm text-muted-foreground">Draft setup preserves your current business profile and sales pipelines. Pack roles apply only within their own pack and do not grant company administrator access.</p>
    {(configuration.data.has_more?.activations || configuration.data.has_more?.contexts) && <p role="alert">Some saved pack configuration is outside this view. New draft creation is unavailable when its existing configuration list is incomplete.</p>}
    <label>Business Pack<NativeSelect aria-label="Business Pack" value={packKey} disabled={!!busy} onChange={event => changePack(event.target.value)} className="w-full rounded border bg-background p-2"><option value="">Choose a Business Pack</option>{catalog.data.items.map(item => <option key={item.key} value={item.key}>{item.label}</option>)}</NativeSelect></label>
    {manifest && <>
      <section className="grid gap-3 rounded border p-4" aria-label={`${manifest.label} pack details`}>
        <div><h3>{manifest.label} Pack</h3><p className="text-sm">Version {manifest.version} · {activation ? `${activation.state.replace(/_/g, ' ')} configuration · revision ${activation.revision}` : configuration.data.has_more?.activations ? 'Not present in the loaded configuration' : 'No saved configuration'}</p></div>
        <p className="text-sm"><strong>Required modules:</strong> {manifest.required_modules.map(key => moduleLabels[key] || key).join(', ')}</p>
        {!!manifest.optional_modules.length && <p className="text-sm"><strong>Optional modules:</strong> {manifest.optional_modules.map(key => moduleLabels[key] || key).join(', ')}</p>}
        <details><summary className="cursor-pointer">Workflows and current availability</summary><ul className="mt-3 grid gap-3">{manifest.workflows.map(workflow => <li key={workflow.key}><strong>{workflow.label}</strong><p className="text-sm text-muted-foreground">{workflowLabels[workflow.state] || workflow.state.replace(/_/g, ' ')}</p></li>)}</ul><p className="mt-3 text-sm">An existing shared service does not mean this pack’s complete workflow or isolation is ready.</p></details>
        <details><summary className="cursor-pointer">{manifest.label} roles and capabilities</summary><ul className="mt-3 grid gap-3">{manifest.roles.map(role => <li key={role.key}><strong>{role.label}</strong><p className="break-words text-sm text-muted-foreground">{role.capabilities.join(' · ')}</p></li>)}</ul><p className="mt-3 text-sm">These are the selected pack’s role definitions. Viewing or saving a draft does not assign them to anyone.</p></details>
        {!!manifest.exclusions.length && <div><h4>Scope boundaries</h4><ul className="list-inside list-disc text-sm">{manifest.exclusions.map(item => <li key={item}>{item}</li>)}</ul></div>}
      </section>
      <section className="grid gap-3" aria-label="Pack readiness">
        <h3>Activation readiness</h3>
        {readiness.isPending && <p role="status">Checking pack readiness…</p>}
        {readiness.isError && <div role="alert"><p>{errorText(readiness.error, 'Could not check pack readiness. Activation is unavailable until it can be verified.')}</p><Button type="button" variant="outline" disabled={!!busy} onClick={() => void readiness.refetch()}>Retry readiness</Button></div>}
        {readiness.data && <><p>{readiness.data.ready ? 'Ready for activation review.' : 'Activation is unavailable until the required setup and workflow checks pass.'}</p>{!!readiness.data.missing_modules.length && <p className="text-sm"><strong>Required modules unavailable:</strong> {readiness.data.missing_modules.map(key => moduleLabels[key] || key).join(', ')}. Approved module access must be enabled before activation.</p>}{!!readiness.data.reasons.length && <ul className="list-inside list-disc text-sm">{readiness.data.reasons.map((item, index) => <li key={`${index}:${item}`}>{item}</li>)}</ul>}</>}
        {!configuration.data.schema_ready && <p role="alert">Business Pack setup is not available for this company yet. Your existing business settings remain available.</p>}
      </section>
      <section className="grid gap-4 border-t pt-4" aria-label="Draft pack setup">
        <div><h3>Draft setup</h3><p className="text-sm text-muted-foreground">Save the company’s pack draft first, then add a branch context. Drafts do not activate workflows or grant staff access.</p></div>
        <label>Branch<NativeSelect aria-label="Pack branch" value={branch} disabled={!!busy} onChange={event => { change(); setBranch(event.target.value); }} className="w-full rounded border bg-background p-2"><option value="">Choose a branch for its draft context</option>{configuration.data.branches.map(item => <option key={item.id} value={String(item.id)}>{item.name}</option>)}</NativeSelect></label>
        {configuration.data.has_more?.branches && <p className="text-sm text-muted-foreground">The first {configuration.data.branches.length} company branches are shown. You can review a listed branch’s context here.</p>}
        {context && <p className="text-sm">Saved branch context: {context.state.replace(/_/g, ' ')} · revision {context.revision}.</p>}
        {(currentAction || activationAction) && <label>Reason<input aria-label="Business Pack setup reason" className="w-full rounded border bg-background p-2" minLength={3} maxLength={1000} value={reason} disabled={!!busy} onChange={event => { change(); setReason(event.target.value); }}/></label>}
        {currentAction ? <div className="flex flex-wrap gap-3"><Button type="button" variant="outline" disabled={!canPreview} onClick={() => void preparePreview(currentAction)}>{busy === 'preview' ? 'Checking preview…' : 'Preview draft setup'}</Button><Button type="button" disabled={!canPreview || !previewMatches || !preview?.result.allowed} onClick={() => void saveDraft()}>{busy === 'save' ? 'Saving…' : currentAction.action === 'draft_activation' ? 'Save draft pack' : 'Save draft branch context'}</Button></div> : activation && !branch ? <p className="text-sm">Choose a branch to review or add its draft context.</p> : null}
        {activationAction && <div className="grid gap-3"><p className="text-sm">Pack activation and branch activation are separate reviewed actions. Activation stays unavailable until all server readiness checks pass.</p><div className="flex flex-wrap gap-3"><Button type="button" variant="outline" disabled={!canReview} onClick={() => void preparePreview(activationAction)}>Preview activation</Button><Button type="button" disabled={!canActivate} onClick={() => void saveDraft()}>{busy === 'save' ? 'Saving…' : activationAction.action === 'activate' ? 'Activate pack' : 'Activate branch context'}</Button></div></div>}
        {(currentAction || activationAction) && <div><Button type="button" variant="outline" disabled={!!busy || (!reason && !preview)} onClick={() => { change(); setReason(''); }}>Discard draft changes</Button></div>}
        {(previewMatches || activationPreviewMatches) && preview && <section className="grid gap-2 rounded border p-3" aria-label="Business Pack setup preview"><h4>Setup preview</h4><p>{preview.result.allowed ? preview.request.action === 'draft_activation' ? `Ready to save ${manifest.label} as a company draft.` : preview.request.action === 'draft_context' ? `Ready to save the ${manifest.label} draft context for the selected branch.` : preview.request.action === 'activate' ? `Ready to activate the ${manifest.label} Pack.` : `Ready to activate the ${manifest.label} branch context.` : 'This change cannot be saved yet.'}</p><p className="text-sm">This preview has not saved any changes.</p>{!!preview.result.reasons.length && <ul className="list-inside list-disc text-sm">{preview.result.reasons.map((item, index) => <li key={`${index}:${item}`}>{item}</li>)}</ul>}</section>}
      </section>
    </>}
    <BusinessPackAccessSettings packKey={packKey}/>
    </div></details>
    {message && <p role="status">{message}</p>}
    {error && <p role="alert">{error}</p>}
  </section>;
}

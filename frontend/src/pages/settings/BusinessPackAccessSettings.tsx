import { useDeferredValue, useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { api } from '@/services/api';
import { useRecordScope } from '@/lib/record-scope';
import { useRecordScopeOwner } from '@/hooks/use-record-scope-owner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { dealError } from '@/apps/crm/deals/deal-utils';
import { registerSettingsDraftGuard } from './settingsNavigationGuard';

const base = '/access/settings/business-packs';
const field = 'h-10 w-full rounded-md border bg-background px-3 text-sm';
type Role = { key: string; label: string; capabilities: string[]; grants_company_admin: false };
type Manifest = { key: string; label: string; version: number; roles: Role[] };
type Context = { id: number; company_id: number; branch_id: number; pack_key: string; pack_version: number; state: string; revision: number };
type Grant = { id: number; context_id: number; user_id: number; role: string; active: boolean; revision: number };
type Configuration = { company_id: number; schema_ready: boolean; contexts: Context[]; grants: Grant[]; branches: { id: number; name: string }[]; has_more?: { contexts?: boolean; grants?: boolean; branches?: boolean } };
type UserOption = { id: number; name: string };
type UserOptions = { context_id: number; context_revision: number; items: UserOption[]; has_more: boolean };
type GrantInput = { context_revision: number; role: string; active: boolean; expected_revision: number; reason: string };
type GrantRequest = GrantInput & { user_id: number };
type GrantPreview = { allowed: boolean; before: Grant | null; after: Omit<Grant, 'id'> & { company_id: number; branch_id: number }; capabilities: string[]; grants_native_permissions: false };
type Kind = 'employees' | 'customers' | 'products' | 'warehouses';
type Master = { id: number; name: string; eligible: boolean; availability_id: number | null; availability_revision: number | null; active: boolean | null };
type MasterOptions = { context_id: number; context_revision: number; kind: Kind; items: Master[]; has_more: boolean };
type ShareInput = { kind: Kind; id: number; active: boolean; expected_context_revision: number; expected_revision: number; reason: string };
function failure(error: unknown) { return `${dealError(error)}${isAxiosError(error) && error.response?.status === 409 ? ' Your draft is retained. Reload, review the latest revisions and preview again.' : ''}`; }

/** Company-admin control plane. Pack roles never grant native/company-admin permissions. */
export default function BusinessPackAccessSettings({ packKey }: { packKey: string }) {
  const scope = useRecordScope();
  return <AccessEditor key={`${scope}:${packKey}`} scope={scope} packKey={packKey}/>;
}
function AccessEditor({ scope, packKey }: { scope: string; packKey: string }) {
  const catalog = useQuery({ queryKey: ['business-pack-access-catalog', scope], queryFn: ({ signal }) => api.get<{ items: Manifest[] }>(base + '/catalog', { signal }).then(response => response.data), retry: false });
  const configuration = useQuery({ queryKey: ['business-pack-access-configuration', scope], queryFn: ({ signal }) => api.get<Configuration>(base + '/configuration', { signal }).then(response => response.data), retry: false, refetchOnWindowFocus: false });
  const [contextId, setContextId] = useState('');
  const manifest = catalog.data?.items.find(item => item.key === packKey);
  const contexts = configuration.data?.contexts.filter(item => item.pack_key === packKey) || [];
  const context = contexts.find(item => String(item.id) === contextId);
  return <section className="grid gap-4 border-t pt-5" aria-label="Business Pack access and master availability">
    <div><h3>Pack access & shared masters</h3><p className="text-sm text-muted-foreground">Explicitly assign a role in one saved branch context, or make an existing native master available there. Draft contexts can be prepared without activating them.</p></div>
    {(catalog.isPending || configuration.isPending) && <p role="status">Loading saved pack access…</p>}
    {(catalog.isError || configuration.isError) && <p role="alert">{failure(catalog.error || configuration.error)} <Button type="button" variant="outline" onClick={() => { void catalog.refetch(); void configuration.refetch(); }}>Retry pack access</Button></p>}
    {configuration.data && !configuration.data.schema_ready && <p role="alert">Pack access setup is unavailable until this company's schema is ready.</p>}
    {manifest && configuration.data?.schema_ready && <>
      <label>Saved {manifest.label} context<NativeSelect aria-label="Access branch pack context" className={field} value={contextId} onChange={event => { const change = new Event('suite:before-context-change', { cancelable: true }); if (window.dispatchEvent(change)) setContextId(event.target.value); }}><option value="">Choose a saved branch context</option>{contexts.map(item => <option key={item.id} value={item.id}>{configuration.data.branches.find(branch => branch.id === item.branch_id)?.name || `Branch #${item.branch_id}`} · {item.state} · context #{item.id}</option>)}</NativeSelect></label>
      {!contexts.length && !configuration.data.has_more?.contexts && <p className="text-sm">Save a branch context above before configuring its access.</p>}
      {(configuration.data.has_more?.contexts || configuration.data.has_more?.grants) && <p role="alert">The saved context or grant list is incomplete. Access changes are unavailable until complete configuration can be verified.</p>}
      {context && <ContextAccess key={context.id} scope={scope} context={context} manifest={manifest} grants={configuration.data.grants.filter(item => item.context_id === context.id)} complete={!configuration.data.has_more?.contexts && !configuration.data.has_more?.grants} reloadConfiguration={async () => { await Promise.all([configuration.refetch(), catalog.refetch()]); }}/>}</>}
  </section>;
}

function ContextAccess({ scope, context, manifest, grants, complete, reloadConfiguration }: { scope: string; context: Context; manifest: Manifest; grants: Grant[]; complete: boolean; reloadConfiguration: () => Promise<void> }) {
  const owns = useRecordScopeOwner(), cache = useQueryClient();
  const [userSearch, setUserSearch] = useState(''), deferredUser = useDeferredValue(userSearch);
  const [user, setUser] = useState<UserOption | null>(null), [role, setRole] = useState(''), [active, setActive] = useState(true), [reason, setReason] = useState('');
  const [kind, setKind] = useState<Kind>('employees'), [masterSearch, setMasterSearch] = useState(''), deferredMaster = useDeferredValue(masterSearch);
  const [masterId, setMasterId] = useState(''), [shareActive, setShareActive] = useState(true), [shareReason, setShareReason] = useState('');
  const [preview, setPreview] = useState<{ request: GrantRequest; result: GrantPreview } | null>(null), [review, setReview] = useState<ShareInput | null>(null);
  const [busy, setBusy] = useState<'preview' | 'grant' | 'share' | null>(null), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const flight = useRef(false);
  const users = useQuery({ queryKey: ['business-pack-user-options', scope, context.id, deferredUser], queryFn: ({ signal }) => api.get<UserOptions>(`${base}/contexts/${context.id}/user-options`, { signal, params: { search: deferredUser || undefined } }).then(response => response.data), retry: false });
  const masters = useQuery({ queryKey: ['business-pack-master-options', scope, context.id, kind, deferredMaster], queryFn: ({ signal }) => api.get<MasterOptions>(`${base}/contexts/${context.id}/master-options`, { signal, params: { kind, search: deferredMaster || undefined } }).then(response => response.data), retry: false });
  const currentGrant = grants.find(item => item.user_id === user?.id), selectedRole = manifest.roles.find(item => item.key === role), master = masters.data?.items.find(item => String(item.id) === masterId);
  const request: GrantRequest | null = user && role ? { user_id: user.id, role, active, context_revision: context.revision, expected_revision: currentGrant?.revision || 0, reason: reason.trim() } : null;
  const share: ShareInput | null = master ? { kind, id: master.id, active: shareActive, expected_context_revision: context.revision, expected_revision: master.availability_revision || 0, reason: shareReason.trim() } : null;
  const contextValid = complete && context.pack_version === manifest.version && ['draft', 'active'].includes(context.state);
  const usersCurrent = users.isSuccess && users.data.context_id === context.id && users.data.context_revision === context.revision && !users.data.has_more;
  const mastersCurrent = masters.isSuccess && masters.data.context_id === context.id && masters.data.context_revision === context.revision && masters.data.kind === kind && !masters.data.has_more;
  const canPreview = contextValid && usersCurrent && !!request && !!selectedRole && reason.trim().length >= 3 && (active || !!currentGrant) && !busy && !users.isFetching;
  const previewMatches = !!preview && JSON.stringify(preview.request) === JSON.stringify(request);
  const previewAuthorized = !!preview && preview.result.allowed && preview.result.grants_native_permissions === false
    && preview.result.after.company_id === context.company_id && preview.result.after.branch_id === context.branch_id
    && preview.result.after.context_id === context.id && preview.result.after.user_id === request?.user_id
    && preview.result.after.role === role && preview.result.after.active === active
    && preview.result.after.revision === (request?.expected_revision ?? -1) + 1;
  const canReviewMaster = contextValid && mastersCurrent && !!share && share.reason.length >= 3 && !!master && !!master.active !== shareActive && (!shareActive || master.eligible === true) && !busy && !masters.isFetching;
  const reviewMatches = !!review && JSON.stringify(review) === JSON.stringify(share);
  const dirty = !!reason || !!shareReason || !!preview || !!review;
  useEffect(() => {
    const release = registerSettingsDraftGuard(() => dirty || !!busy);
    const before = (event: Event) => { if (busy || (dirty && !window.confirm('Discard unsaved pack access changes?'))) event.preventDefault(); };
    const unload = (event: BeforeUnloadEvent) => { if (dirty || busy) event.preventDefault(); };
    window.addEventListener('suite:before-context-change', before); window.addEventListener('beforeunload', unload);
    return () => { release(); window.removeEventListener('suite:before-context-change', before); window.removeEventListener('beforeunload', unload); };
  }, [dirty, busy]);
  function changed() { setPreview(null); setReview(null); setNotice(''); setError(''); }
  async function reload() { changed(); await Promise.all([reloadConfiguration(), users.refetch(), masters.refetch()]); }
  function chooseUser(next: UserOption) { changed(); setUser(next); const saved = grants.find(item => item.user_id === next.id); setRole(saved?.role || ''); setActive(saved?.active ?? true); }
  async function previewGrant() {
    if (!canPreview || !request || flight.current || !owns()) return;
    flight.current = true; setBusy('preview'); setError('');
    try { const result = await api.post<GrantPreview>(`${base}/contexts/${context.id}/grant-preview`, request, { readOnlyPreview: true }); if (owns()) setPreview({ request, result: result.data }); }
    catch (error) { if (owns()) { setError(failure(error)); setPreview(null); } }
    finally { flight.current = false; if (owns()) setBusy(null); }
  }
  async function saveGrant() {
    if (!canPreview || !previewMatches || !previewAuthorized || !request || flight.current || !owns()) return;
    flight.current = true; setBusy('grant'); setError('');
    const { user_id, ...payload } = preview.request;
    try {
      await api.put(`${base}/contexts/${context.id}/grants/${user_id}`, payload);
      if (!owns()) return; setPreview(null); setReason(''); setNotice(active ? 'Pack role saved for this context. Native permissions and company administrator access were not changed.' : 'Pack role revoked for this context.');
      await Promise.all([reloadConfiguration(), users.refetch(), cache.invalidateQueries({ queryKey: ['business-packs-configuration'] })]);
    } catch (error) { if (owns()) { setError(failure(error)); setPreview(null); await Promise.all([reloadConfiguration(), users.refetch()]); } }
    finally { flight.current = false; if (owns()) setBusy(null); }
  }
  async function saveMaster() {
    if (!canReviewMaster || !reviewMatches || !review || flight.current || !owns()) return;
    flight.current = true; setBusy('share'); setError('');
    try { await api.put(`${base}/contexts/${context.id}/masters`, review); if (!owns()) return; setReview(null); setShareReason(''); setNotice(review.active ? 'Native master made available in this context. Native permissions were not changed.' : 'Master availability removed from this context. The native source record was not deleted.'); await Promise.all([masters.refetch(), users.refetch(), reloadConfiguration()]); }
    catch (error) { if (owns()) { setError(failure(error)); setReview(null); await Promise.all([masters.refetch(), users.refetch(), reloadConfiguration()]); } }
    finally { flight.current = false; if (owns()) setBusy(null); }
  }
  return <div className="grid gap-5" aria-label="Selected pack context access">
    <p className="text-sm">{manifest.label} context #{context.id} · {context.state} · revision {context.revision}. {context.state === 'draft' ? 'Draft enrollment grants no operational pack access until activation.' : 'Pack access also requires the user’s existing native permissions.'}</p>
    {!contextValid && <p role="alert">This context is unavailable for editing: its configuration is incomplete, its definition changed, or its state does not allow enrollment. Reload configuration before continuing.</p>}
    <Button type="button" variant="outline" className="justify-self-start" disabled={!!busy || users.isFetching || masters.isFetching} onClick={() => void reload()}>Reload access configuration</Button>
    <section className="grid gap-3 rounded border p-4" aria-label="Pack role enrollment">
      <h4>Explicit pack role assignment</h4><p className="text-xs text-muted-foreground">A pack role cannot grant company administrator, native module, or native branch access. Those permissions must already be assigned through their own controls.</p>
      <label>Find company user<Input aria-label="Find pack user" maxLength={100} value={userSearch} disabled={!!busy} onChange={event => setUserSearch(event.target.value)}/></label>
      <label>User<NativeSelect aria-label="Pack access user" className={field} value={user?.id || ''} loading={users.isFetching} error={users.isError} disabled={!!busy} onChange={event => { const next = users.data?.items.find(item => String(item.id) === event.target.value); if (next) chooseUser(next); else { changed(); setUser(null); setRole(''); } }}><option value="">Choose a company user</option>{user && !users.data?.items.some(item => item.id === user.id) && <option value={user.id}>{user.name}</option>}{users.data?.items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</NativeSelect></label>
      {users.isError && <p role="alert">{failure(users.error)} <Button type="button" variant="outline" onClick={() => void users.refetch()}>Retry company users</Button></p>}
      {users.data?.has_more && <p role="alert">Only the first 100 matching users are loaded. Narrow the user search before previewing or saving.</p>}
      {users.isSuccess && users.data.context_revision !== context.revision && <p role="alert">Context revision changed. Reload access configuration.</p>}
      <label>{manifest.label} role<NativeSelect aria-label="Pack role" className={field} value={role} disabled={!!busy || !user} onChange={event => { changed(); setRole(event.target.value); }}><option value="">Choose a role explicitly</option>{manifest.roles.map(item => <option key={item.key} value={item.key}>{item.label}</option>)}</NativeSelect></label>
      {selectedRole && <div className="rounded border p-3"><p className="font-medium">{selectedRole.label} capabilities</p><ul className="list-inside list-disc break-words text-xs text-muted-foreground">{selectedRole.capabilities.map(capability => <li key={capability}>{capability}</li>)}</ul></div>}
      <label className="flex items-center gap-2"><input type="checkbox" checked={active} disabled={!!busy || !user} onChange={event => { changed(); setActive(event.target.checked); }}/><span>Role active in this context (uncheck to revoke)</span></label>
      <label>Assignment or revocation reason<Input aria-label="Pack role reason" minLength={3} maxLength={1000} value={reason} disabled={!!busy} onChange={event => { changed(); setReason(event.target.value); }}/></label>
      <div className="flex flex-wrap gap-2"><Button type="button" variant="outline" disabled={!canPreview} onClick={() => void previewGrant()}>Preview pack role change</Button><Button type="button" disabled={!canPreview || !previewMatches || !previewAuthorized} onClick={() => void saveGrant()}>{busy === 'grant' ? 'Saving…' : active ? 'Save pack role' : 'Save role revocation'}</Button></div>
      {previewMatches && preview && <div className="grid gap-2 rounded border p-3" aria-label="Authoritative pack role preview"><p>{previewAuthorized ? `${preview.request.active ? 'Assign' : 'Revoke'} ${selectedRole?.label || preview.request.role} for ${user?.name} in context #${context.id}.` : 'The server preview did not match this exact change. Reload and preview again.'}</p><p className="text-xs">Server preview only. No permissions have been saved.</p><p className="text-xs">Before: {preview.result.before ? `${preview.result.before.role}, ${preview.result.before.active ? 'active' : 'revoked'}, revision ${preview.result.before.revision}` : 'No grant'}. After: {preview.result.after.role}, {preview.result.after.active ? 'active' : 'revoked'}, revision {preview.result.after.revision}.</p><p className="break-words text-xs">Role definition: {preview.result.capabilities.join(' · ')}. A revoked grant confers no pack access.</p><p className="text-xs">No native permission or company administrator grant.</p></div>}
      <div><h4>Saved context grants</h4>{grants.length ? <ul className="grid gap-2">{grants.map(grant => <li key={grant.id} className="flex flex-wrap items-center justify-between gap-2 rounded border p-2 text-sm"><span>User #{grant.user_id} · {manifest.roles.find(item => item.key === grant.role)?.label || grant.role} · {grant.active ? 'active' : 'revoked'} · revision {grant.revision}</span><Button type="button" size="sm" variant="outline" disabled={!!busy} onClick={() => { chooseUser(users.data?.items.find(item => item.id === grant.user_id) || { id: grant.user_id, name: `User #${grant.user_id}` }); setActive(false); }}>Review revocation</Button></li>)}</ul> : <p className="text-sm text-muted-foreground">No grants in the loaded configuration.</p>}</div>
    </section>
    <section className="grid gap-3 rounded border p-4" aria-label="Explicit native master availability">
      <h4>Native master availability</h4><p className="text-xs text-muted-foreground">Only existing employees, customers, catalog products and warehouses from the verified company branch can be enrolled. Private operational records are not shared here.</p>
      <label>Master kind<NativeSelect aria-label="Master kind" className={field} value={kind} disabled={!!busy} onChange={event => { changed(); setKind(event.target.value as Kind); setMasterId(''); setMasterSearch(''); }}>{(['employees', 'customers', 'products', 'warehouses'] as const).map(item => <option key={item} value={item}>{item}</option>)}</NativeSelect></label>
      <label>Find native master<Input aria-label="Find native master" value={masterSearch} maxLength={100} disabled={!!busy} onChange={event => { changed(); setMasterSearch(event.target.value); setMasterId(''); }}/></label>
      <label>Native source<NativeSelect aria-label="Native master source" className={field} value={masterId} disabled={!!busy} loading={masters.isFetching} error={masters.isError} onChange={event => { changed(); setMasterId(event.target.value); const source = masters.data?.items.find(item => String(item.id) === event.target.value); setShareActive(source?.eligible === true); }}><option value="">Choose an existing source</option>{masters.data?.items.map(item => <option key={item.id} value={item.id}>{item.name} · #{item.id} · {item.active ? 'enrolled' : 'not enrolled'}{item.eligible !== true ? ' - unavailable for sharing' : ''}</option>)}</NativeSelect></label>
      {masters.isError && <p role="alert">{failure(masters.error)} <Button type="button" variant="outline" onClick={() => void masters.refetch()}>Retry native masters</Button></p>}
      {masters.data?.has_more && <p role="alert">Only the first 100 matching masters are loaded. Narrow the search before reviewing or saving.</p>}
      {masters.isSuccess && masters.data.context_revision !== context.revision && <p role="alert">Context revision changed. Reload access configuration.</p>}
      {master && <p className="text-xs">Native source #{master.id}; current availability {master.active ? 'active' : 'inactive or not configured'}; availability revision {master.availability_revision || 0}.</p>}
      {master && master.eligible !== true && <p role="status" className="text-sm">This native source is unavailable for sharing. You can only remove its existing context availability; it cannot be reactivated here.</p>}
      <label className="flex items-center gap-2"><input type="checkbox" checked={shareActive} disabled={!!busy || !master || master.eligible !== true} onChange={event => { changed(); setShareActive(event.target.checked); }}/><span>Make source available in this context (uncheck to unshare)</span></label>
      <label>Availability reason<Input aria-label="Master availability reason" minLength={3} maxLength={1000} value={shareReason} disabled={!!busy} onChange={event => { changed(); setShareReason(event.target.value); }}/></label>
      <div className="flex flex-wrap gap-2"><Button type="button" variant="outline" disabled={!canReviewMaster} onClick={() => setReview(share)}>Review availability change</Button><Button type="button" disabled={!canReviewMaster || !reviewMatches} onClick={() => void saveMaster()}>{busy === 'share' ? 'Saving…' : 'Save master availability'}</Button></div>
      {reviewMatches && review && <div className="rounded border p-3" aria-label="Unsaved master availability review"><p>{review.active ? 'Share' : 'Unshare'} {master?.name} (#{review.id}) in context #{context.id}.</p><p className="text-xs">This is an unsaved review of the selected native source. The server verifies ownership and both revisions when you save. It grants no native permissions.</p></div>}
      <details><summary className="cursor-pointer">Loaded native availability</summary><ul className="mt-2 grid gap-1 text-sm">{masters.data?.items.filter(item => item.availability_id !== null).map(item => <li key={item.id}>{item.name} · #{item.id} · {item.active ? 'available' : 'unshared'} · revision {item.availability_revision}</li>)}</ul><p className="text-xs text-muted-foreground">This list follows the current kind and search. Availability is not the native source's access policy.</p></details>
    </section>
    {(dirty || error) && <Button type="button" variant="outline" className="justify-self-start" disabled={!!busy} onClick={() => { changed(); setReason(''); setShareReason(''); setRole(currentGrant?.role || ''); setActive(currentGrant?.active ?? true); setShareActive(master?.eligible === true && !!master.active); }}>Discard unsaved access changes</Button>}
    {notice && <p role="status">{notice}</p>}{error && <p role="alert">{error}</p>}
  </div>;
}

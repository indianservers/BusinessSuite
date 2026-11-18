import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/services/api';
import { useRecordScopeOwner } from '@/hooks/use-record-scope-owner';
import { clearPackContext } from '@/lib/pack-context';
import { refreshCurrentAccess } from '@/features/access/refresh-current-access';
import { registerSettingsDraftGuard } from './settingsNavigationGuard';
import { DEFAULT_BUSINESS_PACK_LABEL } from '@/lib/business-pack-labels';

type CatalogPack = { key: string; label: string; activation_ready: boolean; isolation_ready: boolean; ui_integrated: boolean; workflows: { label: string }[]; release_status?: string };
type ThemeState = { company_id: number; active_key: string | null; selection_revision: string; multiple_active: boolean; terminology: { business_type: string; terms: Record<string, unknown> }; activation_id?: number | null };
const endpoint = '/access/settings/business-packs/theme';

function message(error: unknown) {
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail.message === 'string') return detail.message;
  }
  return error instanceof Error ? error.message : 'Business Pack could not be updated.';
}

export default function BusinessThemeCards({ scope, companyId, catalog, beforeActivate, onActivated }: {
  scope: string; companyId: number; catalog: CatalogPack[]; beforeActivate?: () => boolean; onActivated?: (key: string) => void;
}) {
  const cache = useQueryClient(), owns = useRecordScopeOwner(), pending = useRef(false);
  const [busy, setBusy] = useState<string | null>(null), [error, setError] = useState(''), [notice, setNotice] = useState(''), [conflict, setConflict] = useState(false);
  const queryKey = ['business-packs-theme', scope];
  function verified(value: ThemeState) {
    if (value.company_id !== companyId || !/^[a-f0-9]{64}$/.test(value.selection_revision) || typeof value.multiple_active !== 'boolean'
        || (value.multiple_active ? value.active_key !== null : typeof value.active_key !== 'string') || !value.terminology?.terms) throw new Error('Reload the verified company Business Pack before activating another pack.');
    return value;
  }
  const theme = useQuery({ queryKey, retry: false, refetchOnWindowFocus: false,
    queryFn: async ({ signal }) => verified((await api.get<ThemeState>(endpoint, { signal })).data) });
  useEffect(() => {
    const release = registerSettingsDraftGuard(() => busy !== null);
    const guard = (event: Event) => { if (pending.current) event.preventDefault(); };
    window.addEventListener('suite:before-context-change', guard);
    window.addEventListener('beforeunload', guard);
    return () => { release(); window.removeEventListener('suite:before-context-change', guard); window.removeEventListener('beforeunload', guard); };
  }, [busy]);
  async function activate(key: string, label: string) {
    if (!owns() || pending.current || conflict || !theme.data || theme.isError || theme.isFetching || (theme.data.active_key === key && !theme.data.multiple_active)) return;
    if (beforeActivate && !beforeActivate()) return;
    pending.current = true; setBusy(key); setError(''); setNotice('');
    try {
      const result = verified((await api.post<ThemeState>(endpoint, { pack_key: key, expected_selection: theme.data.selection_revision, reason: `Activate ${label} Business Pack` })).data);
      if (!owns()) return;
      if (result.multiple_active || result.active_key !== key) throw new Error('The activation receipt did not confirm this Business Pack. Reload the company selection.');
      // This is the verified server receipt, never an optimistic activation.
      cache.setQueryData(queryKey, result); setNotice(`${label} is active. Business terms apply automatically.`); onActivated?.(key);
      try {
        await cache.cancelQueries({ queryKey: ['suite-access'] });
        clearPackContext();
        await cache.invalidateQueries({ queryKey: ['suite-access'] });
        await refreshCurrentAccess(cache);
        await Promise.all(['business-packs-configuration', 'business-packs-readiness', 'business-profile', 'business-profile-configuration', 'shared-settings', 'business-pack-discovery'].map(key => cache.invalidateQueries({ queryKey: [key] })));
      } catch {
        if (owns()) setError('The Business Pack was activated, but current access or labels could not refresh. Reload this page before continuing.');
      }
    } catch (failure) {
      if (!owns()) return;
      setError(message(failure));
      if (isAxiosError(failure) && failure.response?.status === 409) setConflict(true);
    } finally { pending.current = false; if (owns()) setBusy(null); }
  }
  async function reload() {
    if (pending.current) return;
    const result = await theme.refetch();
    if (owns() && result.isSuccess) { setConflict(false); setError(''); setNotice(''); }
  }
  const cards = [{ key: 'general', label: DEFAULT_BUSINESS_PACK_LABEL, upcoming: false, description: 'The default Business Pack for your current business, with standard terms and shared workflows.' }, ...catalog.map(pack => ({
    key: pack.key, label: pack.label, upcoming: pack.release_status === 'upcoming', description: pack.workflows.slice(0, 2).map(item => item.label).join(' · '),
  }))];
  return <section className="grid gap-4" aria-label="Business Packs">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">Choose your Business Pack</h3><p className="text-sm text-muted-foreground">One Business Pack is active for this company. Activating a pack applies its business terms automatically.</p></div><Button variant="outline" disabled={busy !== null || theme.isFetching} onClick={() => void reload()}>Reload Business Pack</Button></div>
    {theme.isPending && <p role="status">Loading the active Business Pack…</p>}
    {theme.isError && <p role="alert">{message(theme.error)}</p>}
    {theme.data?.multiple_active && <p role="alert">Several legacy packs are active. Choose one Business Pack to resolve this selection; none is shown as the single active pack.</p>}
    {conflict && <p role="alert">The company selection changed. Reload the Business Pack and review it before activating.</p>}
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{cards.map(card => {
      const active = !!theme.data && !theme.data.multiple_active && theme.data.active_key === card.key;
      return <Card key={card.key} aria-label={`${card.label} Business Pack`}><CardHeader><div className="flex flex-wrap items-center justify-between gap-2"><CardTitle>{card.label}</CardTitle>{active ? <span className="text-sm font-medium">Active</span> : card.upcoming ? <span className="text-sm text-muted-foreground">Upcoming</span> : null}</div></CardHeader><CardContent className="grid gap-4"><p className="text-sm text-muted-foreground">{card.description}</p><Button aria-label={`${active ? 'Active' : 'Activate'} ${card.label} Business Pack`} disabled={active || card.upcoming || busy !== null || !theme.data || theme.isError || theme.isFetching || conflict} onClick={() => void activate(card.key, card.label)}>{active ? 'Active' : card.upcoming ? 'Upcoming' : busy === card.key ? 'Activating…' : 'Activate'}</Button></CardContent></Card>;
    })}</div>
  </section>;
}

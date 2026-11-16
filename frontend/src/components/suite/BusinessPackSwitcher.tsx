import { useEffect, useState } from 'react';
import { isAxiosError } from 'axios';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import * as Dialog from '@radix-ui/react-dialog';
import { accessQueryOptions } from '@/features/access/access-query';
import { useAuthStore, type AuthUser } from '@/store/authStore';
import { useRecordScope } from '@/lib/record-scope';
import { selectedPackContext } from '@/lib/pack-context';
import { switchPackContext, validPackChoice } from '@/lib/switch-pack-context';
import type { BusinessPackChoice, BusinessPackDiscovery } from '@/lib/business-pack-types';
import { NativeSelect } from '@/components/ui/native-select';
import { Button } from '@/components/ui/button';
import { dealError } from '@/apps/crm/deals/deal-utils';
import { DEFAULT_BUSINESS_PACK_LABEL } from '@/lib/business-pack-labels';

export default function BusinessPackSwitcher({ onVisibility }: { onVisibility?: (visible: boolean) => void }) {
  const scope = useRecordScope();
  return <Switcher key={scope} onVisibility={onVisibility}/>;
}
function Switcher({ onVisibility }: { onVisibility?: (visible: boolean) => void }) {
  const user = useAuthStore(state => state.user), qc = useQueryClient();
  const scope = useRecordScope();
  const [pending, setPending] = useState<BusinessPackChoice | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const query = useQuery({ queryKey: ['business-pack-discovery', scope], enabled: !!user, retry: false,
    queryFn: () => qc.fetchQuery(accessQueryOptions()).then(data => (data as NonNullable<AuthUser['access']> & {businessPacks?:BusinessPackDiscovery}).businessPacks || null) });
  const discovery = query.data;
  const general = !!discovery && selectedPackContext() === null && (discovery.state === 'ready' || discovery.reason === 'not_installed') && !discovery.selectorRequired && !discovery.contexts.length;
  const visible = general || (!!discovery && discovery.state === 'ready' && (!!discovery.contexts.length || discovery.selectorRequired));
  useEffect(() => { onVisibility?.(visible); }, [onVisibility, visible]);
  if (query.isError && selectedPackContext() !== null) return <div className="max-w-48 text-xs" role="alert">Pack choices could not be verified. <Button type="button" variant="outline" size="sm" onClick={() => void query.refetch()}>Reload pack choices</Button></div>;
  if (general) return <div className="suite-branch-field" aria-label="Business Pack selection"><span className="suite-branch-label">Business Pack</span><span aria-label="Current Business Pack">{DEFAULT_BUSINESS_PACK_LABEL}</span></div>;
  if (!discovery || discovery.state !== 'ready' || (!discovery.contexts.length && !discovery.selectorRequired)) return null;
  const complete = !discovery.hasMore && discovery.contexts.every(validPackChoice) && new Set(discovery.contexts.map(row => row.contextId)).size === discovery.contexts.length;
  return <div className="flex min-w-0 flex-wrap items-center gap-2" aria-label="Business Pack selection">
    <label className="suite-branch-field min-w-0"><span className="suite-branch-label">Business Pack</span><NativeSelect aria-label="Current Business Pack" className="suite-branch-select max-w-48" value={discovery.selectionState === 'verified' ? String(discovery.selectedContextId) : ''} disabled={!complete || busy || query.isFetching || !discovery.contexts.length} onChange={event => { const choice = discovery.contexts.find(row => String(row.contextId) === event.target.value); if (choice) setPending(choice); }}>
      <option value="">{discovery.selectorRequired ? 'Choose assigned context' : DEFAULT_BUSINESS_PACK_LABEL}</option>{discovery.contexts.filter(validPackChoice).map(row => <option key={row.contextId} value={row.contextId}>{row.packLabel} · {row.branchName} · {row.role}</option>)}
    </NativeSelect></label>
    {(!complete || error || discovery.selectionState === 'invalid' || !discovery.contexts.length) && <div className="max-w-64 text-xs"><p role="alert">{error || (!complete ? 'Context choices are incomplete. Reload before switching.' : 'Select an assigned context or ask a company administrator to review access.')}</p><Button type="button" size="sm" variant="outline" disabled={query.isFetching || busy} onClick={() => { setError(''); void query.refetch(); }}>Reload pack choices</Button></div>}
    <Dialog.Root open={!!pending} onOpenChange={open => { if (!open && !busy) setPending(null); }}><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-[100] bg-black/50"/><Dialog.Content className="fixed left-1/2 top-1/2 z-[101] w-[min(420px,95vw)] -translate-x-1/2 -translate-y-1/2 rounded-xl border bg-background p-6"><Dialog.Title className="font-semibold">Switch Business Pack?</Dialog.Title><Dialog.Description className="my-3 text-sm text-muted-foreground">Switch to {pending?.packLabel} in {pending?.branchName}? Save unfinished changes first. The page will reload after your current access is verified.</Dialog.Description><div className="flex justify-end gap-2"><Dialog.Close asChild><Button variant="outline" disabled={busy}>Stay here</Button></Dialog.Close><Button disabled={busy} onClick={async () => { if (!pending) return; setBusy(true); try { await switchPackContext(qc, pending); setPending(null); } catch (caught) { setError(isAxiosError(caught) ? dealError(caught) : caught instanceof Error ? caught.message : 'Business Pack verification failed. Reload choices.'); setPending(null); } finally { setBusy(false); } }}>Switch pack</Button></div></Dialog.Content></Dialog.Portal></Dialog.Root>
  </div>;
}

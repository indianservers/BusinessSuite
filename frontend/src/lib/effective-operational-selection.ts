import type { BusinessPackDiscovery } from './business-pack-types';
import type { AuthUser } from '@/store/authStore';

export type OperationalSelection = {
  realm: 'legacy' | 'pack'; user_id: number; company_id: number; branch_id: number;
  context_id: number | null; pack_key: string | null; pack_version: number | null;
  context_revision: number | null; grant_revision: number | null; activation_revision: number | null;
};
const positive = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) > 0;
const unavailable = () => { throw new Error('POS context verification is unavailable. Reload after the application update completes.'); };

/** Verifies a server selection against fresh discovery. This grants no permissions. */
export function effectiveOperationalSelection(value: unknown, user: AuthUser | null, branch: string | null, rawSelector: string | null): OperationalSelection {
  const data = value as Partial<OperationalSelection> | null;
  const discovery = (user?.access as unknown as { businessPacks?: BusinessPackDiscovery })?.businessPacks;
  if (!data || !positive(user?.id) || !positive(user?.access?.companyId) || !branch || !/^[1-9][0-9]*$/.test(branch)
      || data.user_id !== user.id || data.company_id !== user.access.companyId || data.branch_id !== Number(branch)
      || !discovery || !Array.isArray(discovery.contexts) || discovery.hasMore !== false || discovery.selectionState === 'invalid') return unavailable();
  const eligible = discovery.contexts.filter(choice => choice.branchId === data.branch_id);
  if (data.realm === 'legacy') {
    const uninstalled = discovery.state === 'unavailable' && discovery.reason === 'not_installed'
      && discovery.contexts.length === 0 && discovery.selectorRequired === false
      && discovery.selectedContextId === null && discovery.selectionState === 'none';
    if (discovery.state !== 'ready' && !uninstalled) return unavailable();
    if (rawSelector !== null || eligible.length || discovery.selectorRequired
        || [data.context_id, data.pack_key, data.pack_version, data.context_revision, data.grant_revision, data.activation_revision].some(item => item !== null)) return unavailable();
    return data as OperationalSelection;
  }
  if (discovery.state !== 'ready') return unavailable();
  if (data.realm !== 'pack' || !positive(data.context_id) || !positive(data.pack_version)
      || !positive(data.context_revision) || !positive(data.grant_revision) || !positive(data.activation_revision) || typeof data.pack_key !== 'string') return unavailable();
  if (rawSelector !== null && (!/^[1-9][0-9]*$/.test(rawSelector) || Number(rawSelector) !== data.context_id)) return unavailable();
  const choice = eligible.find(item => item.contextId === data.context_id);
  if (!choice || choice.packKey !== data.pack_key || choice.packVersion !== data.pack_version
      || choice.contextRevision !== data.context_revision || choice.grantRevision !== data.grant_revision || choice.activationRevision !== data.activation_revision
      || (rawSelector === null && eligible.length !== 1)
      || (rawSelector !== null && (discovery.selectionState !== 'verified' || discovery.selectedContextId !== data.context_id))) return unavailable();
  return data as OperationalSelection;
}


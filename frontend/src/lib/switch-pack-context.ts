import type { QueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import { useAuthStore, type AuthUser } from '@/store/authStore';
import { recordScope } from './record-scope';
import { clearPackContext, setPackContext } from './pack-context';
import type { BusinessPackChoice, BusinessPackDiscovery } from './business-pack-types';

const identity = ['contextId', 'branchId', 'packKey', 'packVersion', 'role', 'contextRevision', 'grantRevision', 'activationRevision'] as const;
export function validPackChoice(choice: BusinessPackChoice) {
  return choice && ['contextId', 'branchId', 'packVersion', 'contextRevision', 'grantRevision', 'activationRevision'].every(key => Number.isSafeInteger(choice[key as keyof BusinessPackChoice]) && Number(choice[key as keyof BusinessPackChoice]) > 0)
    && /^[a-z][a-z0-9_]{0,63}$/.test(choice.packKey) && /^[a-z][a-z0-9_]{0,63}$/.test(choice.role)
    && typeof choice.branchName === 'string' && !!choice.branchName.trim() && typeof choice.packLabel === 'string' && !!choice.packLabel.trim();
}

/** The server verifies the exact pair. This helper never generates permissions. */
export async function switchPackContext(qc: QueryClient, candidate: BusinessPackChoice, href = window.location.pathname + window.location.search) {
  if (!href.startsWith('/') || href.startsWith('//')) throw new Error('Reload destination must remain inside this application.');
  if (!validPackChoice(candidate)) throw new Error('Invalid Business Pack choice. Reload available contexts.');
  if (!window.dispatchEvent(new Event('suite:before-context-change', { cancelable: true }))) return false;
  const user = useAuthStore.getState().user;
  if (!user) throw new Error('Sign in before selecting a Business Pack.');
  const owner = recordScope(user), company = user.access?.companyId;
  if (!Number.isSafeInteger(company) || !company) throw new Error('A verified current company is required.');
  if (sessionStorage.getItem('suite-organization') && sessionStorage.getItem('suite-organization') !== String(company)) throw new Error('Company selection changed. Reload access before choosing a pack.');
  const { data } = await api.get<NonNullable<AuthUser['access']> & { businessPacks?: BusinessPackDiscovery }>('/access/me', {
    headers: { 'X-Suite-Organization': String(company), 'X-Suite-Branch': String(candidate.branchId), 'X-Suite-Pack-Context': String(candidate.contextId) },
  });
  const discovery = data.businessPacks;
  const choices = Array.isArray(discovery?.contexts) ? discovery.contexts : [];
  const matches = choices.filter(row => row && row.contextId === candidate.contextId);
  if (recordScope(useAuthStore.getState().user) !== owner || data.companyId !== company || discovery?.state !== 'ready' || discovery.hasMore !== false || choices.length > 100 || !choices.every(validPackChoice) || new Set(choices.map(row => row.contextId)).size !== choices.length || discovery.selectionState !== 'verified' || discovery.selectedContextId !== candidate.contextId || matches.length !== 1 || identity.some(key => matches[0][key] !== candidate[key])) {
    throw new Error('Business Pack access changed or choices are incomplete. Reload available contexts before switching.');
  }
  await qc.cancelQueries();
  if (recordScope(useAuthStore.getState().user) !== owner) throw new Error('The current workspace changed before switching.');
  // Remove old aliases before changing branch, then establish the new selector's
  // owner fingerprint in that exact branch. Company and tenant stay unchanged.
  clearPackContext();
  sessionStorage.setItem('suite-branch', String(candidate.branchId));
  setPackContext(String(candidate.contextId));
  useAuthStore.getState().setUser({ ...user, access: data });
  qc.clear();
  window.location.assign(href);
  return true;
}

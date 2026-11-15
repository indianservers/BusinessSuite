import { useAuthStore } from '@/store/authStore';
import { recordScope } from './record-scope';
import type { OperationalSelection } from './effective-operational-selection';

export type POSOperationalPin = Readonly<{ owner: string; contextId: string | null; realm: 'legacy' | 'pack' }>;
let active: POSOperationalPin | null = null;
export const operationalOwner = () => recordScope(useAuthStore.getState().user);
export const currentPOSOperationalPin = () => active;
/** In-memory request binding only. It never persists a selector or grants a role. */
export function installPOSOperationalPin(selection: OperationalSelection, owner: string) {
  if (owner !== operationalOwner() || active !== null) throw new Error('POS context changed before request binding');
  const pin: POSOperationalPin = Object.freeze({ owner, contextId: selection.realm === 'pack' ? String(selection.context_id) : null, realm: selection.realm });
  active = pin;
  return () => { if (active === pin) active = null; };
}
export function isPOSOperationalRequest(url: string | undefined) {
  return typeof url === 'string' && /^\/(?:api\/v1\/)?srm(?:\/|$)/.test(url);
}

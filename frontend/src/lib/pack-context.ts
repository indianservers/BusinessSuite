/** A selector is an opaque server-authorized identity, never a role or grant. */
export const packContextEvent = 'suite:pack-context-changed';
const canonical = 'suite-pack-context';
const alias = 'suite-business-pack-context';
const ownerKey = 'suite-pack-context-owner';
const owner = () => JSON.stringify(['suite-tenant', 'suite-organization', 'suite-branch'].map(key => sessionStorage.getItem(key)));

export function clearPackContext() {
  const changed = sessionStorage.getItem(canonical) !== null || sessionStorage.getItem(alias) !== null;
  sessionStorage.removeItem(canonical); sessionStorage.removeItem(alias); sessionStorage.removeItem(ownerKey);
  if (changed) window.dispatchEvent(new Event(packContextEvent));
}

export function selectedPackContext(): string | null {
  const previous = sessionStorage.getItem(ownerKey), current = owner();
  if (previous !== null && previous !== current) clearPackContext();
  const value = sessionStorage.getItem(canonical), legacy = sessionStorage.getItem(alias);
  if (value === null && legacy === null) return null;
  if (previous === null || previous !== current) sessionStorage.setItem(ownerKey, current);
  // Never drop malformed/conflicting selectors into a permissive legacy mode.
  if (value !== null && legacy !== null && value !== legacy) return '!conflicting-pack-context';
  const selected = value ?? legacy!;
  if (value === null) sessionStorage.setItem(canonical, selected);
  return selected;
}

export function setPackContext(value: string | null) {
  if (value === null) { clearPackContext(); return; }
  if (!/^[0-9]+$/.test(value) || !/[1-9]/.test(value)) throw new Error('Select a positive Business Pack context identity.');
  sessionStorage.setItem(canonical, value); sessionStorage.setItem(alias, value); sessionStorage.setItem(ownerKey, owner());
  window.dispatchEvent(new Event(packContextEvent));
}

// Existing switchers may write storage directly. Persisted ownership also
// detects changes across reloads, before the next request/cache/owner read.
if (typeof window !== 'undefined') {
  selectedPackContext();
  for (const event of ['suite:organization-changed', 'suite:branch-changed', 'suite:tenant-changed']) {
    window.addEventListener(event, () => { selectedPackContext(); });
  }
}

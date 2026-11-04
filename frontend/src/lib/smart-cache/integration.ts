import type { AxiosInstance } from 'axios';
import type { QueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/store/authStore';
import { shareRecordReferences } from './structural-sharing';
import { stable, splitView } from './model';
import { RecordCacheManager, type Change } from './manager';

function identity(): string | null {
  const { user, accessToken, isAuthenticated } = useAuthStore.getState();
  if (!user || !accessToken || !isAuthenticated) return null;
  let session = '';
  try { session = JSON.parse(atob(accessToken.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))).sid || ''; } catch { return null; }
  // App changes the displayed module role during navigation. The authenticated
  // primary role and live grants remain the authorization identity.
  return stable([1, user.id, session, user.primary_role ?? user.role, user.is_superuser, user.access, sessionStorage.getItem('suite-organization'), sessionStorage.getItem('suite-branch')]);
}
function replace(value: unknown, old: unknown, data: unknown): unknown {
  if (value === old) return data;
  if (!value || typeof value !== 'object') return value;
  // Axios objects contain request cycles. Their JSON body is the only cached part.
  if ('data' in value) {
    const object = value as Record<string, unknown>;
    const next = replace(object.data, old, data);
    return next === object.data ? value : { ...object, data: next };
  }
  if (stable(value) === stable(old)) return data;
  const oldView = splitView(old), nextView = splitView(data);
  if (oldView && nextView && Array.isArray(value) && stable(value) === stable(oldView.rows)) return nextView.rows;
  const object = value as Record<string, unknown>;
  let changed = false;
  const entries = Object.entries(object).map(([key, item]) => {
    if (['config', 'request', 'headers'].includes(key)) return [key, item];
    const next = item && typeof item === 'object' ? replace(item, old, data) : item;
    changed ||= next !== item;
    return [key, next];
  });
  return changed ? (Array.isArray(value) ? entries.map(([, item]) => item) : Object.fromEntries(entries)) : value;
}
export let recordCache: RecordCacheManager;
export function installRecordCache(api: AxiosInstance, client: QueryClient) {
  const defaults = client.getDefaultOptions();
  client.setDefaultOptions({ ...defaults, queries: { ...defaults.queries, structuralSharing: shareRecordReferences } });
  const provenance = new WeakMap<object, Set<string>>();
  const dependencies = new Map<string, Set<string>>();
  const used = (key: string, data: unknown) => {
    if (!data || typeof data !== 'object') return;
    const keys = provenance.get(data) || new Set<string>(); keys.add(key); provenance.set(data, keys);
    const view = splitView(data);
    if (view) provenance.set(view.rows, keys);
  };
  const keysFor = (data: unknown, seen = new WeakSet<object>(), depth = 0): Set<string> | undefined => {
    if (!data || typeof data !== 'object' || seen.has(data) || depth > 4) return;
    seen.add(data);
    const direct = provenance.get(data);
    if (direct) return direct;
    const keys = new Set<string>();
    for (const [name, value] of Object.entries(data)) if (!['config', 'request', 'headers'].includes(name)) keysFor(value, seen, depth + 1)?.forEach(key => keys.add(key));
    return keys.size ? keys : undefined;
  };
  client.getQueryCache().subscribe(event => {
    if (event.type === 'removed') dependencies.delete(event.query.queryHash);
    if (event.type === 'updated' && event.action.type === 'success') {
      const keys = keysFor(event.query.state.data);
      if (keys) dependencies.set(event.query.queryHash, new Set(keys));
    }
  });
  const changed = (change: Change) => {
    for (const query of client.getQueryCache().getAll()) if (dependencies.get(query.queryHash)?.has(change.key)) {
      client.setQueryData(query.queryKey, (data: unknown) => replace(data, change.old, change.data));
    }
    window.dispatchEvent(new CustomEvent('suite:records-updated', { detail: change }));
  };
  recordCache = new RecordCacheManager(api, {
    identity, used, changed,
    active: key => client.getQueryCache().getAll().some(q => q.isActive() && dependencies.get(q.queryHash)?.has(key)),
    revoked: (revalidate = true) => {
      // Drop already-visible unauthorized records too; components retain their local UI state.
      void client.cancelQueries().then(() => {
        if (!useAuthStore.getState().isAuthenticated) { client.clear(); return; }
        for (const query of client.getQueryCache().getAll()) {
          if (revalidate) query.reset();
          else query.setState({ data: undefined, error: new Error('Access to cached records is unavailable. Refresh after checking your permissions.'), status: 'error', fetchStatus: 'idle' });
        }
        if (revalidate) return client.refetchQueries({ type: 'active' });
      });
      window.dispatchEvent(new CustomEvent('suite:record-access-changed', { detail: { revalidate } }));
    },
  });
  useAuthStore.subscribe(() => recordCache.contextChanged());
  for (const event of ['suite:organization-changed', 'suite:branch-changed']) window.addEventListener(event, () => recordCache.contextChanged());
  window.addEventListener('suite:record-push', event => { const module = (event as CustomEvent<{ module: string }>).detail?.module; void recordCache.syncModuleChanges(module, true); });
  window.addEventListener('suite:record-mutated', event => { void recordCache.afterMutation((event as CustomEvent<string>).detail); });
  return recordCache;
}

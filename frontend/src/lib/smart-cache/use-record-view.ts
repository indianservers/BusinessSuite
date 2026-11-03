import { useAuthStore } from "@/store/authStore";
import { useEffect, useRef } from 'react';
import { api } from '@/services/api';
import type { Change } from './manager';
import { recordCache } from './integration';
import { canonicalView as canonical } from './model';

/** Subscribe legacy state-based grids without repeating their unrelated bootstrap requests. */
export function useRecordView<T>(url: string, params: Record<string, unknown>, update: (data: T) => void, clear: () => void, enabled = true) {
  const latest = useRef({ update, clear }); latest.current = { update, clear };
  const key = canonical(api.getUri({ url, params }).replace(api.defaults.baseURL || '', ''));
  useEffect(() => {
    if (!enabled) return;
    const unobserve = recordCache?.observeView(key);
    const changed = (event: Event) => { const change = (event as CustomEvent<Change>).detail; if (canonical(change.url) === key) latest.current.update(change.data as T); };
    let mounted = true;
    const revoked = (event: Event) => {
      latest.current.clear();
      if ((event as CustomEvent<{revalidate?: boolean}>).detail?.revalidate && navigator.onLine && useAuthStore.getState().isAuthenticated) {
        void api.get<T>(url, { params, recordCache: false, progress: false }).then(response => { if (mounted) latest.current.update(response.data); }).catch(() => undefined);
      }
    };
    window.addEventListener('suite:records-updated', changed);
    window.addEventListener('suite:record-access-changed', revoked);
    window.addEventListener('suite:organization-changed', revoked);
    window.addEventListener('suite:branch-changed', revoked);
    return () => { unobserve?.(); mounted = false; window.removeEventListener('suite:records-updated', changed); window.removeEventListener('suite:record-access-changed', revoked); window.removeEventListener('suite:organization-changed', revoked); window.removeEventListener('suite:branch-changed', revoked); };
  }, [key, enabled]);
}

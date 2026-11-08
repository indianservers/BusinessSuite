import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { defaultSuitePreferences, useSuitePreferences } from "@/store/suitePreferences";

export function useFavoriteSync(scope: string, enabled: boolean) {
  const client = useQueryClient();
  const [failedScope, setFailedScope] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const preferences = useSuitePreferences(s => s.contexts[scope] || defaultSuitePreferences);
  const remote = useQuery({ queryKey: ["launcher-favorites", scope], enabled,
    queryFn: () => api.get<{ favorites: string[] | null }>("/access/launcher-preferences", { progress: false }).then(r => r.data),
    refetchInterval: 30_000, retry: false });
  useEffect(() => {
    if (!enabled || !remote.data) return;
    const current = useSuitePreferences.getState().contexts[scope] || defaultSuitePreferences;
    if (current.favoritesDirty) return;
    if (remote.data.favorites === null) {
      useSuitePreferences.getState().update(scope, { favoritesDirty: true });
    } else if (JSON.stringify(current.favorites) !== JSON.stringify(remote.data.favorites)) {
      useSuitePreferences.getState().update(scope, { favorites: remote.data.favorites });
    }
  }, [enabled, scope, remote.data]);
  useEffect(() => {
    if (!enabled || !remote.data || !preferences.favoritesDirty || failedScope === scope) return;
    let cancelled = false;
    const favorites = [...preferences.favorites];
    const timer = window.setTimeout(() => {
      void api.put("/access/launcher-preferences", { favorites }, { progress: false }).then(() => {
        if (cancelled) return;
        const latest = useSuitePreferences.getState().contexts[scope];
        if (JSON.stringify(latest?.favorites) === JSON.stringify(favorites)) {
          client.setQueryData(["launcher-favorites", scope], { favorites });
          useSuitePreferences.getState().update(scope, { favoritesDirty: false });
        }
      }).catch(() => { if (!cancelled) setFailedScope(scope); });
    }, 400);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [enabled, scope, preferences.favorites, preferences.favoritesDirty, remote.data, client, failedScope, attempt]);
  return { error: remote.isError || failedScope === scope, retry: () => {
    setFailedScope(null); setAttempt(value => value + 1); void remote.refetch();
  } };
}

import { useQuery } from '@tanstack/react-query';
import { useLocation } from 'react-router-dom';
import { commonRouteContext } from '@/lib/common-routes';
import { useAuthStore } from '@/store/authStore';
import { api } from '@/services/api';
import { defaultsScope } from '@/lib/form-defaults';
import { businessRouteLabel, profileTerm, resolveBusinessProfile, type ResolvedProfile, type TermKey } from '@/lib/business-profile';

const generic = resolveBusinessProfile([]);
export function useBusinessTerms() {
  const user = useAuthStore(state => state.user);
  const scope = defaultsScope();
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const module = (commonRouteContext(location.pathname, location.search)?.contextPath || location.pathname).split('/')[1];
  const workspace = ['crm', 'srm', 'fam', 'hrms', 'pms'].includes(module) ? params.get('space') || params.get('workspace') : null;
  const query = useQuery({ queryKey: ['business-profile', scope, workspace ? module : null, workspace], queryFn: async () => {
    const { data } = await api.get<ResolvedProfile>('/access/settings/business-profile/effective', { progress: false, params: workspace ? { workspace_module: module, workspace_id: workspace } : undefined });
    if (!data?.terms || !Object.keys(generic.terms).every(key => Array.isArray(data.terms[key as TermKey]) && data.terms[key as TermKey].length === 2)) throw new Error('Invalid business profile response');
    return data;
  }, enabled: Boolean(user), staleTime: 60_000, retry: 1 });
  const profile = query.data ?? generic;
  return { profile, term: (key: TermKey, plural = false) => profileTerm(profile, key, plural), routeLabel: (path: string, fallback: string) => businessRouteLabel(profile, path, fallback), loading: query.isPending, error: query.error };
}

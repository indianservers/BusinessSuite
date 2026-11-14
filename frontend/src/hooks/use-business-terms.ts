import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { defaultsScope } from '@/lib/form-defaults';
import { profileTerm, resolveBusinessProfile, type ResolvedProfile, type TermKey } from '@/lib/business-profile';

const generic = resolveBusinessProfile([]);
export function useBusinessTerms() {
  const scope = defaultsScope();
  const query = useQuery({ queryKey: ['business-profile', scope], queryFn: async () => (await api.get<ResolvedProfile>('/access/settings/business-profile/effective', { progress: false })).data, staleTime: 60_000, retry: 1 });
  const profile = query.data ?? generic;
  return { profile, term: (key: TermKey, plural = false) => profileTerm(profile, key, plural), loading: query.isPending, error: query.error };
}

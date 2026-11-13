import type { QueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import { useAuthStore } from '@/store/authStore';
import { canAccessRoute } from '@/lib/roles';

/** Validate the destination before atomically changing the tab's company/branch. */
export async function switchSuiteContext(qc: QueryClient, company: number, branch: string, href = window.location.pathname + window.location.search) {
  if (!window.dispatchEvent(new Event('suite:before-context-change', {cancelable:true}))) return false;
  const user = useAuthStore.getState().user;
  if (!user) throw new Error('Sign in before switching company.');
  await qc.cancelQueries();
  const {data: access} = await api.get('/access/me', {headers:{'X-Suite-Organization':String(company),'X-Suite-Branch':branch}});
  if (access.companyId !== company) throw new Error('The destination company could not be verified.');
  sessionStorage.setItem('suite-organization', String(company));
  sessionStorage.setItem('suite-branch', branch);
  useAuthStore.getState().setUser({...user, access});
  qc.clear();
  window.location.assign(canAccessRoute(href.split('?')[0], user.role, user.is_superuser) ? href : '/dashboard');
  return true;
}

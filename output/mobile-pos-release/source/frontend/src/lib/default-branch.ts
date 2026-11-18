import { useAuthStore } from '@/store/authStore';

// A preference is never authority: callers must validate it against fresh branch choices.
function key(company: number) {
  return `suite-default-branch:${sessionStorage.getItem('suite-tenant') || ''}:${useAuthStore.getState().user?.id}:${company}`;
}
export function defaultBranch(company: number): string | null {
  try { return localStorage.getItem(key(company)); } catch { return null; }
}
export function saveDefaultBranch(company: number, branch: string) {
  localStorage.setItem(key(company), branch);
  window.dispatchEvent(new Event('suite:default-branch-changed'));
}

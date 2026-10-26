const key = "internhub.application-access";
export const applicationToken = () => sessionStorage.getItem(key);
export function setApplicationToken(token: string | null) {
  if (token) sessionStorage.setItem(key,token);
  else sessionStorage.removeItem(key);
}

import { useSyncExternalStore } from "react";
import { useAuthStore, type AuthUser } from "@/store/authStore";
export function communicationActor(user:AuthUser|null|undefined) {
  return `${user?.id || 0}:${sessionStorage.getItem("suite-organization") || user?.access?.companyId || "primary"}`;
}
function subscribe(notify:()=>void){window.addEventListener("focus",notify);window.addEventListener("storage",notify);return()=>{window.removeEventListener("focus",notify);window.removeEventListener("storage",notify);};}
/** Company switching must not reuse another company/account's cached chat state. */
export function useCommunicationScope(){
  const user=useAuthStore(s=>s.user);
  return useSyncExternalStore(subscribe,()=>communicationActor(user));
}

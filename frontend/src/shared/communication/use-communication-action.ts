import {useAuthStore} from "@/store/authStore";

/** Canonical shared messaging authority; conversation membership still applies. */
export function useCommunicationAction(action:string){
  const user=useAuthStore(s=>s.user);
  if(user?.is_superuser)return true;
  if(!user?.access)return false;
  if(!user.access.managed)return true;
  return ["project_management","crm","hrms","srm","fam"].some(key=>{
    const grant=user.access!.grants[key];
    return !!grant?.enabled&&grant.actions.includes(action);
  });
}

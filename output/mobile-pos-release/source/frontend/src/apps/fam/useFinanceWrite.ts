import { useAuthStore } from "@/store/authStore";
/** Mirror central grants for affordances; the API remains authoritative. */
export function useFinanceWrite(permissions: string[], action = "any") {
  const user=useAuthStore(s=>s.user);
  if(user?.is_superuser)return true;
  const module=permissions.some(p=>p.startsWith("srm_"))?"srm":"fam";
  const grant=user?.access?.grants?.[module];
  if(grant)return grant.enabled && (action==="any"?grant.actions.some(a=>["create","edit","delete","configure","approve"].includes(a)):grant.actions.includes(action)) && permissions.some(p=>grant.permissions.includes(p));
  if(user?.access?.managed)return false;
  return ["admin","super_admin","fam_admin","fam_accountant","fam_finance_manager","srm_admin","srm_sales_manager"].includes(user?.role||"");
}

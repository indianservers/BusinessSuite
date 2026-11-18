import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";

export default function FinancialYearSetupGuidance({errors,date}: {errors:unknown[];date?:string}) {
  const user=useAuthStore(state=>state.user);
  const messages=errors.map(error=>(error as {response?:{data?:{detail?:unknown}}})?.response?.data?.detail);
  const message=messages.find((detail):detail is string=>typeof detail==="string"&&/financial[\s_-]*year/i.test(detail));
  if(!message)return null;
  return <div role="alert" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950 dark:bg-amber-950/20 dark:text-amber-100">
    <p className="font-medium">{message}</p>
    <p>Review the financial year covering {date||"the voucher date"}, then return here to retry. Your voucher stays open.</p>
    {canAccessRoute("/fam/financial-years",user?.role,user?.is_superuser)?<Button asChild variant="outline" className="mt-2"><Link to="/fam/financial-years" target="_blank" rel="noopener" aria-label="Open financial year settings (new tab)">Open financial year settings ↗</Link></Button>:<p>Ask your Finance administrator to review the financial year and voucher date.</p>}
  </div>;
}

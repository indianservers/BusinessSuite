import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
export default function MobileStockHint({id,trackInventory}:{id:number;trackInventory?:boolean}){
 const user=useAuthStore(s=>s.user);const stock=useQuery({queryKey:['mobile-stock',user?.id,user?.access?.companyId,id],queryFn:()=>api.get<{current_quantity?:number}>(`/srm/inventory/items/${id}`,{progress:false}).then(r=>r.data),enabled:!!trackInventory,staleTime:15000,retry:false});
 return <small className="block">{!trackInventory?'Available in this branch':stock.isPending?'Checking stock…':stock.data?.current_quantity != null ? `${stock.data.current_quantity} in stock`:'Stock not available'}</small>;
}

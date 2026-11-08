import {useNavigate} from "react-router-dom";
import {useState,useEffect,useRef} from "react";
import {useSmartCreation} from "@/shared/creation/SmartCreationProvider";
import {useQuery} from "@tanstack/react-query";
import {api} from "@/services/api";
import {Input} from "@/components/ui/input";
export const HR="/employees/workbench";
export const errorText=(e:any)=>typeof e.response?.data?.detail==="string"?e.response.data.detail:e.message||"Unable to save. Your changes are still available; retry.";
export type Person={id:number;name:string;employee_code:string;department?:string;branch?:string;status:string;email?:string;phone?:string};
export function PersonSearch({select,label="Find employee"}:{select:(p:Person)=>void;label?:string}){
 const [search,setSearch]=useState("");const query=useQuery({queryKey:["hr-work-search",search],queryFn:()=>api.get<{items:Person[]}>(`${HR}/search`,{params:{q:search}}).then(r=>r.data),enabled:search.trim().length>=2});
 return <div className="space-y-2"><Input aria-label={label} value={search} onChange={e=>setSearch(e.target.value)} placeholder="Name, employee ID, email or phone"/>{query.isError&&<p role="alert">{errorText(query.error)}</p>}{query.data?.items.map(p=><button key={p.id} className="block w-full rounded border p-2 text-left text-sm" onClick={()=>{select(p);setSearch("");}}>{p.name} · {p.employee_code} · {p.department||"No department"} · {p.status}<span className="block text-xs">{p.email} {p.phone}</span></button>)}</div>;
}
/** Employee shortcuts open the same form as the employee directory and sidebar. */
export function HRQuickAdd({close,saved}:{close:()=>void;saved:(id:number)=>void}){
 const creation=useSmartCreation(),navigate=useNavigate(),attempted=useRef(false);
 useEffect(()=>{
  if(attempted.current)return;
  attempted.current=true;
  const destination="/hrms/employees/new";
  const handled=creation?.open(destination,record=>{const employee=record as {id?:number}|undefined;if(employee?.id)saved(employee.id);});
  close();
  if(!handled)navigate(destination);
 },[creation,navigate,close,saved]);
 return null;
}

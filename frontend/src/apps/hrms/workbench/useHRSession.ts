import {useEffect,useState,type Dispatch,type SetStateAction} from "react";
import {useAuthStore} from "@/store/authStore";
import {hrScope} from "./state";
/** Per-user, per-company navigation drafts. Never use for passwords. */
export function useHRSession<T>(name:string,initial:T):[T,Dispatch<SetStateAction<T>>]{
 const user=useAuthStore(s=>s.user),key=`hrms.session.${hrScope(user?.id,user?.access?.companyId)}.${name}`;
 const read=():T=>{try{const saved=sessionStorage.getItem(key);return saved?JSON.parse(saved):initial;}catch{return initial;}};
 const [record,setRecord]=useState(()=>({key,value:read()}));
 const value=record.key===key?record.value:read();
 useEffect(()=>{if(record.key!==key)setRecord({key,value:read()});else sessionStorage.setItem(key,JSON.stringify(record.value));},[key,record]);
 const setValue:Dispatch<SetStateAction<T>>=next=>setRecord(prev=>{const current=prev.key===key?prev.value:read();return {key,value:typeof next==="function"?(next as (previous:T)=>T)(current):next};});
 return [value,setValue];
}

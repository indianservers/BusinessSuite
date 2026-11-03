import { useEffect, useState, type SetStateAction, type Dispatch } from "react";
import { useAuthStore } from "@/store/authStore";
import { useMobile } from "./useMobile";
export function useMobileSessionState<T>(name: string, initial: T): [T, Dispatch<SetStateAction<T>>] {
 const mobile=useMobile(), user=useAuthStore(s=>s.user); const key=`mobile-filter:${user?.id}:${user?.access?.companyId}:${name}`;
 const read=()=>{if(!mobile)return initial;try{return JSON.parse(sessionStorage.getItem(key)||'null')??initial;}catch{return initial;}};
 const [state,setState]=useState<{key:string;value:T}>(()=>({key,value:read()}));
 if(state.key!==key)setState({key,value:read()});
 useEffect(()=>{if(mobile&&state.key===key){try{sessionStorage.setItem(key,JSON.stringify(state.value));}catch{/* Optional persistence. */}}},[key,mobile,state]);
 const setValue:Dispatch<SetStateAction<T>>=next=>setState(previous=>({key,value:typeof next==='function'?(next as (v:T)=>T)(previous.key===key?previous.value:read()):next}));
 return [state.key===key?state.value:read(),setValue];
}

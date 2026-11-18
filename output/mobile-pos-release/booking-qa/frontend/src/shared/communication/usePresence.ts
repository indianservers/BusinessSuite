import { useCommunicationScope } from "./scope";
import { useAuthStore } from "@/store/authStore";
import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
export function usePresence(wid:number,rid:number,enabled:boolean) {
  const actor=useCommunicationScope();
  const lastTyping=useRef(0),url=`/collaboration/workspaces/${wid}/chat/conversations/${rid}/presence`;
  const presence=useQuery({queryKey:["communication-presence",actor,wid,rid],enabled,queryFn:async()=>(await api.get<{users:{id:number;typing:boolean}[]}>(url,{progress:false})).data,refetchInterval:5000,refetchIntervalInBackground:false});
  useEffect(()=>{
    if(!enabled)return;
    const heartbeat=()=>{if(!document.hidden)void api.put(url,{typing:false},{progress:false}).catch(()=>{});};
    heartbeat(); const interval=setInterval(heartbeat,30000);
    return()=>clearInterval(interval);
  },[url,enabled]);
  return {users:presence.data?.users||[],typing:()=>{const now=Date.now();if(enabled&&now-lastTyping.current>4500){lastTyping.current=now;void api.put(url,{typing:true},{progress:false}).catch(()=>{});}}};
}

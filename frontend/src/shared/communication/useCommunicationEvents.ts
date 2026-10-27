import { useCommunicationScope } from "./scope";
import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useRealtimeStore } from "@/apps/project-management/realtime";
import { useAuthStore } from "@/store/authStore";
/** Durable invalidations recover missed socket events across server instances.
 * Payloads contain no message/participant metadata. Membership is checked per read.
 */
export function useCommunicationEvents() {
  const scope=useCommunicationScope();
  const qc=useQueryClient(), user=useAuthStore(s=>s.user);
  const socketConnected = useRealtimeStore(s=>s.connected && s.transport==="websocket");
  useEffect(()=>{
    if(!user || socketConnected) return;
    let cancelled=false, cursor:number|undefined, timer:ReturnType<typeof setTimeout>;
    async function receive(){
      try{
        const {data}=await api.get<{cursor:number;changed:boolean}>("/collaboration/events",{params:{cursor},progress:false});
        if(cancelled)return;
        const reconnect=cursor===undefined;
        cursor=data.cursor;
        if(data.changed || reconnect) await Promise.all(["chat-inbox","chat-history","chat-search","communication-collaboration","communication-discussions","communication-files","communication-meetings"].map(async key=>{
          // A first history request may have started before the cursor snapshot.
          // Cancel it before refetching, so a late old response cannot hide a send.
          await qc.cancelQueries({queryKey:[key]});
          await qc.invalidateQueries({queryKey:[key]});
        }));
      }catch{cursor=undefined;}
      finally{if(!cancelled)timer=setTimeout(receive,document.hidden?15000:5000);}
    }
    void receive();
    const focus=()=>{if(!document.hidden)cursor=undefined;}; window.addEventListener("online",focus);document.addEventListener("visibilitychange",focus);
    return()=>{cancelled=true;clearTimeout(timer);window.removeEventListener("online",focus);document.removeEventListener("visibilitychange",focus);};
  },[scope,qc,socketConnected]);
}

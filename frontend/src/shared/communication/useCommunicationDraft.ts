import { useEffect, useRef } from "react";
import { api } from "@/services/api";
/** Local drafts are immediately available; server drafts add recovery across sessions. */
export function useCommunicationDraft({wid,rid,thread,context,enabled,draft,setDraft}:{wid:number;rid:number;thread:number;context:string;enabled:boolean;draft:string|undefined;setDraft:(value:string)=>void}) {
  const current = useRef({context,draft,setDraft}); current.current={context,draft,setDraft};
  const loaded = useRef("");
  const baseline = useRef("");
  useEffect(()=>{
    if(!enabled) return;
    let cancelled=false;
    loaded.current="";
    void api.get<{body:string}>(`/collaboration/workspaces/${wid}/chat/conversations/${rid}/draft`,{params:{thread_id:thread},progress:false}).then(({data})=>{
      if(cancelled || current.current.context!==context) return;
      loaded.current=context; baseline.current=current.current.draft ?? data.body;
      if(current.current.draft===undefined && data.body) current.current.setDraft(data.body);
    }).catch(()=>{ if(!cancelled) loaded.current=context; });
    return()=>{cancelled=true;};
  },[wid,rid,thread,context,enabled]);
  useEffect(()=>{
    if(!enabled) return;
    const timer=setTimeout(()=>{
      if(loaded.current!==context || draft===undefined || draft===baseline.current) return;
      void api.put(`/collaboration/workspaces/${wid}/chat/conversations/${rid}/draft`,{body:draft,thread_id:thread},{progress:false}).then(()=>{if(current.current.context===context)baseline.current=draft;}).catch(()=>{ /* Local recovery remains available; retry on next edit. */ });
    },1200);
    return()=>clearTimeout(timer);
  },[draft,context,enabled,wid,rid,thread]);
}

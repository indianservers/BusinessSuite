import {useEffect, useRef, useState} from "react";
import {useAuthStore} from "@/store/authStore";

/** Only confirmed snapshots are acknowledged. A failed snapshot waits for an edit or explicit retry. */
export function useRecordAutosave<T>({value, enabled, dirty, save, delay=1400}: {
  value:T; enabled:boolean; dirty:boolean; save:(value:T)=>Promise<boolean | void>; delay?:number;
}) {
  const snapshot=JSON.stringify(value);
  const latest=useRef({value,save,snapshot,enabled,dirty});
  latest.current={value,save,snapshot,enabled,dirty};
  const confirmed=useRef<string>(),failed=useRef<string>(),running=useRef(false),mounted=useRef(true);
  const [phase,setPhase]=useState<"idle"|"pending"|"saving"|"saved"|"error">("idle");
  const [revision,setRevision]=useState(0);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  useEffect(()=>{
    if(!enabled||!dirty){if(!dirty)confirmed.current=snapshot;return;}
    if(snapshot===confirmed.current||snapshot===failed.current||running.current)return;
    setPhase("pending");
    const timer=setTimeout(async()=>{
      const current=latest.current;
      if(!current.enabled||!current.dirty||running.current)return;
      running.current=true;setPhase("saving");
      try {
        const saved=await current.save(current.value);
        if(saved===false)throw new Error("Save was not confirmed");
        confirmed.current=current.snapshot;failed.current=undefined;
        if(mounted.current)setPhase("saved");
      }catch{failed.current=current.snapshot;if(mounted.current)setPhase("error");}
      finally{running.current=false;if(mounted.current)setRevision(n=>n+1);}
    },delay);
    return()=>clearTimeout(timer);
  },[snapshot,enabled,dirty,delay,revision]);
  return {phase,saving:phase==="saving",message:phase==="saving"?"Saving automatically…":phase==="pending"?"Unsaved changes":phase==="saved"?"All changes saved":phase==="error"?"Automatic save failed. Your edits are retained; use Save to retry.":""};
}

export function recordDraftKey(name:string) {
  const {user}=useAuthStore.getState();
  let organization = "", branch = "";
  try { organization = sessionStorage.getItem("suite-organization") || ""; branch = sessionStorage.getItem("suite-branch") || ""; } catch { /* In-memory editing remains available. */ }
  return `suite-form-draft:v1:${user?.id}:${user?.access?.companyId||organization}:${branch}:${name}`;
}

/** Preserve the complete React draft, including fields on inactive tabs. Never submit a new record. */
export function useRecordDraft<T>(name:string,value:T,restore:(value:T)=>void,enabled:boolean) {
  const key=recordDraftKey(name),snapshot=JSON.stringify(value),latest=useRef(restore),skip=useRef(true),restored=useRef<string>();
  const [status, setStatus] = useState<"idle" | "restored" | "saved" | "unavailable">("idle");
  latest.current=restore;
  useEffect(()=>{
    if(!enabled||restored.current===key)return;
    restored.current=key;
    skip.current=true;
    try{const saved=sessionStorage.getItem(key);if(saved){latest.current(JSON.parse(saved));setStatus("restored");}}catch{setStatus("unavailable");}
  },[key,enabled]);
  useEffect(()=>{
    if(!enabled)return;
    if(skip.current){skip.current=false;return;}
    try{sessionStorage.setItem(key,snapshot);setStatus(current => current === "restored" ? current : "saved");}catch{setStatus("unavailable");}
  },[key,snapshot,enabled]);
  // Async owners can acknowledge a confirmed field before they unmount. Capture
  // this render's key so a late response cannot overwrite a new actor's draft.
  const persist = (value:T) => { if(!enabled)return false;try{sessionStorage.setItem(key,JSON.stringify(value));return true;}catch{return false;} };
  return Object.assign(()=>{try{sessionStorage.removeItem(key);}catch{/* The successful write is still confirmed. */}}, { status, persist });
}

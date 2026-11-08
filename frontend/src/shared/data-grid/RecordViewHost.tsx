import { createContext, useCallback, useContext, useMemo, useState, type ComponentType } from "react";

type Registration = {owner:string;table:boolean};
const Context = createContext<{
  host:HTMLDivElement|null;
  setHost:(host:HTMLDivElement|null)=>void;
  registration:Registration|null;
  register:(value:Registration)=>void;
  unregister:(owner:string)=>void;
}|null>(null);
export const useRecordViewHost = () => useContext(Context);

/** Moves shared record tabs into the page's existing view strip, preserving its own workflows. */
export function withRecordViewHost<P extends object>(Page:ComponentType<P>) {
  return function UnifiedRecordPage(props:P) {
    const [host,setHost]=useState<HTMLDivElement|null>(null);
    const [registration,setRegistration]=useState<Registration|null>(null);
    const register=useCallback((value:Registration)=>setRegistration(current=>current||value),[]);
    const unregister=useCallback((owner:string)=>setRegistration(current=>current?.owner===owner?null:current),[]);
    const value=useMemo(()=>({host,setHost,registration,register,unregister}),[host,registration,register,unregister]);
    return <Context.Provider value={value}><Page {...props}/></Context.Provider>;
  };
}

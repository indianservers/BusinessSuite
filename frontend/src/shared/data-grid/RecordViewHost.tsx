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
    const [registrations,setRegistrations]=useState<Registration[]>([]);
    const registration=registrations[0]||null;
    const register=useCallback((value:Registration)=>setRegistrations(current=>{const at=current.findIndex(item=>item.owner===value.owner);if(at<0)return [...current,value];if(current[at].table===value.table)return current;return current.map((item,index)=>index===at?value:item);}),[]);
    const unregister=useCallback((owner:string)=>setRegistrations(current=>current.filter(item=>item.owner!==owner)),[]);
    const value=useMemo(()=>({host,setHost,registration,register,unregister}),[host,registration,register,unregister]);
    return <Context.Provider value={value}><Page {...props}/></Context.Provider>;
  };
}

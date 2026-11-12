import {createContext,useContext,useState,type Dispatch,type ReactNode,type SetStateAction} from "react";
import type {WorkTask} from "../pages/workspaceTypes";

type FailedStatus={status:string;latest?:WorkTask}|null;
type EditState={failed:FailedStatus;busy:boolean;task?:WorkTask};
type States=Record<number,EditState>;
const Context=createContext<{states:States;setStates:Dispatch<SetStateAction<States>>}|null>(null);

/** Ephemeral collection ownership survives table/card row replacement; scope owns lifetime. */
export function InlineTaskEditState({children}:{children:ReactNode}){
 const [states,setStates]=useState<States>({});
 return <Context.Provider value={{states,setStates}}>{children}</Context.Provider>;
}

export function useInlineTaskEdits(){
 const context=useContext(Context);
 if(!context)throw new Error("Inline task editing requires collection ownership");
 return context;
}
export function useInlineTaskEditState(task:WorkTask){
 const id=task.id;
 const context=useInlineTaskEdits();
 const {states,setStates}=context;
 const state=states[id]||{failed:null,busy:false};
 const setFailed:Dispatch<SetStateAction<FailedStatus>>=update=>setStates(previous=>{
  const current=previous[id]||{failed:null,busy:false};
  const failed=typeof update==="function"?update(current.failed):update;
  return {...previous,[id]:{...current,failed,task:failed?current.task||task:undefined}};
 });
 const setBusy=(busy:boolean)=>setStates(previous=>({...previous,[id]:{...previous[id]||{failed:null},busy}}));
 return {...state,setFailed,setBusy};
}

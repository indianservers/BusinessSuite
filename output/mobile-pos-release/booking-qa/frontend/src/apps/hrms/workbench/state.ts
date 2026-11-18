import {create} from "zustand";
import {persist} from "zustand/middleware";
export type HRLink={path:string;label:string};
export type HRContext={employee_id?:string;department_id?:string;branch_id?:string;month?:string;year?:string};
type Preferences={pins:HRLink[];visits:Record<string,{label:string;count:number}>;context:HRContext};
const empty:Preferences={pins:[],visits:{},context:{}};
export const hrScope=(id?:number,company?:number)=>`${id||0}:${company||0}`;
export const useHRWork= create<{scopes:Record<string,Preferences>;visit:(scope:string,p:HRLink)=>void;pin:(scope:string,p:HRLink)=>void;context:(scope:string,c:HRContext)=>void}>()(persist(set=>({
 scopes:{},
 visit:(scope,p)=>set(s=>{const prev=s.scopes[scope]||empty;return {scopes:{...s.scopes,[scope]:{...prev,visits:{...prev.visits,[p.path]:{label:p.label,count:(prev.visits[p.path]?.count||0)+1}}}}};}),
 pin:(scope,p)=>set(s=>{const prev=s.scopes[scope]||empty;return {scopes:{...s.scopes,[scope]:{...prev,pins:prev.pins.some(i=>i.path===p.path)?prev.pins.filter(i=>i.path!==p.path):[...prev.pins,p]}}};}),
 context:(scope,c)=>set(s=>({scopes:{...s.scopes,[scope]:{...(s.scopes[scope]||empty),context:{...(s.scopes[scope]?.context||{}),...c}}}})),
}),{name:"hrms.daily-work.v1"}));

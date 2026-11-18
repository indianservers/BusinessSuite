import {create} from "zustand";
import {persist} from "zustand/middleware";
export type CRMShortcut={path:string;label:string};
type Preferences={pins:CRMShortcut[];visits:Record<string,{count:number;label:string}>};
const empty:Preferences={pins:[],visits:{}};
export const useCRMProductivity= create<{scopes:Record<string,Preferences>;visit:(scope:string,p:CRMShortcut)=>void;pin:(scope:string,p:CRMShortcut)=>void;move:(scope:string,path:string,direction:number)=>void}>()(persist((set)=>({scopes:{},visit:(scope,p)=>set(s=>{const current=s.scopes[scope]||empty;return {scopes:{...s.scopes,[scope]:{...current,visits:{...current.visits,[p.path]:{label:p.label,count:(current.visits[p.path]?.count||0)+1}}}}};}),pin:(scope,p)=>set(s=>{const current=s.scopes[scope]||empty;return {scopes:{...s.scopes,[scope]:{...current,pins:current.pins.some(i=>i.path===p.path)?current.pins.filter(i=>i.path!==p.path):[...current.pins,p]}}};}),move:(scope,path,direction)=>set(s=>{const current=s.scopes[scope]||empty,pins=[...current.pins],index=pins.findIndex(p=>p.path===path),to=index+direction;if(index<0||to<0||to>=pins.length)return s;[pins[index],pins[to]]=[pins[to],pins[index]];return {scopes:{...s.scopes,[scope]:{...current,pins}}};})}),{name:"crm.personal-navigation.v1"}));
export const crmScope=(userId?:number,companyId?:number)=>`${userId||0}:${companyId||0}`;

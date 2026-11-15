import { useAuthStore } from "@/store/authStore";
import { logicalIntentScope } from "./logical-intent-scope";
import { readFinancialIntent, saveFinancialIntent } from "./financial-intent";
type Recovery<T> = { pending:boolean; payload:T|null; sourceKeys:string[] };
/** Only the released v2 key's complete native identity proves a recoverable source. */
export function readPOSCheckoutIntent<T extends {payload:{request_id:string};recoverySourceKeys?:string[]}>(key:string): Recovery<T> {
  const current = readFinancialIntent<T>(key);

  const user=useAuthStore.getState().user;
  const identity=[user?.id,sessionStorage.getItem("suite-tenant"),sessionStorage.getItem("suite-organization") || user?.access?.companyId,sessionStorage.getItem("suite-branch"),(JSON.parse(logicalIntentScope()) as unknown[]).slice(-1)[0]];
  const prefix="business-suite-srm-pos-v2:",suffix=":uncertain-checkout";
  if(current.pending) {
    const valid=typeof current.payload?.payload?.request_id === "string";
    const rawSources=current.payload?.recoverySourceKeys;
    if(rawSources !== undefined && !Array.isArray(rawSources))return {pending:true,payload:null,sourceKeys:[]};
    const sourceKeys=(rawSources || []).filter(source=>{
      try { const parsed=JSON.parse(decodeURIComponent(source.slice(prefix.length,-suffix.length))); return source.startsWith(prefix)&&source.endsWith(suffix)&&Array.isArray(parsed)&&parsed.length===8&&JSON.stringify(parsed.slice(0,5))===JSON.stringify(identity); } catch { return false; }
    });
    return {pending:true,payload:valid?current.payload:null,sourceKeys};
  }
  let payload:T|null=null; const sourceKeys:string[]=[];
  try {
    for(let index=0;index<localStorage.length;index++) {
      const source=localStorage.key(index)!;
      if(!source.startsWith(prefix)||!source.endsWith(suffix))continue;
      let sourceIdentity:unknown;
      try { sourceIdentity=JSON.parse(decodeURIComponent(source.slice(prefix.length,-suffix.length))); } catch { continue; }
      if(!Array.isArray(sourceIdentity)||sourceIdentity.length!==8||JSON.stringify(sourceIdentity.slice(0,4))!==JSON.stringify(identity.slice(0,4)))continue;
      if(sourceIdentity[4]!==identity[4]) {
        if(sourceIdentity[4]===null || identity[4]===null)return {pending:true,payload:null,sourceKeys};
        continue;
      }
      const raw=localStorage.getItem(source); if(!raw || raw==="null")continue;
      const value=JSON.parse(raw) as T;
      if(!value?.payload?.request_id)return {pending:true,payload:null,sourceKeys};
      if(payload && JSON.stringify(payload)!==JSON.stringify(value))return {pending:true,payload:null,sourceKeys};
      payload=value;sourceKeys.push(source);
    }
    if(payload) { payload={...payload,recoverySourceKeys:sourceKeys}; saveFinancialIntent(key,payload); }
    return {pending:!!payload,payload,sourceKeys};
  } catch { return {pending:true,payload:null,sourceKeys}; }
}

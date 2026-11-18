import { logicalIntentScope } from "./logical-intent-scope";
const prefix = "suite-financial-intent-v1:";
export function financialIntentKey(kind: "checkout" | "payment" | "invoice_payment" | "refund" | "cash_movement", recordId?: number) {
  return `${prefix}${JSON.stringify([logicalIntentScope(),kind,recordId ?? null])}`;
}
/** A damaged/unreadable recovery store is an opaque lock, never permission for a new request. */
export function readFinancialIntent<T>(key: string): { pending: boolean; payload: T | null } {
  try {
    const raw = localStorage.getItem(key);
    if(raw !== null)return {pending:true,payload:JSON.parse(raw) as T};
    const target=JSON.parse(key.slice(prefix.length)) as [string,string,number|null];
    const identity=JSON.parse(target[0]) as unknown[];
    // An implicit selector whose grant disappeared cannot unlock a different key.
    // Only opaque presence crosses this uncertain identity, never the private body.
    if(identity[identity.length-1]===null)for(let index=0;index<localStorage.length;index++) {
      const other=localStorage.key(index)!;if(!other.startsWith(prefix)||other===key)continue;
      try { const candidate=JSON.parse(other.slice(prefix.length));const source=JSON.parse(candidate[0]);if(candidate[1]===target[1]&&candidate[2]===target[2]&&JSON.stringify(source.slice(0,-1))===JSON.stringify(identity.slice(0,-1)))return {pending:true,payload:null}; } catch { /* Unproved keys are never adopted. */ }
    }
    return {pending:false,payload:null};
  }
  catch { return {pending:true,payload:null}; }
}
export function saveFinancialIntent<T>(key: string, payload: T) {
  localStorage.setItem(key,JSON.stringify(payload));
}
export function clearFinancialIntent(key: string) { localStorage.removeItem(key); }

/** Recover one drawer intent in the exact current owner/realm, before starting any new cash action. */
export function findPendingCashIntent<T>(): { pending: boolean; key: string | null; recordId: number | null; payload: T | null } {
  const opaque = {pending:true,key:null,recordId:null,payload:null};
  try {
    const scope=logicalIntentScope(), identity=JSON.parse(scope) as unknown[];
    if(!Array.isArray(identity)||identity.length!==7||identity[0]!=="intent-v1"||!Number.isSafeInteger(identity[1])||Number(identity[1])<=0||!Number.isSafeInteger(identity[3])||Number(identity[3])<=0)return opaque;
    const matching: {key:string;recordId:number|null}[]=[];
    let ambiguous=false;
    for(let index=0;index<localStorage.length;index++) {
      const key=localStorage.key(index);if(!key?.startsWith(prefix))continue;
      try {
        const target=JSON.parse(key.slice(prefix.length));
        if(!Array.isArray(target)||target.length!==3||target[1]!=="cash_movement")continue;
        if(target[0]===scope)matching.push({key,recordId:Number.isSafeInteger(target[2])&&target[2]>0?target[2]:null});
        else if(identity[identity.length-1]===null) {
          const source=JSON.parse(target[0]);
          if(Array.isArray(source)&&JSON.stringify(source.slice(0,-1))===JSON.stringify(identity.slice(0,-1)))ambiguous=true;
        }
      } catch { /* A foreign/unproved namespace never supplies a private body. */ }
    }
    if(ambiguous)return opaque;
    const first=matching.sort((a,b)=>a.key.localeCompare(b.key))[0];
    if(!first)return {pending:false,key:null,recordId:null,payload:null};
    try { return {pending:true,...first,payload:JSON.parse(localStorage.getItem(first.key) || "null") as T}; }
    catch { return {...opaque,key:first.key,recordId:first.recordId}; }
  } catch { return opaque; }
}

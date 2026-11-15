import { logicalIntentScope } from "./logical-intent-scope";
const prefix = "suite-financial-intent-v1:";
export function financialIntentKey(kind: "checkout" | "payment" | "refund" | "cash_movement", recordId?: number) {
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

import { useAuthStore } from "@/store/authStore";
import type { BusinessPackDiscovery } from "./business-pack-types";
import { selectedPackContext } from "./pack-context";
/** Stable identity for unresolved money requests. Authority changes must never unlock a second key. */
export function logicalIntentScope() {
  const user = useAuthStore.getState().user;
  const raw = selectedPackContext();
  const discovery=(user?.access as unknown as {businessPacks?:BusinessPackDiscovery})?.businessPacks;
  const branch=Number(sessionStorage.getItem("suite-branch"));
  let pack=raw;
  if(raw===null && Number.isSafeInteger(branch) && branch>0 && discovery?.state==="ready" && discovery.hasMore===false) {
    const eligible=discovery.contexts.filter(context=>context.branchId===branch && Number.isSafeInteger(context.contextId) && context.contextId>0);
    const selected=discovery.selectionState==="verified" ? eligible.find(context=>context.contextId===discovery.selectedContextId) : undefined;
    if(selected || eligible.length===1)pack=String((selected || eligible[0]).contextId);
  }
  return JSON.stringify(["intent-v1",user?.id,sessionStorage.getItem("suite-tenant"),user?.access?.companyId,sessionStorage.getItem("suite-organization"),sessionStorage.getItem("suite-branch"),pack]);
}

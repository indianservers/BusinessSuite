import type { AuthUser } from '@/store/authStore';
import type { BusinessPackDiscovery } from '@/lib/business-pack-types';
import { selectedPackContext } from '@/lib/pack-context';
/** Only a UI background-query hint; every explicit operation remains server-authorized. */
export function selectedConstruction(user: AuthUser | null): boolean {
  const discovery=(user?.access as unknown as {businessPacks?:BusinessPackDiscovery})?.businessPacks;
  if(discovery?.state!=='ready' || discovery.hasMore!==false || discovery.selectionState==='invalid') return false;
  let branch: string | null, selector: string | null;
  try {
    branch=sessionStorage.getItem('suite-branch');
    selector=selectedPackContext();
  } catch {
    return false;
  }
  if(!branch || !/^[1-9][0-9]*$/.test(branch)) return false;
  const choices=discovery.contexts.filter(choice=>choice.branchId===Number(branch));
  const choice=selector===null ? choices.length===1 ? choices[0] : undefined : /^[1-9][0-9]*$/.test(selector) && discovery.selectionState==='verified' && discovery.selectedContextId===Number(selector) ? choices.find(choice=>choice.contextId===Number(selector)) : undefined;
  return choice?.packKey==='construction' && [choice.contextId,choice.packVersion,choice.contextRevision,choice.grantRevision,choice.activationRevision].every(value=>Number.isSafeInteger(value)&&value>0);
}

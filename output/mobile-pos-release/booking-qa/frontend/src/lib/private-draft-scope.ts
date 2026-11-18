import { useRef } from "react";
import { recordScope, useRecordScope } from "./record-scope";
import { selectedPackContext } from "./pack-context";
import { useAuthStore } from "@/store/authStore";
import { useRecordScopeOwner } from "@/hooks/use-record-scope-owner";
import type { BusinessPackDiscovery } from "./business-pack-types";

/** Browser drafts are private to their source authority; old unproved keys are never adopted. */
export function privateDraftScope() {
  const user = useAuthStore.getState().user;
  const discovery = (user?.access as unknown as { businessPacks?: BusinessPackDiscovery })?.businessPacks;
  const selected = selectedPackContext();
  const verified = discovery?.selectionState === "verified" && String(discovery.selectedContextId) === selected
    ? discovery.contexts.find(item => String(item.contextId) === selected) : undefined;
  return JSON.stringify([recordScope(user), verified ? [verified.contextId, verified.branchId, verified.role, verified.packVersion, verified.contextRevision, verified.grantRevision, verified.activationRevision] : null]);
}
export function privateDraftKey(kind: string, ...identity: unknown[]) {
  return `${kind}:v2:${JSON.stringify([privateDraftScope(), ...identity])}`;
}
export function usePrivateDraftScope() {
  useRecordScope();
  return privateDraftScope();
}
export function usePrivateDraftOwner() {
  const nativeOwner = useRecordScopeOwner();
  const owner = useRef(privateDraftScope());
  return () => nativeOwner() && owner.current === privateDraftScope();
}

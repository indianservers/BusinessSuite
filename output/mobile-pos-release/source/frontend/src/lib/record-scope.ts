import { securityAuthStamp } from "./security-auth-stamp";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/authStore";
import { selectedPackContext } from './pack-context';

export function recordScope(user: ReturnType<typeof useAuthStore.getState>["user"]) {
  return [user?.id, user?.access?.companyId, sessionStorage.getItem("suite-tenant"), sessionStorage.getItem("suite-organization"), sessionStorage.getItem("suite-branch"), selectedPackContext(), securityAuthStamp(user)].join(":");
}

export function useRecordScope() {
  const user = useAuthStore(state => state.user), [generation, setGeneration] = useState(0);
  useEffect(() => {
    const changed = () => setGeneration(value => value + 1);
    const names = ["suite:organization-changed", "suite:branch-changed", "suite:tenant-changed", "suite:pack-context-changed", "suite:record-access-changed"];
    names.forEach(name => window.addEventListener(name, changed));
    return () => names.forEach(name => window.removeEventListener(name, changed));
  }, []);
  return `${recordScope(user)}:${generation}`;
}

import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/authStore";

export function recordScope(user: ReturnType<typeof useAuthStore.getState>["user"]) {
  return [user?.id, user?.access?.companyId, sessionStorage.getItem("suite-organization"), sessionStorage.getItem("suite-branch"), JSON.stringify(user?.access?.grants)].join(":");
}

export function useRecordScope() {
  const user = useAuthStore(state => state.user), [generation, setGeneration] = useState(0);
  useEffect(() => {
    const changed = () => setGeneration(value => value + 1);
    const names = ["suite:organization-changed", "suite:branch-changed", "suite:record-access-changed"];
    names.forEach(name => window.addEventListener(name, changed));
    return () => names.forEach(name => window.removeEventListener(name, changed));
  }, []);
  return `${recordScope(user)}:${generation}`;
}

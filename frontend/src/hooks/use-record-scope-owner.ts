import { useEffect, useRef } from "react";
import { useAuthStore } from "@/store/authStore";
import { recordScope } from "@/shared/records/Record360Workspace";

/** Keep asynchronous UI completions within the context that started them. */
export function useRecordScopeOwner() {
  const owner = useRef(recordScope(useAuthStore.getState().user));
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => { active.current = false; };
  }, []);
  return () => active.current && owner.current === recordScope(useAuthStore.getState().user);
}

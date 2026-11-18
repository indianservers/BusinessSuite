import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/authStore";
import { syncScope } from "@/shared/record-sync/store";
import { useMobile } from "./useMobile";

/** Reset phone-owned views when the existing application context changes. */
export function useMobileContext(persistOutsideMobile = false) {
  const phone = useMobile(480);
  const [scope, setScope] = useState(syncScope);
  useEffect(() => {
    if (!phone && !persistOutsideMobile) return;
    const changed = () => setScope(syncScope());
    changed();
    const unsubscribe = useAuthStore.subscribe(changed);
    const events = ["suite:organization-changed", "suite:branch-changed", "storage"];
    events.forEach(name => window.addEventListener(name, changed));
    return () => { unsubscribe(); events.forEach(name => window.removeEventListener(name, changed)); };
  }, [phone, persistOutsideMobile]);
  return scope;
}

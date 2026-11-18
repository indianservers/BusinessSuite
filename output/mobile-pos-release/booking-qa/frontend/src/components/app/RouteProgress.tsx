import { useEffect } from "react";
import { useLoadingContext } from "@/hooks/use-loading-context";
import { progress } from "@/lib/async-progress";
import { setProgressContext } from "@/lib/progress-context";
/** Navigation progress follows mounted Suspense/data boundaries, never a timer. */
export default function RouteProgress() {
  const context = useLoadingContext();
  useEffect(() => {
    setProgressContext({ title: context.resource, module: context.module });
    progress.leaveRoute(context.pathname);
  }, [context.resource, context.module, context.pathname]);
  return null;
}
export function PendingPageProgress() {
  return null;
}

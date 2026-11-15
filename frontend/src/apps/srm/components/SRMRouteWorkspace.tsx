import { useContext } from "react";
import type { FrontendRoute } from "@/appRegistry";
import OperationsWorkspace from "@/components/layout/OperationsWorkspace";
import { OperationContentContext } from "@/lib/operation-panel";

/** Native and shared hosts use the same SRM manager, including its operation tabs. */
export default function SRMRouteWorkspace({ route, routes }: { route: FrontendRoute; routes: FrontendRoute[] }) {
  const embedded = useContext(OperationContentContext);
  return embedded ? <>{route.element}</> : <OperationsWorkspace route={route} routes={routes} />;
}

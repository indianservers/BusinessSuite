import { createElement, lazy, Suspense } from "react";
import type { CommunicationWorkspaceProps } from "./types";
const Workspace = lazy(() => import("./CommunicationWorkspace"));
/** Keep the editor and timeline out of modules that only render a launcher. */
export function CommunicationWorkspace(props: CommunicationWorkspaceProps) {
  return createElement(Suspense, { fallback: createElement("p", { role: "status" }, "Loading communication workspace…") }, createElement(Workspace, props));
}
export { ContextualChat, ConversationLauncher, TaskConversationSource, moduleAdapters } from "./adapters";
export { FollowUpWidget } from "./widgets";
export type { CommunicationWorkspaceProps, CommunicationContext, CommunicationFeatures, CommunicationModule } from "./types";

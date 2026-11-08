import { useContext, type ReactNode } from "react";
import { CreationSurfaceContext } from "./CreationSurfaceContext";
import { SmartCreateModal } from "./SmartCreateModal";

/** Keep the original editor and its owner state; new records use the common window. */
export function CreationEditorSurface({ creating, title, children, onClose }: { creating: boolean; title: string; children: ReactNode; onClose: () => void }) {
  const inside = useContext(CreationSurfaceContext);
  if (!creating || inside) return <>{children}</>;
  return <SmartCreateModal definition={{entity:title,title,presentation:"page",size:"large"}} onClose={onClose}>{children}</SmartCreateModal>;
}

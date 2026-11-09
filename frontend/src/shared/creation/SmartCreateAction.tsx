import type { ReactElement, ReactNode } from "react";
import { SmartCreateSection } from "./SmartCreateSection";

/** Existing actions with preset payloads still review their context in the common creation window. */
export function SmartCreateAction({ title, description, children }: { title: string; description?: ReactNode; children: ReactElement<{ onClick?: () => void }> }) {
  return <SmartCreateSection nested title={title} size="compact" trigger={children}>
    <p className="text-sm text-muted-foreground">{description || "Create this record using the current page’s selected values and settings."}</p>
    {children}
  </SmartCreateSection>;
}

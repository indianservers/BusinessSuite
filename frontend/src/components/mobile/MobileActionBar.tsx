import type { ReactNode } from "react";
import "./mobile-action-bar.css";
/** Mobile presentation only; callers retain validation, permissions and save handlers. */
export function MobileActionBar({children, label = "Page actions"}: {children:ReactNode;label?:string}) {
  return <div className="suite-mobile-action-bar" role="group" aria-label={label}>{children}</div>;
}

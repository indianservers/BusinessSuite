import { Children, isValidElement, type ReactNode } from "react";
import { normalizePriority, type Priority } from "./priority";

/** Read the chosen value, never the complete option list of a priority editor. */
export function cellPriority(content: ReactNode): Priority | undefined {
  for (const child of Children.toArray(content)) {
    const text=normalizePriority(child);
    if (text) return text;
    if (!isValidElement<Record<string,unknown>>(child) || child.type === "option") continue;
    const props=child.props;
    if ("value" in props) { const value=normalizePriority(props.value); if(value)return value; continue; }
    const priority=normalizePriority(props.priority) || cellPriority(props.children as ReactNode);
    if (priority) return priority;
  }
  return undefined;
}

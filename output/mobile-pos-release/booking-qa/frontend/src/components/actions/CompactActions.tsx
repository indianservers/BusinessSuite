import { Children, Fragment, cloneElement, isValidElement, useEffect, useRef, useState, type HTMLAttributes, type ReactElement, type ReactNode } from "react";
import { Ellipsis } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function flatten(children: ReactNode, parentKey = "actions"): ReactElement[] {
  return Children.toArray(children).flatMap((child, index) => {
    if (!isValidElement(child)) return [];
    // Fragment children restart React's automatic keys. Keep their ancestry so
    // promoting another primary action cannot leave duplicate/stale DOM buttons.
    const key = `${parentKey}/${child.key ?? index}`;
    return child.type === Fragment
      ? flatten((child.props as {children?: ReactNode}).children, key)
      : [cloneElement(child, {key})];
  });
}

/** Keeps original handlers, role/status conditions, forms and review dialogs intact. */
export default function CompactActions({ children, className, primaryIndex, primaryId, ...props }: HTMLAttributes<HTMLDivElement> & { primaryIndex?: number; primaryId?: string }) {
  const [open, setOpen] = useState(false);
  const details = useRef<HTMLDetailsElement>(null);
  const [position, setPosition] = useState({left: 12, top: 12, maxHeight: 400});
  useEffect(() => {
    if (!open) return;
    const close = () => {if (details.current) details.current.open = false;};
    const outside = (event: PointerEvent) => {if (event.target instanceof Node && !details.current?.contains(event.target)) close();};
    const escape = (event: KeyboardEvent) => {if (event.key === "Escape" && !event.defaultPrevented && event.target instanceof Node && details.current?.contains(event.target)) {event.preventDefault(); close(); details.current.querySelector("summary")?.focus();}};
    const scroll = (event: Event) => {if (!(event.target instanceof Node) || !details.current?.contains(event.target)) close();};
    document.addEventListener("pointerdown", outside); document.addEventListener("keydown", escape); document.addEventListener("scroll", scroll, true); window.addEventListener("resize", close);
    return () => {document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); document.removeEventListener("scroll", scroll, true); window.removeEventListener("resize", close);};
  }, [open]);
  const nodes = flatten(children).filter(action => (action.props as {available?: boolean}).available !== false);
  const fields = nodes.filter(node => typeof node.type === "string" && ["label", "input", "select", "span", "strong", "p"].includes(node.type));
  const actions = nodes.filter(node => !fields.includes(node));
  const preferredAction = actions.findIndex(action => {
    const p = action.props as {variant?: string; disabled?: boolean};
    return !p.disabled && (!p.variant || p.variant === "default");
  });
  const preferred = primaryId ? actions.findIndex(action => (action.props as {id?: string}).id === primaryId) : primaryIndex ?? (preferredAction >= 0 ? preferredAction : actions.findIndex(action => { const p = action.props as {variant?: string; disabled?: boolean}; return !p.disabled && p.variant !== "destructive"; }));
  const primary = preferred >= 0 ? actions[preferred] : undefined;
  const visible = primary ? [primary, ...actions.filter(action => action !== primary).slice(0, 2)] : actions.slice(0, 3);
  const overflow = actions.filter(action => !visible.includes(action));
  const present = (action: ReactElement, i: number, isPrimary = false) => cloneElement(action as ReactElement<{variant?: string; "data-primary"?: boolean}>, {key: action.key || i, "data-primary": isPrimary, ...(action.type === Button ? {variant: isPrimary ? "default" : (action.props as {variant?: string}).variant === "destructive" ? "destructive" : "outline"} : {})});
  return <div {...props} style={{...props.style, display: "flex"}} className={cn("suite-compact-actions flex flex-wrap items-center gap-2", className)}>
    {fields}
    {visible.map((action, i) => present(action, i, action === primary))}
    {!!overflow.length && <details ref={details} onToggle={event => {
      const expanded = event.currentTarget.open; setOpen(expanded);
      if (expanded) { const rect = event.currentTarget.querySelector("summary")!.getBoundingClientRect(); const below = innerHeight - rect.bottom - 18; const above = below < 180 && rect.top > below; const height = Math.min(448, above ? rect.top - 18 : below); setPosition({left: Math.max(8, Math.min(rect.right - 288, innerWidth - 296)), top: above ? Math.max(8, rect.top - height - 6) : rect.bottom + 6, maxHeight: Math.max(100, height)}); }
    }}>
      <summary role="button" aria-label="More actions" aria-expanded={open} className={cn(buttonVariants({variant: "outline"}), "min-h-11 cursor-pointer list-none [&::-webkit-details-marker]:hidden")}><Ellipsis size={16} aria-hidden="true"/>More</summary>
      <div aria-label="More actions" style={{position: "fixed", ...position}} className="z-[170] flex w-72 max-w-[calc(100vw-1rem)] flex-col gap-2 overflow-y-auto rounded-xl border bg-popover p-3 text-popover-foreground shadow-lg">
        {overflow.map((action, i) => present(action, i))}
      </div>
    </details>}
  </div>;
}

import { useEffect, useId, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Slot } from "@radix-ui/react-slot";

export function ActionTooltip({ content, children }: { content: string; children: ReactNode }) {
  return <Slot data-action-tooltip={content}>{children}</Slot>;
}

/** One delegated tooltip layer also covers existing native navigation and grid controls. */
export function ActionTooltipProvider() {
  const id = useId();
  const [tip, setTip] = useState<{ text: string; x: number; y: number; below: boolean } | null>(null);
  useEffect(() => {
    let anchor: HTMLElement | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let previousDescription: string | null = null;
    let nativeTitle: string | null = null;
    const clear = () => {
      clearTimeout(timer);
      if (anchor) {
        if (previousDescription) anchor.setAttribute("aria-describedby", previousDescription);
        else anchor.removeAttribute("aria-describedby");
        if (nativeTitle) anchor.setAttribute("title", nativeTitle);
      }
      anchor = null; previousDescription = null; nativeTitle = null; setTip(null);
    };
    const find = (target: EventTarget | null) => target instanceof Element ? target.closest<HTMLElement>('[data-action-tooltip],button,a[href],[role="tab"],[role="menuitem"],summary,[role="button"],input[type="checkbox"],input[type="radio"],select') : null;
    const show = (element: HTMLElement, immediate: boolean) => {
      if (element === anchor) return;
      clear();
      const fieldLabel = element instanceof HTMLInputElement || element instanceof HTMLSelectElement ? element.labels?.[0] : null;
      const labelCopy = fieldLabel?.cloneNode(true) as HTMLElement | undefined;
      labelCopy?.querySelectorAll("input,select,button").forEach(node => node.remove());
      const text = element.dataset.actionTooltip || element.getAttribute("title") || element.getAttribute("aria-label") || labelCopy?.textContent?.trim() || element.innerText?.trim().replace(/\s+/g, " ");
      if (!text || element.dataset.tooltip === "off") return;
      anchor = element;
      previousDescription = element.getAttribute("aria-describedby");
      nativeTitle = element.getAttribute("title");
      if (nativeTitle) element.removeAttribute("title");
      timer = setTimeout(() => {
        if (anchor !== element || !element.isConnected) return;
        const bounds = element.getBoundingClientRect();
        element.setAttribute("aria-describedby", [previousDescription, id].filter(Boolean).join(" "));
        setTip({ text: text.length > 240 ? `${text.slice(0, 237)}...` : text, x: Math.max(Math.min(innerWidth / 2, 156), Math.min(innerWidth - Math.min(innerWidth / 2, 156), bounds.left + bounds.width / 2)), y: bounds.top < 65 ? bounds.bottom + 8 : bounds.top - 8, below: bounds.top < 65 });
      }, immediate ? 0 : 350);
    };
    const over = (event: PointerEvent) => { if (event.pointerType === "touch") return; const element = find(event.target); if (element) show(element, false); };
    const out = (event: PointerEvent) => { if (event.relatedTarget instanceof Element && (anchor?.contains(event.relatedTarget) || event.relatedTarget.closest('[data-action-tooltip-content]'))) return; clearTimeout(timer); timer = setTimeout(clear, 120); };
    const focus = (event: FocusEvent) => { const element = find(event.target); if (element?.matches(":focus-visible")) show(element, true); };
    const blur = (event: FocusEvent) => { if (!(event.relatedTarget instanceof Node) || !anchor?.contains(event.relatedTarget)) clear(); };
    const key = (event: KeyboardEvent) => { if (event.key === "Escape") clear(); };
    const keep = () => clearTimeout(timer);
    document.addEventListener("pointerover", over);
    document.addEventListener("pointerout", out);
    document.addEventListener("focusin", focus);
    document.addEventListener("focusout", blur);
    document.addEventListener("keydown", key);
    document.addEventListener("pointerdown", clear);
    document.addEventListener("scroll", clear, true);
    const tooltipOver = (event: PointerEvent) => { if (event.target instanceof Element && event.target.closest('[data-action-tooltip-content]')) keep(); };
    document.addEventListener("pointerover", tooltipOver);
    return () => {
      clear();
      document.removeEventListener("pointerover", over);document.removeEventListener("pointerover", tooltipOver);
      document.removeEventListener("pointerout", out);document.removeEventListener("focusin", focus);document.removeEventListener("focusout", blur);
      document.removeEventListener("keydown", key);document.removeEventListener("pointerdown", clear);document.removeEventListener("scroll", clear, true);
    };
  }, [id]);
  return tip ? createPortal(<div id={id} role="tooltip" data-action-tooltip-content className="suite-action-tooltip" style={{ left: tip.x, top: tip.y, transform: `translate(-50%, ${tip.below ? "0" : "-100%"})` }}>{tip.text}</div>, document.body) : null;
}

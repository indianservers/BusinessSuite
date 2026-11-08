import { useEffect } from "react";

/** Use the active editor's existing save action, preserving its validation. */
export default function SaveShortcut() {
  useEffect(() => {
    const pending=new Map<HTMLElement,ReturnType<typeof setTimeout>>();
    const cancelInline=(event:Event)=>{const field=event.target as HTMLElement;const timer=pending.get(field);if(timer)clearTimeout(timer);pending.delete(field);};
    const saveInline=(event:Event)=>{
      const field=event.target as HTMLInputElement;
      if(!field.matches('[data-autosave-blur]'))return;
      cancelInline(event);
      pending.set(field,setTimeout(()=>{pending.delete(field);if(field.isConnected&&!field.disabled&&field.checkValidity())field.blur();},1400));
    };
    const save = (event: KeyboardEvent) => {
      if (event.defaultPrevented || !(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "s") return;
      // Let editor-specific shortcuts run before this fallback.
      event.preventDefault();
      if (event.repeat) return;
      queueMicrotask(() => {
        const focused = document.activeElement;
        if(focused instanceof HTMLInputElement&&focused.matches('[data-autosave-blur]')){if(focused.checkValidity())focused.blur();return;}
        const dialogs = [...document.querySelectorAll<HTMLElement>('[role="dialog"]')].filter(el => el.getClientRects().length);
        const scope = focused?.closest('[role="dialog"]') || dialogs[dialogs.length - 1] || focused?.closest("form") || document.querySelector("main") || document.body;
        const buttons = [...scope.querySelectorAll<HTMLButtonElement>('button')].filter(button => !button.disabled && button.getClientRects().length);
        const safe = buttons.filter(button=>! /\b(delete|discard|archive|approve|send|publish|post|remove)\b/i.test(button.textContent||""));
        const button = safe.find(button => button.hasAttribute("data-save-action"))
          || safe.find(button => /^(save|update)\b/i.test((button.textContent || "").trim())&&!/\b(draft|view|filter|template)\b/i.test(button.textContent||""))
          || safe.find(button=>button.type==="submit"&&/^(create|add|register)\b/i.test((button.textContent||"").trim()))
          || safe.find(button=>/^save draft$/i.test((button.textContent||"").trim()));
        button?.click();
      });
    };
    // React editor handlers and capture listeners can claim the shortcut first.
    const deferred = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      save(event);
    };
    window.addEventListener("keydown", deferred);
    document.addEventListener("input",saveInline);
    document.addEventListener("focusout",cancelInline);
    return () => {window.removeEventListener("keydown", deferred);document.removeEventListener("input",saveInline);document.removeEventListener("focusout",cancelInline);pending.forEach(clearTimeout);};
  }, []);
  return null;
}

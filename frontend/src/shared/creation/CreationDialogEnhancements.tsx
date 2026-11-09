import { useEffect, useRef, useState } from "react";
import * as Alert from "@radix-ui/react-alert-dialog";
import { Button } from "@/components/ui/button";

/** Enhance existing creation portals without replacing their forms, drafts, callbacks or focus scopes. */
export function CreationDialogEnhancements() {
  const [pending, setPending] = useState<{ dialog: HTMLElement; resume: () => void }>();
  const bypass = useRef(false);
  useEffect(() => {
    function inspect() {
      const all = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"]')).filter(dialog => dialog.getAttribute('data-state') !== 'closed');
      if (all.some(dialog => dialog.hasAttribute('data-smart-create') || dialog.hasAttribute('data-smart-create-enhanced'))) all.forEach((dialog, index) => {
        dialog.style.zIndex = String(170 + index * 4);
        const overlay = dialog.previousElementSibling as HTMLElement | null;
        if (overlay && /overlay|inset-0/i.test(overlay.className)) { overlay.style.zIndex = String(169 + index * 4); overlay.dataset.smartCreateOverlay = 'true'; }
      });
      document.querySelectorAll<HTMLElement>('[role="dialog"]:not([data-smart-create]):not([data-smart-create-enhanced]):not([data-navigation-sheet])').forEach(dialog => {
        const heading = dialog.querySelector('h1,h2,h3,[role="heading"],[data-dialog-title]')?.textContent?.trim() || dialog.getAttribute('aria-label') || '';
        if (!/^(?:quick\s+)?(create|new|add|invite|schedule|log|apply|request|upload)\b/i.test(heading)) return;
        dialog.dataset.smartCreateEnhanced = 'true';
        dialog.dataset.smartCreateSize = dialog.querySelectorAll('input,select,textarea').length <= 3 ? 'compact' : 'standard';
      });
    }
    const observer = new MutationObserver(inspect); observer.observe(document.body, { childList: true, subtree: true }); inspect();
    const dirty = (event: Event) => { const dialog = (event.target as Element)?.closest<HTMLElement>('[data-smart-create-enhanced]'); if (dialog) dialog.dataset.smartCreateDirty = 'true'; };
    function topDialog() { const dialogs = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"]')).filter(dialog => dialog.getAttribute('data-state') !== 'closed' && dialog.getClientRects().length > 0); const top = dialogs[dialogs.length - 1]; return top?.hasAttribute('data-smart-create-enhanced') ? top : undefined; }
    function guarded(dialog: HTMLElement | undefined, event: Event, resume: () => void) {
      if (!dialog || bypass.current) return false;
      const saving = !!dialog.querySelector('form[aria-busy="true"],[data-save-action][aria-busy="true"]') || Array.from(dialog.querySelectorAll('button:disabled')).some(button => /^(creating|saving|uploading|processing)\b/i.test(button.textContent?.trim() || ''));
      if (dialog.dataset.smartCreateDirty !== 'true' && !saving) return false;
      event.preventDefault(); event.stopImmediatePropagation();
      if (!saving) setPending({ dialog, resume });
      return true;
    }
    function click(event: MouseEvent) {
      const button = (event.target as Element)?.closest<HTMLButtonElement>('button');
      const dialog = button?.closest<HTMLElement>('[data-smart-create-enhanced]');
      if (!button || !dialog) return;
      const label = button.getAttribute('aria-label') || button.textContent?.trim() || '';
      if (/^(close|cancel|discard|back)(\b|$)/i.test(label) && !/previous|back step/i.test(label)) guarded(dialog, event, () => button.click());
    }
    function keyboard(event: KeyboardEvent) {
      if (event.key !== 'Escape' || document.querySelector('[role="alertdialog"]')) return;
      if (document.querySelector('[role="listbox"],[role="menu"],[data-record-picker][aria-expanded="true"]')) return;
      guarded(topDialog(), event, () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })));
    }
    function outside(event: PointerEvent) {
      const target = event.target as HTMLElement;
      if (document.querySelector('[role="alertdialog"]') || target.closest('[role="dialog"],[role="menu"],[role="listbox"]')) return;
      if (/overlay|inset-0/i.test(typeof target.className === 'string' ? target.className : '')) guarded(topDialog(), event, () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })));
    }
    function unload(event: BeforeUnloadEvent) { if (topDialog()?.dataset.smartCreateDirty === 'true') { event.preventDefault(); event.returnValue = ''; } }
    function submitShortcut(event: KeyboardEvent) {
      if (event.defaultPrevented || event.repeat || !(event.ctrlKey || event.metaKey) || event.key !== 'Enter') return;
      const dialog = (event.target as Element).closest<HTMLElement>('[data-smart-create-enhanced]');
      if (!dialog || dialog !== topDialog()) return;
      const form = (event.target as Element).closest('form') || dialog.querySelector('form');
      if (dialog.querySelector('form[aria-busy="true"],[data-save-action][aria-busy="true"]')) return;
      if (form) { event.preventDefault(); form.requestSubmit(); return; }
      const buttons = Array.from(dialog.querySelectorAll<HTMLButtonElement>('button')).filter(button => !button.disabled);
      const primary = buttons.find(button => button.hasAttribute('data-save-action')) || buttons.find(button => /^(create|save|submit|register)\b/i.test(button.textContent?.trim() || '') && !/draft|template|field|folder/i.test(button.textContent || ''));
      if (primary) { event.preventDefault(); primary.click(); }
    }
    document.addEventListener('input', dirty, true); document.addEventListener('change', dirty, true);
    document.addEventListener('click', click, true); document.addEventListener('keydown', keyboard, true);
    document.addEventListener('pointerdown', outside, true); window.addEventListener('beforeunload', unload); window.addEventListener('keydown', submitShortcut);
    return () => { observer.disconnect(); document.removeEventListener('input', dirty, true); document.removeEventListener('change', dirty, true); document.removeEventListener('click', click, true); document.removeEventListener('keydown', keyboard, true); document.removeEventListener('pointerdown', outside, true); window.removeEventListener('beforeunload', unload); window.removeEventListener('keydown', submitShortcut); };
  }, []);
  const draft = pending && Array.from(pending.dialog.querySelectorAll<HTMLButtonElement>('button')).find(button => /^save (as )?draft$/i.test(button.textContent?.trim() || '') && !button.disabled);
  return <Alert.Root open={!!pending} onOpenChange={open => { if (!open) setPending(undefined); }}><Alert.Portal><Alert.Overlay className="smart-discard-overlay"/><Alert.Content className="smart-discard-window"><Alert.Title>Discard changes?</Alert.Title><Alert.Description>Your unsaved information will be lost.</Alert.Description><div><Alert.Cancel asChild><Button variant="outline">Continue Editing</Button></Alert.Cancel>{draft && <Button variant="outline" onClick={() => { setPending(undefined); draft.click(); }}>Save Draft</Button>}<Alert.Action asChild><Button variant="destructive" onClick={() => {
    const action = pending; setPending(undefined); if (!action) return;
    action.dialog.dataset.smartCreateDirty = 'false'; bypass.current = true;
    try { action.resume(); } finally { bypass.current = false; }
  }}>Discard Changes</Button></Alert.Action></div></Alert.Content></Alert.Portal></Alert.Root>;
}

import { useLocation } from "react-router-dom";
import { useSmartCreation } from "./SmartCreationProvider";
import { creationDefinition } from "./registry";
import { Children, cloneElement, isValidElement, useCallback, useContext, useEffect, useRef, useState, type ReactElement, type ReactNode } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { recordSavedEvent, type RecordSaved } from "@/lib/record-changes";
import { SmartCreateModal } from "./SmartCreateModal";
import { CreationSurfaceContext } from "./CreationSurfaceContext";

function plainText(node: ReactNode): string {
  return Children.toArray(node).map(child => typeof child === 'string' || typeof child === 'number' ? String(child) : isValidElement<{ children?: ReactNode }>(child) ? plainText(child.props.children) : '').join(' ').replace(/\s+/g, ' ').trim();
}

/** Opt-in adapter for audited inline create cards. Their state, validation and API handlers stay with their owner. */
export function SmartCreateSection({ title, children, size = "standard", autoOpen = false, onClose, trigger }: { title: ReactNode; children: ReactNode; size?: "compact" | "standard" | "large"; autoOpen?: boolean; onClose?: () => void; trigger?: ReactElement<{ onClick?: () => void }> }) {
  const inside = useContext(CreationSurfaceContext);
  const creation = useSmartCreation();
  const location = useLocation();
  const destination = `${location.pathname}${location.search}#new-record`;
  const canonical = creationDefinition(destination);
  const canonicalSize = canonical?.size || size;
  const bookmarked = Children.toArray(children).some(child => isValidElement<{ id?: string }>(child) && child.props.id === 'new-record') && (window.location.hash === '#new-record' || /\/(new|create)$/.test(window.location.pathname));
  const [open, setOpen] = useState(autoOpen || bookmarked);
  useEffect(() => { if (autoOpen) setOpen(true); }, [autoOpen]);
  const [adaptiveSize, setAdaptiveSize] = useState(canonicalSize);
  const body = useRef<HTMLDivElement | null>(null), submitted = useRef(false);
  const [element, setElement] = useState<HTMLDivElement | null>(null);
  const attach = useCallback((node: HTMLDivElement | null) => { body.current = node; setElement(node); }, []);
  const label = plainText(title);
  function close() { submitted.current = false; setOpen(false); onClose?.(); }
  const latestClose = useRef(close); latestClose.current = close;
  useEffect(() => {
    if (!open || inside || !element) return;
    const inspect = () => {
      const count = body.current?.querySelectorAll('input:not([type="hidden"]),textarea,select,[contenteditable="true"]').length || 0;
      setAdaptiveSize(canonical?.size || (size === 'large' || count > 10 ? 'large' : size === 'standard' || count > 3 ? 'standard' : size));
    };
    const observer = new MutationObserver(inspect); observer.observe(element, { childList: true, subtree: true }); inspect();
    return () => observer.disconnect();
  }, [open, inside, size, element, canonical?.size]);
  useEffect(() => {
    if (inside || !open) return;
    const saved = (event: Event) => {
      const change = (event as CustomEvent<RecordSaved>).detail;
      const dialogs = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"]')).filter(dialog => dialog.getClientRects().length > 0);
      if (!submitted.current || dialogs[dialogs.length - 1] !== body.current?.closest('[role="dialog"]') || change.method.toLowerCase() !== 'post' || !(change.record?.id || (change.record?.task as { id?: number } | undefined)?.id)) return;
      latestClose.current();
    };
    window.addEventListener(recordSavedEvent, saved); return () => window.removeEventListener(recordSavedEvent, saved);
  }, [inside, open]);
  if (inside) return <>{children}</>;
  const launch = () => { if (!canonical || !creation?.open(destination, onClose)) setOpen(true); };
  return <>{!open && (trigger ? cloneElement(trigger, { onClick: launch }) : <div className="smart-create-section"><div><strong>{label}</strong><p>Add a new record without leaving this page.</p></div><Button type="button" onClick={launch}><Plus size={16}/>{label}</Button></div>)}{open && <SmartCreateModal definition={canonical || { entity: label, title: label, presentation: 'page', size: adaptiveSize }} onClose={close}><div ref={attach} onSubmitCapture={event => { if (body.current?.contains(event.target as Node)) submitted.current = true; }} onClickCapture={event => { const button = (event.target as Element).closest('button'); if (button && body.current?.contains(button) && /^(create|save|register|submit|start|add|record|request|apply|generate|publish)\b/i.test(button.textContent?.trim() || '')) submitted.current = true; }} onInputCapture={() => { submitted.current = false; }}>{children}</div></SmartCreateModal>}</>;
}

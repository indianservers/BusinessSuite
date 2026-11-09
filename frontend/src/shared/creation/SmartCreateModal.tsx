import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import * as Alert from "@radix-ui/react-alert-dialog";
import { CheckCircle2, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { CreationDefinition } from "./registry";
import "./smart-creation.css";
import { CreationSurfaceContext } from "./CreationSurfaceContext";

export function SmartCreateModal({ definition, children, onClose, busy = false, savedRevision = 0, closeRequestRevision = 0, loading = false, mobileSheet = false, returnFocus }: { definition: CreationDefinition; children: ReactNode; onClose: () => void; busy?: boolean; savedRevision?: number; closeRequestRevision?: number; loading?: boolean; mobileSheet?: boolean; returnFocus?: HTMLElement | null }) {
  const content = useRef<HTMLDivElement | null>(null);
  const [element, setElement] = useState<HTMLDivElement | null>(null);
  const attach = useCallback((node: HTMLDivElement | null) => { content.current = node; setElement(node); }, []);
  const [dirty, setDirty] = useState(false), [confirm, setConfirm] = useState(false);
  const [action, setAction] = useState<{ label: string; disabled: boolean; previous?: { disabled: boolean } }>();
  const primary = useRef<HTMLButtonElement>();
  const previous = useRef<HTMLButtonElement>();
  const submitting = useRef(false);
  const submitFromClick = useRef(false);
  useEffect(() => { setDirty(false); submitting.current = false; }, [savedRevision]);
  useEffect(() => {
    if (!dirty) return;
    const unload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', unload); return () => window.removeEventListener('beforeunload', unload);
  }, [dirty]);
  useEffect(() => {
    const inspect = () => {
      const buttons = Array.from(content.current?.querySelectorAll<HTMLButtonElement>('button') || []).filter(button => !button.closest('[data-smart-create-footer]'));
      const button = buttons.find(button => button.hasAttribute('data-save-action')) || buttons.find(button => button.type === 'submit' && button.form && /^(create|save|submit|raise|register|invite|schedule|request|apply|generate|publish|record|assign)\b/i.test(button.textContent?.trim() || '')) || buttons.find(button => /^(create|save|submit|raise)\b/i.test(button.textContent?.trim() || '') && !/draft|subtask|checklist|template|field|folder/i.test(button.textContent || '')) || buttons.find(button => /^(next|continue)$/i.test(button.textContent?.trim() || '')) || buttons.find(button => /^(invite|schedule|request|apply|generate|publish|record|assign)\b/i.test(button.textContent?.trim() || '')) || buttons.find(button => /^add\b/i.test(button.textContent?.trim() || '') && (button.type === 'submit' && !!button.form || !/another|more|existing|line|row|subtask|checklist|template|field|folder|lesson|question|section|condition|filter/i.test(button.textContent || ''))) || buttons.find(button => /^save (as )?draft$/i.test(button.textContent?.trim() || ''));
      primary.current = button;
      if (button && !button.disabled) submitting.current = false;
      previous.current = definition.entity === 'employee' ? buttons.find(button => /^previous$/i.test(button.textContent?.trim() || '')) : undefined;
      const next = button ? { label: button.textContent!.trim(), disabled: button.disabled, previous: previous.current ? { disabled: previous.current.disabled } : undefined } : undefined;
      setAction(current => JSON.stringify(current) === JSON.stringify(next) ? current : next);
    };
    const observer = new MutationObserver(inspect);
    if (element) observer.observe(element, { childList: true, subtree: true, attributes: true, attributeFilter: ['disabled', 'aria-busy'] });
    inspect(); return () => observer.disconnect();
  }, [element, definition.entity]);
  function requestClose() {
    const saving = busy || submitting.current && !!primary.current?.disabled || !!content.current?.querySelector('form[aria-busy="true"],[data-save-action][aria-busy="true"]') || Array.from(content.current?.querySelectorAll<HTMLButtonElement>('button:disabled') || []).some(button => /^(creating|saving|uploading|processing|submitting)\b/i.test(button.textContent?.trim() || ""));
    if (saving) return;
    if (dirty) setConfirm(true); else onClose();
  }
  const latestCloseRequest = useRef(requestClose); latestCloseRequest.current = requestClose;
  useEffect(() => { if (closeRequestRevision) latestCloseRequest.current(); }, [closeRequestRevision]);
  const draftButton = confirm ? Array.from(content.current?.querySelectorAll<HTMLButtonElement>('button') || []).find(button => /^save (as )?draft$/i.test(button.textContent?.trim() || '') && !button.disabled) : undefined;
  return <><Dialog.Root open onOpenChange={open => { if (!open) requestClose(); }}><Dialog.Portal>
    <Dialog.Overlay className="smart-create-overlay" />
    <Dialog.Content ref={attach} className={`smart-create-window smart-create-${definition.size}${definition.entity === "task" ? " smart-create-task" : ""}${mobileSheet ? " smart-create-phone-sheet" : ""}`} aria-describedby="smart-create-description" data-smart-create="true" data-smart-create-loading={loading ? "true" : undefined} onCloseAutoFocus={event => { if(returnFocus?.isConnected) { event.preventDefault(); returnFocus.focus(); } }} onInputCapture={() => { submitting.current = false; submitFromClick.current = false; setDirty(true); }} onChangeCapture={() => { submitting.current = false; submitFromClick.current = false; setDirty(true); }} onSubmitCapture={event => {
      if (!content.current?.contains(event.target as Node)) return;
      if (submitting.current && !submitFromClick.current) { event.preventDefault(); event.stopPropagation(); return; }
      submitFromClick.current = false; submitting.current = true;
    }} onClickCapture={event => {
      const button = (event.target as Element).closest('button');
      if (button && button === primary.current) {
        if (submitting.current) { event.preventDefault(); event.stopPropagation(); return; }
        submitting.current = true;
        submitFromClick.current = button.type === 'submit' && !!button.form;
      }
      if (button?.closest('.smart-create-body') && /^(cancel|close)$/i.test(button.textContent?.trim() || '')) { event.preventDefault(); event.stopPropagation(); requestClose(); }
    }} onPointerDownOutside={event => event.preventDefault()} onKeyDown={event => {
      if (event.defaultPrevented || event.repeat) return;
      if (!content.current?.contains(event.target as Node)) return;
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && !busy && !submitting.current && !primary.current?.disabled) {
        const form = (event.target as HTMLElement).closest('form') || content.current?.querySelector('form');
        if (form && !form.querySelector('form[aria-busy="true"],[data-save-action][aria-busy="true"]')) { event.preventDefault(); form.requestSubmit(); }
        else if (!form && primary.current && !primary.current.disabled) { event.preventDefault(); primary.current.click(); }
      }
    }}>
      <header className="smart-create-header"><span className="smart-create-emblem"><Sparkles size={21}/></span><div><Dialog.Title>{definition.title}</Dialog.Title><Dialog.Description id="smart-create-description">Create without leaving your current work.</Dialog.Description></div><button type="button" aria-label="Close creation window" onClick={requestClose} disabled={busy}><X size={20}/></button></header>
      <div className="smart-create-layout">{definition.size === "large" && definition.entity !== "task" && <aside className="smart-create-sidebar"><span className="smart-create-eyebrow">BUSINESS SUITE</span><h2>Bring your next<br/>idea to life.</h2><p>Your current page stays right here. Complete the details, review your choices, and create when you’re ready.</p><span><CheckCircle2 size={16}/> Clear details, one step at a time</span><span><CheckCircle2 size={16}/> Connected to your current work</span><span><CheckCircle2 size={16}/> Ready when you save</span></aside>}<div className="smart-create-body"><CreationSurfaceContext.Provider value={true}>{children}</CreationSurfaceContext.Provider></div></div>
      <footer className="smart-create-footer" data-smart-create-footer><span>Review the details before creating.</span><Button type="button" variant="outline" disabled={busy} onClick={requestClose}>Cancel</Button>{action?.previous && <Button type="button" variant="outline" disabled={busy || action.previous.disabled} onClick={() => previous.current?.click()}>Previous</Button>}{action && <Button type="button" disabled={busy || action.disabled} onClick={() => primary.current?.click()}>{action.label}</Button>}</footer>
    </Dialog.Content>
  </Dialog.Portal></Dialog.Root>
  <Alert.Root open={confirm} onOpenChange={setConfirm}><Alert.Portal><Alert.Overlay className="smart-discard-overlay"/><Alert.Content className="smart-discard-window"><Alert.Title>Discard changes?</Alert.Title><Alert.Description>Your unsaved information will be lost. Drafts explicitly saved by the form remain available.</Alert.Description><div><Alert.Cancel asChild><Button variant="outline">Continue Editing</Button></Alert.Cancel>{draftButton && <Button variant="outline" onClick={() => { setConfirm(false); draftButton.click(); }}>Save Draft</Button>}<Alert.Action asChild><Button variant="destructive" onClick={onClose}>Discard Changes</Button></Alert.Action></div></Alert.Content></Alert.Portal></Alert.Root></>;
}

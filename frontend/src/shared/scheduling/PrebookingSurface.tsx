import { useEffect, useRef, useState, type ReactNode } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { FocusScope } from '@radix-ui/react-focus-scope';

/** Keep drafts mounted while closed. On phones the editor becomes a focus-trapped drawer. */
export default function PrebookingSurface({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 760px)').matches);
  const trigger = useRef<HTMLElement | null>(null);
  const content = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const media = window.matchMedia('(max-width: 760px)');
    const changed = () => setMobile(media.matches);
    media.addEventListener('change', changed);
    return () => media.removeEventListener('change', changed);
  }, []);
  useEffect(() => {
    if (!mobile || !open) return;
    trigger.current = document.activeElement as HTMLElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    document.body.classList.add('prebooking-drawer-active');
    const siblings: {node:HTMLElement;inert:boolean}[] = [];
    let node: HTMLElement | null = content.current;
    while (node && node !== document.body) {
      const parent: HTMLElement | null = node.parentElement;
      if (!parent) break;
      for (const sibling of Array.from(parent.children)) if (sibling !== node && sibling instanceof HTMLElement) { siblings.push({node:sibling,inert:sibling.inert}); sibling.inert=true; }
      node = parent;
    }
    const frame = requestAnimationFrame(() => content.current?.querySelector<HTMLElement>('input:not(:disabled), button')?.focus());
    return () => { cancelAnimationFrame(frame); document.body.style.overflow = overflow; document.body.classList.remove('prebooking-drawer-active'); siblings.forEach(item=>{item.node.inert=item.inert;}); requestAnimationFrame(()=>trigger.current?.focus()); };
  }, [mobile, open]);
  return <Dialog.Root modal={false} open={open} onOpenChange={next => { if (!next) onClose(); }}>
    {mobile && open && <div aria-hidden="true" className="prebooking-drawer-overlay"/>}
    <Dialog.Content ref={content} forceMount role={mobile ? 'dialog' : 'region'} aria-modal={mobile && open} className={mobile ? 'prebooking-drawer' : 'prebooking-surface'} style={!open ? { display: 'none' } : undefined}
      onOpenAutoFocus={event => event.preventDefault()}
      onCloseAutoFocus={event => event.preventDefault()}
      onInteractOutside={event => event.preventDefault()}
      onEscapeKeyDown={event => { if (document.activeElement?.matches('[role=combobox][aria-expanded=true]')) event.preventDefault(); }}>
      <Dialog.Title className="sr-only">Prebooking editor</Dialog.Title><Dialog.Description className="sr-only">Select the customer, service and an available employee and time. Closing preserves your draft.</Dialog.Description>
      <FocusScope asChild trapped={mobile && open} loop={mobile && open}><div className={mobile ? 'prebooking-drawer-body' : 'contents'}>{children}</div></FocusScope>
    </Dialog.Content>
  </Dialog.Root>;
}

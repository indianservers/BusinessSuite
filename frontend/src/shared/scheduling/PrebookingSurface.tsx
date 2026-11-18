import { useEffect, useRef, useState, type ReactNode } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { CalendarDays, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { FocusScope } from '@radix-ui/react-focus-scope';

/** Keep drafts mounted while closed. On phones the editor becomes a focus-trapped drawer. */
export default function PrebookingSurface({ open, onClose, children, desktopModal = false }: { open: boolean; onClose: () => void; children: ReactNode; desktopModal?: boolean }) {
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 767px)').matches);
  const [canExpand,setCanExpand]=useState(()=>window.matchMedia('(min-width: 1151px)').matches);
  const [showShortcuts,setShowShortcuts]=useState(false);
  const [expanded,setExpanded]=useState(false);
  const trigger = useRef<HTMLElement | null>(null);
  const content = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const media = window.matchMedia('(max-width: 767px)');
    const changed = () => {setMobile(media.matches);setCanExpand(window.matchMedia('(min-width: 1151px)').matches);};
    window.addEventListener('resize',changed);
    media.addEventListener('change', changed);
    return () => {media.removeEventListener('change', changed);window.removeEventListener('resize',changed);};
  }, []);
  useEffect(()=>{
    const viewport=window.visualViewport;if(!mobile||!viewport)return;
    let observedField:HTMLElement|undefined;
    const observer=new ResizeObserver(()=>focus());
    const focus=()=>requestAnimationFrame(()=>{
      const field=document.activeElement,root=content.current;if(!(field instanceof HTMLElement)||!root?.contains(field))return;
      if(observedField!==field){if(observedField)observer.unobserve(observedField);observedField=field;observer.observe(field);}
      const stickyFooter=root.querySelector<HTMLElement>('.prebooking-footer');if(stickyFooter)observer.observe(stickyFooter);
      const bounds=root.getBoundingClientRect(),rect=field.getBoundingClientRect();
      const footer=root.querySelector<HTMLElement>('.prebooking-footer')?.getBoundingClientRect().height || 0;
      const top=bounds.top+65,bottom=bounds.bottom-footer-20;
      if(rect.bottom>bottom)root.scrollTop+=rect.bottom-bottom;
      if(rect.top<top)root.scrollTop-=top-rect.top;
    });
    const resize=()=>{content.current?.style.setProperty('--prebooking-viewport-height',`${viewport.height}px`);content.current?.style.setProperty('--prebooking-viewport-top',`${viewport.offsetTop}px`);focus();};
    resize();viewport.addEventListener('resize',resize);viewport.addEventListener('scroll',resize);content.current?.addEventListener('focusin',focus);
    const element=content.current;return()=>{viewport.removeEventListener('resize',resize);viewport.removeEventListener('scroll',resize);element?.removeEventListener('focusin',focus);observer.disconnect();};
  },[mobile]);
  useEffect(() => {
    if (!(mobile || desktopModal) || !open) return;
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
  }, [mobile, desktopModal, open]);
  useEffect(()=>{
    const listener=(event:KeyboardEvent)=>{if(!open || !event.altKey || !event.shiftKey)return;const keys:Record<string,string>={c:'customer',s:'service',t:'schedule',r:'resources'};const key=keys[event.key.toLowerCase()];if(!key)return;const section=content.current?.querySelector<HTMLElement>(`[data-booking-section="${key}"]`);if(!section)return;event.preventDefault();if(section.querySelector('[data-section-body][hidden]'))section.querySelector<HTMLButtonElement>('.prebooking-section-heading button')?.click();requestAnimationFrame(()=>section.querySelector<HTMLElement>('input:not(:disabled),select:not(:disabled),button')?.focus());};
    window.addEventListener('keydown',listener);return()=>window.removeEventListener('keydown',listener);
  },[open]);
  return <Dialog.Root modal={false} open={open} onOpenChange={next => { if (!next) onClose(); }}>
    {(mobile || desktopModal) && open && <div aria-hidden="true" className="prebooking-drawer-overlay"/>}
    <Dialog.Content ref={content} data-expanded={expanded && canExpand} forceMount role={mobile || desktopModal ? 'dialog' : 'region'} aria-modal={(mobile || desktopModal) && open} className={mobile ? 'prebooking-drawer' : desktopModal ? 'prebooking-surface prebooking-reference-modal' : 'prebooking-surface'} style={!open ? { display: 'none' } : undefined}
      onOpenAutoFocus={event => event.preventDefault()}
      onCloseAutoFocus={event => event.preventDefault()}
      onInteractOutside={event => event.preventDefault()}
      onEscapeKeyDown={event => { if (document.activeElement?.matches('[role=combobox][aria-expanded=true]')) event.preventDefault(); }}>
      <Dialog.Title className="sr-only">Prebooking editor</Dialog.Title><Dialog.Description className="sr-only">Select the customer, service and an available employee and time. Closing preserves your draft.</Dialog.Description>
      <FocusScope asChild trapped={(mobile || desktopModal) && open} loop={(mobile || desktopModal) && open}><div className={mobile ? 'prebooking-drawer-body' : 'contents'}>{(desktopModal || mobile) && <header className="prebooking-reference-header"><CalendarDays size={25}/><div><strong>New appointment</strong><p>Choose a service. Find a time. Confirm.</p></div><Button type="button" variant="ghost" aria-label="Close appointment" onClick={onClose}><X size={22}/></Button></header>}{canExpand && !desktopModal && <Button type="button" variant="ghost" className="prebooking-expand" aria-pressed={expanded} onClick={()=>setExpanded(v=>!v)}>{expanded?'Compact panel':'Expand panel'}</Button>}<button className="prebooking-shortcuts" type="button" aria-expanded={showShortcuts} onClick={()=>setShowShortcuts(v=>!v)}>Keyboard shortcuts</button>{showShortcuts&&<p>Alt+Shift+C: Customer · Alt+Shift+S: Service · Alt+Shift+T: Schedule · Alt+Shift+R: Resources. Alt+Shift+B opens the booking panel. Shortcuts never submit a booking.</p>}{children}</div></FocusScope>
    </Dialog.Content>
  </Dialog.Root>;
}

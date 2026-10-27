import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation } from "react-router-dom";
import { available, collectPageContext, type PageContextAction } from "@/lib/page-context-actions";

type Menu = { x: number; y: number; title: string; actions: PageContextAction[]; origin: HTMLElement };
/** Shared across shells; existing record menus take precedence via preventDefault. */
export default function PageContextMenu() {
  const location = useLocation();
  const [menu, setMenu] = useState<Menu | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const restore = useRef<HTMLElement | null>(null);
  useEffect(() => { setMenu(null); }, [location.key]);
  useEffect(() => {
    function open(event: MouseEvent) {
      if (event.defaultPrevented || !(event.target instanceof Element)) return;
      const target = event.target instanceof HTMLElement ? event.target : event.target.parentElement;
      if (!target) return;
      const root = target.closest<HTMLElement>('[role="dialog"],main,.ws-main');
      if (!root) return;
      const context = collectPageContext(target, root);
      if (!context) return;
      event.preventDefault();
      restore.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      setMenu({ ...context, x: event.clientX, y: event.clientY, origin: target });
    }
    function keyboard(event: KeyboardEvent) {
      if (event.defaultPrevented || !(event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10'))) return;
      if (!(event.target instanceof HTMLElement)) return;
      const rect = event.target.getBoundingClientRect();
      const context = new MouseEvent('contextmenu', { bubbles: true, cancelable: true, clientX: rect.left + 12, clientY: rect.top + 12, button: 2 });
      event.target.dispatchEvent(context);
      if (context.defaultPrevented) event.preventDefault();
    }
    document.addEventListener('contextmenu', open);
    document.addEventListener('keydown', keyboard);
    return () => { document.removeEventListener('contextmenu', open); document.removeEventListener('keydown', keyboard); };
  }, []);
  useLayoutEffect(() => {
    if (!menu || !ref.current) return;
    const node = ref.current;
    const rect = node.getBoundingClientRect();
    node.style.left = `${Math.max(8, Math.min(menu.x, window.innerWidth - rect.width - 8))}px`;
    node.style.top = `${Math.max(8, Math.min(menu.y, window.innerHeight - rect.height - 8))}px`;
    node.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus();
  }, [menu]);
  useEffect(() => {
    if (!menu) return;
    const dismiss = () => setMenu(null);
    const outside = (e: PointerEvent) => { if (!ref.current?.contains(e.target as Node)) dismiss(); };
    const escape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); dismiss(); restore.current?.focus(); }
      if (e.key === 'Tab') dismiss();
    };
    document.addEventListener('pointerdown', outside, true);
    document.addEventListener('keydown', escape);
    window.addEventListener('resize', dismiss);
    window.addEventListener('blur', dismiss);
    const onScroll = (event: Event) => { if (!ref.current?.contains(event.target as Node)) dismiss(); };
    document.addEventListener('scroll', onScroll, true);
    return () => { document.removeEventListener('pointerdown', outside, true); document.removeEventListener('keydown', escape); window.removeEventListener('resize', dismiss); window.removeEventListener('blur', dismiss); document.removeEventListener('scroll', onScroll, true); };
  }, [menu]);
  if (!menu) return null;
  return createPortal(<div ref={ref} role="menu" aria-label={`${menu.title} actions`} data-page-context-menu className="fixed z-[200] max-h-[min(70vh,32rem)] w-72 max-w-[calc(100vw-16px)] overflow-y-auto rounded-lg border bg-popover p-1 text-popover-foreground shadow-xl" style={{ left: menu.x, top: menu.y }} onContextMenu={e => e.preventDefault()} onKeyDown={e => {
    const items = Array.from(ref.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]') || []);
    const index = items.indexOf(document.activeElement as HTMLButtonElement);
    let next: number | undefined;
    if (e.key === 'ArrowDown') next = (index + 1) % items.length;
    if (e.key === 'ArrowUp') next = (index - 1 + items.length) % items.length;
    if (e.key === 'Home') next = 0;
    if (e.key === 'End') next = items.length - 1;
    if (next !== undefined) { e.preventDefault(); items[next]?.focus(); }
  }}>
    <div className="border-b px-3 py-2 text-xs font-semibold text-muted-foreground">{menu.title}</div>
    {menu.actions.map((action, index) => <button key={`${index}:${action.label}`} type="button" role="menuitem" tabIndex={-1} className="flex w-full rounded px-3 py-2 text-left text-sm outline-none hover:bg-accent focus:bg-accent" onClick={() => {
      setMenu(null);
      if (available(action.source)) { action.source.focus(); action.run(); }
    }}>{action.label}</button>)}
  </div>, document.body);
}

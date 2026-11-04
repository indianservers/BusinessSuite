import { useEffect, useRef, type ReactNode } from "react";
import { Maximize2, X } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useMobile } from "@/components/mobile/useMobile";

export default function GridRecordPane({ title, children, close, expand }: { title: string; children: ReactNode; close: () => void; expand?: () => void }) {
  const mobile = useMobile();
  const heading = useRef<HTMLHeadingElement>(null);
  const closeRef = useRef(close);
  closeRef.current = close;
  useEffect(() => {
    if (mobile) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    heading.current?.focus();
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !document.querySelector('[role="dialog"]')) { event.stopPropagation(); closeRef.current(); }
    };
    window.addEventListener("keydown", escape);
    return () => { window.removeEventListener("keydown", escape); if (opener?.isConnected) opener.focus(); };
  }, [mobile]);
  if (mobile) return <Dialog open onOpenChange={open => { if (!open) close(); }}><DialogContent className="udg-details-dialog"><DialogTitle>{title}</DialogTitle>{children}</DialogContent></Dialog>;
  return <aside className="udg-details" aria-label={`Record details: ${title}`}>
    <header><div><small>Record details</small><h2 ref={heading} tabIndex={-1}>{title}</h2></div>
      {expand && <button type="button" aria-label="Open full record" title="Open full record" onClick={expand}><Maximize2 size={16}/></button>}
      <button type="button" aria-label="Close record details" onClick={close}><X size={18}/></button>
    </header><div className="udg-details-body">{children}</div>
  </aside>;
}

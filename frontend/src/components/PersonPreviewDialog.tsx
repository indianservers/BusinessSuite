import { SuiteAvatar } from "@/components/visuals/SuiteVisuals";
import { useId, useRef, useState, type ReactNode } from "react";
import { Home, Layers, CalendarDays, MessageSquare, Copy, type LucideIcon } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import "./workforce/workforce.css";
export type PersonPreviewTab = { id: string; label: string; icon?: LucideIcon; content: ReactNode };
export function PersonPreviewHeader({ name, identifier, status, photoUrl }: { name: string; identifier?: string; status?: ReactNode; photoUrl?: string | null }) {
  const identifierText = useRef<HTMLSpanElement>(null);
  const [copyStatus, setCopyStatus] = useState("");

  async function copyIdentifier() {
    if (!identifier) return;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(identifier);
        setCopyStatus("Profile identifier copied.");
        return;
      }
    } catch {
      // Keep the visible identifier available for manual copying.
    }
    const selection = window.getSelection();
    if (!selection || !identifierText.current) return;
    const range = document.createRange();
    range.selectNodeContents(identifierText.current);
    selection.removeAllRanges();
    selection.addRange(range);
    setCopyStatus("Profile identifier selected. Copy the selected text.");
  }

  return <header className="wfp-header"><div className="wfp-avatar"><SuiteAvatar name={name} src={photoUrl} size={72}/></div><div className="min-w-0"><DialogTitle className="wfp-title break-words">{name}</DialogTitle><div className="wfp-identity">{identifier && <><span ref={identifierText} className="break-all select-text">{identifier}</span><button type="button" aria-label="Copy profile identifier" onClick={() => void copyIdentifier()}><Copy size={16}/></button><span className="sr-only" role="status">{copyStatus}</span></>}{status && <span className="wfp-active" data-inactive={typeof status === "string" && /inactive|suspended|terminated|resigned|lost/i.test(status)}>{status}</span>}</div></div></header>;
}
export function PersonPreviewTabs({ tabs, value, onChange }: { tabs: PersonPreviewTab[]; value: string; onChange: (value: string) => void }) {
  const uid = useId();
  const icons = [Home, Layers, CalendarDays, MessageSquare];
  return <><div className="wfp-tabs" style={{ gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr))` }} role="tablist" aria-label="Profile sections" onKeyDown={event => { const index = tabs.findIndex(tab => tab.id === value); const next = event.key === "ArrowRight" ? tabs[(index + 1) % tabs.length] : event.key === "ArrowLeft" ? tabs[(index + tabs.length - 1) % tabs.length] : event.key === "Home" ? tabs[0] : event.key === "End" ? tabs[tabs.length - 1] : null; if (next) { event.preventDefault(); onChange(next.id); document.getElementById(`${uid}-tab-${next.id}`)?.focus(); } }}>{tabs.map((tab, index) => { const Icon = tab.icon || icons[index % icons.length]; return <button type="button" key={tab.id} id={`${uid}-tab-${tab.id}`} role="tab" tabIndex={value === tab.id ? 0 : -1} aria-selected={value === tab.id} aria-controls={`${uid}-panel`} onClick={() => onChange(tab.id)}><Icon size={23}/>{tab.label}</button>; })}</div><div id={`${uid}-panel`} role="tabpanel" aria-labelledby={`${uid}-tab-${value}`} className="wfp-body wf-space">{tabs.find(tab => tab.id === value)?.content}</div></>;
}
export default function PersonPreviewDialog({ name, identifier, status, photoUrl, tabs, onClose, initialTab, beforeTabs, onCloseAutoFocus }: { name: string; identifier?: string; status?: ReactNode; photoUrl?: string | null; tabs: PersonPreviewTab[]; onClose: () => void; initialTab?: string; beforeTabs?: ReactNode; onCloseAutoFocus?: (event: Event) => void }) {
  const [tab, setTab] = useState(initialTab || tabs[0]?.id);
  return <Dialog open onOpenChange={open => { if (!open) onClose(); }}><DialogContent className="wf-preview" onCloseAutoFocus={onCloseAutoFocus}><PersonPreviewHeader name={name} identifier={identifier} status={status} photoUrl={photoUrl}/>{beforeTabs}<PersonPreviewTabs tabs={tabs} value={tab} onChange={setTab}/></DialogContent></Dialog>;
}

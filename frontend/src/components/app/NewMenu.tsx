import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { useState } from "react";
import { ChevronDown, Plus, type LucideIcon } from "lucide-react";
import "./new-menu.css";
import MobileCreateMenu from "@/components/mobile/MobileCreateMenu";

export type NewAction = { label: string; description: string; icon: LucideIcon; onSelect: () => void; disabled?: boolean; menuPaths?: string[] };
export default function NewMenu({ actions, disabled, floating = false }: { actions: NewAction[]; disabled?: boolean; floating?: boolean }) {
  const [open, setOpen] = useState(false);
  if (floating) return <MobileCreateMenu actions={actions} disabled={disabled} />;
  if (!actions.length) return null;
  return <Dropdown.Root modal={false} open={open} onOpenChange={setOpen}><Dropdown.Trigger className="suite-new-trigger" disabled={disabled}><Plus size={16} aria-hidden="true" />New<ChevronDown size={14} /></Dropdown.Trigger><Dropdown.Portal><Dropdown.Content onEscapeKeyDown={() => setOpen(false)} className="suite-new-menu" align="end" side="bottom" sideOffset={8} collisionPadding={12}><Dropdown.Label>Create something great</Dropdown.Label>{actions.map(action => <Dropdown.Item key={action.label} disabled={action.disabled} onSelect={() => {
    // Finish dismissing the menu before mounting a dialog with its own focus scope.
    setOpen(false);
    requestAnimationFrame(() => action.onSelect());
  }}><action.icon size={18} /><span className="suite-new-item-copy">{action.label}<small>{action.description}</small></span><Plus size={13} /></Dropdown.Item>)}</Dropdown.Content></Dropdown.Portal></Dropdown.Root>;
}

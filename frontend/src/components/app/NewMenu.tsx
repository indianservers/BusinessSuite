import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { ChevronDown, Plus, type LucideIcon } from "lucide-react";
import "./new-menu.css";

export type NewAction = { label: string; description: string; icon: LucideIcon; onSelect: () => void; disabled?: boolean };
export default function NewMenu({ actions, disabled }: { actions: NewAction[]; disabled?: boolean }) {
  if (!actions.length) return null;
  return <Dropdown.Root><Dropdown.Trigger className="suite-new-trigger" disabled={disabled}><Plus size={16} />New<ChevronDown size={14} /></Dropdown.Trigger><Dropdown.Portal><Dropdown.Content className="suite-new-menu" align="end" sideOffset={8} collisionPadding={12}><Dropdown.Label>Create something great</Dropdown.Label>{actions.map(action => <Dropdown.Item key={action.label} disabled={action.disabled} onSelect={action.onSelect}><action.icon size={18} /><span>{action.label}<small>{action.description}</small></span><Plus size={13} /></Dropdown.Item>)}</Dropdown.Content></Dropdown.Portal></Dropdown.Root>;
}

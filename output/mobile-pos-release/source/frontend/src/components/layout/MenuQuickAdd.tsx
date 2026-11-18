import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { Plus } from "lucide-react";
import type { NewAction } from "@/components/app/NewMenu";

/** Separate from the page link so a create click never also navigates to its list. */
export default function MenuQuickAdd({ actions, paths, label, onNavigate }: {
  actions: NewAction[]; paths: string[]; label: string; onNavigate: () => void;
}) {
  const matches = actions.filter(action => !action.disabled && action.menuPaths?.some(path =>
    paths.some(candidate => candidate.split(/[?#]/)[0] === path)));
  if (!matches.length) return null;
  const select = (action: NewAction) => { onNavigate(); requestAnimationFrame(action.onSelect); };
  if (matches.length === 1) return <button type="button" className="module-menu-create" aria-label={`Create ${matches[0].label.replace(/^Add /, "")}`} title={matches[0].description} onClick={() => select(matches[0])}><Plus size={14}/></button>;
  return <Dropdown.Root modal={false}><Dropdown.Trigger className="module-menu-create" aria-label={`Create in ${label}`} title={`Create in ${label}`}><Plus size={14}/></Dropdown.Trigger><Dropdown.Portal><Dropdown.Content className="suite-new-menu" side="right" align="start" sideOffset={8} collisionPadding={12}><Dropdown.Label>Create in {label}</Dropdown.Label>{matches.map(action => <Dropdown.Item key={action.label} onSelect={() => select(action)}><action.icon size={17}/><span>{action.label}<small>{action.description}</small></span></Dropdown.Item>)}</Dropdown.Content></Dropdown.Portal></Dropdown.Root>;
}

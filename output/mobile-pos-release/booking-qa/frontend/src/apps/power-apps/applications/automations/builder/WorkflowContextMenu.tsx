import * as Menu from "@radix-ui/react-dropdown-menu";
import { ChevronRight, type LucideIcon } from "lucide-react";

export type WorkflowMenuItem = {
  label: string;
  icon?: LucideIcon;
  shortcut?: string;
  disabled?: boolean;
  danger?: boolean;
  action?: () => void;
  children?: WorkflowMenuItem[];
};

function Items({ items }: { items: WorkflowMenuItem[] }) {
  return items.map((item) => {
    const Icon = item.icon;
    const content = <>{Icon && <Icon size={16} />}<span>{item.label}</span>{item.shortcut && <kbd>{item.shortcut}</kbd>}</>;
    return item.children ? (
      <Menu.Sub key={item.label}>
        <Menu.SubTrigger className="as-workflow-menu-item" aria-label={item.label} disabled={item.disabled}>
          {content}<ChevronRight size={14} />
        </Menu.SubTrigger>
        <Menu.Portal>
          <Menu.SubContent className="as-workflow-menu" collisionPadding={10} sideOffset={5}>
            <Items items={item.children} />
          </Menu.SubContent>
        </Menu.Portal>
      </Menu.Sub>
    ) : (
      <Menu.Item key={item.label} aria-label={item.label} className={`as-workflow-menu-item ${item.danger ? "as-workflow-menu-danger" : ""}`} disabled={item.disabled} onSelect={item.action}>
        {content}
      </Menu.Item>
    );
  });
}

export function WorkflowContextMenu({ x, y, title, items, onClose }: {
  x: number; y: number; title: string; items: WorkflowMenuItem[]; onClose: () => void;
}) {
  return (
    <Menu.Root open onOpenChange={(open) => { if (!open) onClose(); }} modal={false}>
      <Menu.Trigger aria-label="Workflow context menu" tabIndex={-1} style={{ position: "fixed", left: x, top: y, width: 1, height: 1, padding: 0, opacity: 0, pointerEvents: "none" }} />
      <Menu.Portal>
        <Menu.Content className="as-workflow-menu" aria-label={title} aria-labelledby={undefined} align="start" sideOffset={2} collisionPadding={10} onCloseAutoFocus={(event) => event.preventDefault()}>
          <Menu.Label className="as-workflow-menu-title">{title}</Menu.Label>
          <Menu.Separator className="as-workflow-menu-separator" />
          <Items items={items} />
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
  );
}

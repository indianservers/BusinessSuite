import type { ReactNode } from "react";
import MoveBoard from "./MoveBoard";

export function moveBefore<T extends { id: number | string }>(
  items: T[],
  id: number | string,
  beforeId?: number | string,
): T[] {
  const item = items.find((i) => i.id === id);
  if (!item || id === beforeId) return items;
  const rest = items.filter((i) => i.id !== id);
  const index = rest.findIndex((i) => i.id === beforeId);
  rest.splice(index < 0 ? rest.length : index, 0, item);
  return rest;
}
export default function OrderedList<T extends { id: number | string }>({
  label,
  items,
  title,
  render,
  onReorder,
  disabled,
}: {
  label: string;
  items: T[];
  title: (item: T) => string;
  render?: (item: T) => ReactNode;
  onReorder: (items: T[]) => Promise<void>;
  disabled?: boolean;
}) {
  return (
    <MoveBoard
      label={label}
      groups={[{ id: "list", label }]}
      items={items.map((item) => ({
        id: item.id,
        label: title(item),
        group: "list",
        content: render?.(item),
      }))}
      disabled={disabled}
      onMove={async ({ item, beforeId }) =>
        onReorder(moveBefore(items, item.id, beforeId))
      }
    />
  );
}

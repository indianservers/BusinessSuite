import { useState, type ReactNode } from "react";
import {
  DndContext,
  PointerSensor,
  KeyboardSensor,
  closestCenter,
  pointerWithin,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical } from "lucide-react";
import "./movement.css";

export type MoveItem = {
  id: string | number;
  label: string;
  group: string;
  disabled?: boolean;
  content?: ReactNode;
};
export type MoveGroup = { id: string; label: string; disabled?: boolean };
export type MoveRequest = {
  item: MoveItem;
  group: string;
  beforeId?: string | number;
};

/** Controlled, handle-only movement. The caller commits through its domain API. */
export default function MoveBoard({
  label,
  items,
  groups,
  onMove,
  disabled = false,
  reorder = true,
}: {
  label: string;
  items: MoveItem[];
  groups: MoveGroup[];
  onMove: (request: MoveRequest) => Promise<void>;
  disabled?: boolean;
  reorder?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );
  async function move(request: MoveRequest) {
    if (
      disabled ||
      busy ||
      request.item.disabled ||
      groups.find((g) => g.id === request.group)?.disabled
    )
      return;
    setBusy(true);
    setError("");
    try {
      await onMove(request);
      setMessage(
        `${request.item.label} moved to ${groups.find((g) => g.id === request.group)?.label || request.group}`,
      );
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail;
      setError(
        typeof detail === "string"
          ? detail
          : "Could not save this move. Refresh and try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  function end(event: DragEndEvent) {
    if (!event.over) return;
    const item = items.find((i) => `item:${i.id}` === event.active.id);
    const target = items.find((i) => `item:${i.id}` === event.over?.id);
    const group =
      target?.group ??
      groups.find((g) => `group:${g.id}` === event.over?.id)?.id;
    if (
      item &&
      group !== undefined &&
      item.id !== target?.id &&
      (reorder || group !== item.group)
    )
      void move({ item, group, beforeId: target?.id });
  }
  return (
    <section className="move-board" aria-label={label} aria-busy={busy}>
      <p className="move-help">
        Drag a handle to move or reorder. You can also use the Move menu or
        focus a handle and press Space, arrow keys, then Space.
      </p>
      <div role="status" className="move-feedback">
        {message}
      </div>
      {error && (
        <p role="alert" className="move-error">
          {error}
        </p>
      )}
      <DndContext
        sensors={sensors}
        collisionDetection={(args) => {
          const hits = pointerWithin(args);
          if (hits.length)
            return hits.some((hit) => String(hit.id).startsWith("item:"))
              ? hits.filter((hit) => String(hit.id).startsWith("item:"))
              : hits;
          return closestCenter(args);
        }}
        onDragEnd={end}
      >
        <div className="move-columns">
          {groups.map((group) => (
            <Lane
              key={group.id}
              group={group}
              items={items.filter((i) => i.group === group.id)}
              disabled={disabled || busy || !!group.disabled}
              groups={groups}
              reorder={reorder}
              move={move}
            />
          ))}
        </div>
      </DndContext>
    </section>
  );
}
function Lane({
  group,
  items,
  disabled,
  groups,
  move,
  reorder,
}: {
  reorder: boolean;
  group: MoveGroup;
  items: MoveItem[];
  disabled: boolean;
  groups: MoveGroup[];
  move: (r: MoveRequest) => Promise<void>;
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: `group:${group.id}`,
    disabled,
  });
  return (
    <section
      ref={setNodeRef}
      className={`move-lane ${isOver ? "move-over" : ""}`}
      aria-label={group.label}
    >
      <h3>
        {group.label}
        <span>{items.length}</span>
      </h3>
      <SortableContext
        items={items.map((i) => `item:${i.id}`)}
        strategy={verticalListSortingStrategy}
      >
        {items.map((item, index) => (
          <Card
            key={item.id}
            item={item}
            disabled={disabled || !!item.disabled}
            groups={groups}
            up={items[index - 1]}
            down={items[index + 1]}
            after={items[index + 2]}
            reorder={reorder}
            move={move}
          />
        ))}
      </SortableContext>
      {!items.length && <p className="move-empty">Drop here</p>}
    </section>
  );
}
function Card({
  item,
  disabled,
  groups,
  up,
  down,
  after,
  move,
  reorder,
}: {
  reorder: boolean;
  item: MoveItem;
  disabled: boolean;
  groups: MoveGroup[];
  up?: MoveItem;
  down?: MoveItem;
  after?: MoveItem;
  move: (r: MoveRequest) => Promise<void>;
}) {
  const {
    setNodeRef,
    attributes,
    listeners,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: `item:${item.id}`, disabled });
  return (
    <article
      ref={setNodeRef}
      className={`move-card ${isDragging ? "move-dragging" : ""}`}
      style={{ transform: CSS.Transform.toString(transform), transition }}
    >
      <div className="move-card-heading">
        <button
          type="button"
          className="move-handle"
          disabled={disabled}
          {...attributes}
          {...listeners}
          aria-label={`Move ${item.label}`}
        >
          <GripVertical size={16} />
        </button>
        <strong>{item.label}</strong>
      </div>
      {item.content}
      <div className="move-card-actions">
        {reorder && (
          <>
            <button
              type="button"
              disabled={disabled || !up}
              aria-label={`Move ${item.label} up`}
              onClick={() =>
                void move({ item, group: item.group, beforeId: up?.id })
              }
            >
              ↑
            </button>
            <button
              type="button"
              disabled={disabled || !down}
              aria-label={`Move ${item.label} down`}
              onClick={() =>
                void move({ item, group: item.group, beforeId: after?.id })
              }
            >
              ↓
            </button>
          </>
        )}
        <select
          aria-label={`Move ${item.label} to`}
          disabled={disabled}
          value={item.group}
          onChange={(e) => void move({ item, group: e.target.value })}
        >
          {groups.map((g) => (
            <option key={g.id} value={g.id} disabled={g.disabled}>
              {g.label}
            </option>
          ))}
        </select>
      </div>
    </article>
  );
}

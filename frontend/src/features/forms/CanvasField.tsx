import { useRef, useState, type CSSProperties, type ReactNode } from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { Question } from "./formsTypes";

export const fieldSpans = { auto: 12, full: 12, half: 6, third: 4, "two-thirds": 8, quarter: 3, "three-quarters": 9 };
type Layout = Pick<Question, "width" | "height">;
export type CanvasEditor = {
  selected: string;
  select: (id: string) => void;
  label: (id: string, label: string) => void;
  resize: (id: string, layout: Layout) => void;
};
export function fieldStyle(field: Question, columns: number): CSSProperties {
  const span = ["section", "page"].includes(field.type) ? 12 : field.width && field.width !== "auto" ? fieldSpans[field.width] : 12 / columns;
  return { "--field-span": span, "--field-height": field.height ? `${field.height}px` : undefined } as CSSProperties;
}
const widths: [NonNullable<Question["width"]>, number][] = [["quarter",3],["third",4],["half",6],["two-thirds",8],["three-quarters",9],["full",12]];
export default function CanvasField({ field, columns, editor, children }: { field: Question; columns: number; editor: CanvasEditor; children: ReactNode }) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging, isOver } = useSortable({ id: field.id });
  const [preview, setPreview] = useState<Layout | null>(null);
  const gesture = useRef<{ x: number; y: number; width: number; height: number; grid: number; scale: number; layout: Layout } | null>(null);
  const selected = editor.selected === field.id;
  return <div ref={setNodeRef} data-field-id={field.id} className={`form-live-field editable-field ${selected ? "editing-field" : ""} ${isDragging ? "canvas-field-dragging" : ""} ${isOver ? "canvas-field-over" : ""}`} style={{ ...fieldStyle({ ...field, ...preview }, columns), transform: CSS.Transform.toString(transform), transition, zIndex: isDragging ? 10 : undefined }}>
    <button type="button" className="form-field-edit-target" aria-label={`Edit ${field.label}`} aria-pressed={selected} onClick={() => editor.select(field.id)} />
    <div className="canvas-field-tools">
      <button type="button" ref={setActivatorNodeRef} {...attributes} {...listeners} className="canvas-field-drag" aria-label={`Drag ${field.label}`} onFocus={() => editor.select(field.id)}>⠿</button>
      <span>Drag to arrange</span>
    </div>
    {children}
    {!["section", "page"].includes(field.type) && <button type="button" className="canvas-field-resize" aria-label={`Resize ${field.label}`} title="Drag to resize; arrow keys adjust size" onKeyDown={e => {
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
      e.preventDefault();
      if (e.key === "ArrowUp" || e.key === "ArrowDown") editor.resize(field.id, { height: Math.max(48, Math.min(600, (field.height || 80) + (e.key === "ArrowUp" ? -16 : 16))) });
      else {
        const span = fieldSpans[field.width || "auto"] / (!field.width || field.width === "auto" ? columns : 1);
        const next = e.key === "ArrowLeft" ? [...widths].reverse().find(w => w[1] < span) : widths.find(w => w[1] > span);
        if (next) editor.resize(field.id, { width: next[0] });
      }
    }} onPointerDown={e => {
      e.preventDefault(); e.stopPropagation(); editor.select(field.id);
      const node = e.currentTarget.parentElement!;
      const rect = node.getBoundingClientRect();
      gesture.current = { x:e.clientX, y:e.clientY, width:rect.width, height:rect.height, grid:node.parentElement!.getBoundingClientRect().width, scale:rect.width / node.offsetWidth, layout:{} };
      e.currentTarget.setPointerCapture(e.pointerId);
    }} onPointerMove={e => {
      const g = gesture.current; if (!g) return;
      const span = Math.max(3, Math.min(12, (g.width + e.clientX - g.x) / g.grid * 12));
      const nearest = widths.reduce((a,b) => Math.abs(a[1]-span) < Math.abs(b[1]-span) ? a : b);
      g.layout = { width:nearest[0], height:Math.round(Math.max(48,Math.min(600,(g.height+e.clientY-g.y)/g.scale))) };
      setPreview(g.layout);
    }} onPointerUp={e => {
      const g = gesture.current; gesture.current = null;
      if (g && Object.keys(g.layout).length) editor.resize(field.id,g.layout);
      setPreview(null); e.currentTarget.releasePointerCapture(e.pointerId);
    }} onPointerCancel={() => { gesture.current = null; setPreview(null); }}>↘</button>}
  </div>;
}

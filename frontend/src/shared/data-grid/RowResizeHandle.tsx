import { useRef } from "react";

/** Excel-style row boundary: drag, use arrow keys, or double-click to fit. */
export default function RowResizeHandle({ height, change, fit }: { height: number; change: (height: number) => void; fit: () => number }) {
  const start = useRef<{ y: number; height: number }>();
  const clamp = (value: number) => Math.max(32, Math.min(400, Math.round(value)));
  return <span className="suite-row-resize" role="separator" aria-label="Resize row height" aria-orientation="horizontal" aria-valuemin={32} aria-valuemax={400} aria-valuenow={height} tabIndex={0}
    title="Drag to resize row; double-click to fit content"
    onClick={event => event.stopPropagation()} onDoubleClick={event => { event.preventDefault(); event.stopPropagation(); change(clamp(fit())); }}
    onPointerDown={event => { event.preventDefault(); event.stopPropagation(); start.current = { y: event.clientY, height }; event.currentTarget.setPointerCapture(event.pointerId); }}
    onPointerMove={event => { if (start.current) change(clamp(start.current.height + event.clientY - start.current.y)); }}
    onPointerUp={() => { start.current = undefined; }} onPointerCancel={() => { start.current = undefined; }}
    onKeyDown={event => { if (["ArrowUp", "ArrowDown", "Enter"].includes(event.key)) { event.preventDefault(); event.stopPropagation(); change(clamp(event.key === "Enter" ? fit() : height + (event.key === "ArrowDown" ? 8 : -8))); } }}/>
}

export function fitRow(element: HTMLElement | null) {
  if (!element) return 64;
  return Math.max(48, ...Array.from(element.querySelectorAll<HTMLElement>(".udg-cell > *, td > *:not(.suite-row-resize)"), child => child.scrollHeight + 20));
}

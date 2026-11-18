import type { KeyboardEvent } from "react";

/** Enter edits text; task creation requires an explicit Create/Save action. */
export function guardTaskEnter(event: KeyboardEvent<HTMLElement>) {
  if (event.key !== "Enter" || event.nativeEvent.isComposing) return;
  const target = event.target;
  if (!(target instanceof HTMLElement) || target.closest('[role="combobox"],[role="listbox"],[role="menu"]')) return;
  if (target.matches('input:not([type="button"]):not([type="submit"]):not([type="checkbox"]):not([type="radio"]):not([type="file"])')) event.preventDefault();
  // Rich text and textarea retain their native newlines, including Ctrl+Enter.
  if (target.matches("input,textarea") || target.isContentEditable) event.stopPropagation();
}

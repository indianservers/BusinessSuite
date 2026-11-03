/** Installed before BrowserRouter so canceled back/forward events never replace the draft. */
type DraftGuard = { isDirty: () => boolean; index: number };
let current: DraftGuard | undefined;
let reversing = false;
window.addEventListener("popstate", event => {
  if (reversing) {
    reversing = false;
    event.stopImmediatePropagation();
    return;
  }
  if (!current?.isDirty()) return;
  if (window.confirm("Discard your unsaved settings changes?")) return;
  event.stopImmediatePropagation();
  const destination = event.state?.idx;
  if (typeof destination === "number" && destination !== current.index) {
    reversing = true;
    window.history.go(current.index - destination);
  }
}, true);
export function registerSettingsDraftGuard(isDirty: () => boolean) {
  const guard = { isDirty, index: window.history.state?.idx ?? 0 };
  current = guard;
  return () => { if (current === guard) current = undefined; };
}

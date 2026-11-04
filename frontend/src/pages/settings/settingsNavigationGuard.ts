/** Installed before BrowserRouter so canceled back/forward events never replace the draft. */
type DraftGuard = { isDirty: () => boolean; index: number };
const guards = new Set<DraftGuard>();
let reversing = false;
window.addEventListener("popstate", event => {
  if (reversing) {
    reversing = false;
    event.stopImmediatePropagation();
    return;
  }
  const current = [...guards].find(guard => guard.isDirty());
  if (!current) return;
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
  guards.add(guard);
  return () => { guards.delete(guard); };
}

/** Actions come from the current page/record, so permission and busy states stay
 * owned by the original controls and their existing confirmation flows. */
export type PageContextAction = { label: string; source: HTMLElement; run: () => void };
const recordSelector = '[data-context-record],tbody tr,[role="row"][data-row-index],article,[data-context-scope]';
const excluded = 'aside,[role="menu"],[data-context-menu-ignore],.ws-sidebar,.kf-workspace-global';
const editable = 'input,textarea,select,[contenteditable]:not([contenteditable="false"])';
export function controlLabel(element: HTMLElement): string {
  return (element.dataset.contextAction || element.getAttribute("aria-label") || element.getAttribute("title") || element.innerText || "").replace(/\s+/g, " ").trim();
}
export function available(element: HTMLElement): boolean {
  return element.isConnected && element.getClientRects().length > 0 &&
    !element.closest('[hidden],[inert],[aria-hidden="true"],[aria-disabled="true"]') &&
    !element.matches(':disabled,[aria-disabled="true"]') &&
    getComputedStyle(element).visibility !== "hidden" && getComputedStyle(element).display !== "none";
}
export function collectPageContext(target: HTMLElement, root: HTMLElement) {
  if (target.closest(editable) || target.closest(excluded)) return null;
  const dialog = target.closest<HTMLElement>('[role="dialog"]');
  const record = target.closest<HTMLElement>(recordSelector);
  const scope = record && root.contains(record) ? record : dialog || root;
  const heading = scope.querySelector<HTMLElement>('h1,h2,h3,[data-context-title]');
  const title = scope.dataset.contextRecord || scope.dataset.contextTitle || heading?.textContent?.trim() ||
    (record ? record.querySelector('td,[role="cell"]')?.textContent?.trim() : root.querySelector('h1,h2')?.textContent?.trim()) || document.title;
  const actions: PageContextAction[] = [];
  const seen = new Set<string>();
  const add = (label: string, source: HTMLElement, run: () => void) => {
    if (!label || label.length > 100 || seen.has(label.toLowerCase()) || !available(source)) return;
    seen.add(label.toLowerCase()); actions.push({ label, source, run });
  };
  if (record?.dataset.contextOpen) add(record.dataset.contextOpen, record, () => { if (available(record)) record.click(); });
  // Record actions never borrow controls from another row or card.
  scope.querySelectorAll<HTMLElement>('button,a[href],[data-context-action]').forEach(source => {
    if (source.closest(excluded) || !available(source)) return;
    if (!record && source.closest(recordSelector)) return;
    if (source.closest('nav') && !source.closest('[data-context-actions]')) return;
    if (source.getAttribute('role') === 'tab' && source.getAttribute('aria-selected') === 'true') return;
    const label = controlLabel(source);
    if (!label || /^(previous|next|back|close|cancel|dismiss|menu|more|actions|\d+|…|\.\.\.)$/i.test(label)) return;
    // Avoid turning filters, pagination, selections and arbitrary record values
    // into a long menu. Explicitly named actions are always supported.
    if (!record && source.tagName !== 'A' && !source.dataset.contextAction &&
      !/^(adjust|transfer|receive|dispatch|calculate|convert|duplicate|merge|resolve|close|add|new|create|invite|import|export|download|upload|save|submit|approve|reject|process|run|generate|reconcile|record|pay|post|send|schedule|assign|manage|edit|delete|remove|archive|restore|search|filter|clear|reset|view|open|show|configure|connect|start|stop|pause|resume|publish|apply|check|mark|refresh|sync|load|enable|disable|build|review)\b/i.test(label)) return;
    const contextualLabel = /^(edit|delete|remove|archive|restore|view|open|approve|reject|save|submit|export|download|refresh)$/i.test(label) ? `${label} · ${title}` : label;
    add(contextualLabel, source, () => { if (available(source)) source.click(); });
  });
  if (!record) {
    scope.querySelectorAll<HTMLElement>('input[type="search"],input[placeholder],select,[role="combobox"]').forEach(source => {
      if (source.closest(excluded) || source.closest(recordSelector)) return;
      const label = source.getAttribute('aria-label') || source.getAttribute('placeholder') ||
        (source as HTMLInputElement).labels?.[0]?.textContent?.trim();
      if (!label || !/search|find|filter|workspace|team|status|period|year|month|branch|department|role/i.test(label)) return;
      add(`${source.tagName === 'INPUT' ? 'Search' : 'Filter'} · ${label}`, source, () => { if (available(source)) { source.focus(); source.scrollIntoView({ block: 'nearest' }); } });
    });
  }
  return actions.length ? { title: title.slice(0, 100), actions } : null;
}

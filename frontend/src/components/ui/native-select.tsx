import { Children, cloneElement, forwardRef, isValidElement, useEffect, useId, useRef, useState, type ReactNode, type SelectHTMLAttributes } from "react";
import * as Popover from "@radix-ui/react-popover";
import { useAuthStore } from "@/store/authStore";

type Props = SelectHTMLAttributes<HTMLSelectElement> & {
  loading?: boolean;
  error?: boolean;
  loadingText?: string;
  emptyText?: string;
  searchable?: boolean;
  recentKey?: string;
};

function hasChoices(children: ReactNode): boolean {
  return Children.toArray(children).some(child => {
    if (!isValidElement<{ value?: unknown; children?: ReactNode }>(child)) return false;
    if (child.type === "option") return child.props.value !== "";
    return hasChoices(child.props.children);
  });
}

function hasPlaceholder(children: ReactNode): boolean {
  return Children.toArray(children).some(child => isValidElement<{ value?: unknown; children?: ReactNode }>(child) &&
    (child.type === "option" ? child.props.value === "" : hasPlaceholder(child.props.children)));
}

function loadingChildren(children: ReactNode, text: string): ReactNode {
  return Children.map(children, child => {
    if (!isValidElement<{ value?: unknown; children?: ReactNode }>(child)) return child;
    if (child.type === "option") return child.props.value === "" ? cloneElement(child, {}, text) : child;
    return child.props.children ? cloneElement(child, {}, loadingChildren(child.props.children, text)) : child;
  });
}

/** A native select: retains browser keyboard, form, styling and ref behavior. */
export const NativeSelect = forwardRef<HTMLSelectElement, Props>(function NativeSelect({
  children, loading = false, error = false, loadingText = "Loading choices…", emptyText = "No data found", searchable, recentKey, ...props
}, ref) {
  const initialLoading = loading && !hasChoices(children);
  const node = useRef<HTMLSelectElement | null>(null);
  const interactedOutside = useRef(false);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [choices, setChoices] = useState<{value: string; label: string; disabled: boolean; group: string}[]>([]);
  const [recent, setRecent] = useState<string[]>([]);
  const [active, setActive] = useState(0);
  const listId = useId();
  const userId = useAuthStore(state => state.user?.id);
  const label = props["aria-label"] || props.name || "choices";
  const storageKey = () => `suite:choices:${userId || "anonymous"}:${sessionStorage.getItem("suite-organization") || ""}:${sessionStorage.getItem("suite-branch") || ""}:${recentKey || `${location.pathname}:${props.id || label}`}`;
  const readRecent = (): string[] => { try { const value = JSON.parse(localStorage.getItem(storageKey()) || "[]"); return Array.isArray(value) ? value.filter(v => typeof v === "string").slice(0, 5) : []; } catch { return []; } };
  const remember = (value: string) => { if (!value) return; try { localStorage.setItem(storageKey(), JSON.stringify([value, ...readRecent().filter(v => v !== value)].slice(0, 5))); } catch { /* Storage may be unavailable. Selection still works. */ } };
  const canSearch = () => (!props.size || props.size === 1) && !props.disabled && !initialLoading && !error && searchable !== false && (searchable === true || (node.current?.options.length || 0) > 8);
  const show = () => {
    if (!canSearch() || !node.current) return;
    setChoices(Array.from(node.current.options).map(option => ({value: option.value, label: option.text, disabled: option.disabled || (option.parentElement instanceof HTMLOptGroupElement && option.parentElement.disabled), group: option.parentElement instanceof HTMLOptGroupElement ? option.parentElement.label : ""})));
    interactedOutside.current = false;
    setRecent(readRecent()); setQuery(""); setActive(0); setOpen(true);
  };
  const matches = choices.filter(choice => `${choice.label} ${choice.group}`.toLowerCase().includes(query.trim().toLowerCase()));
  const ordered = !query.trim() ? [...matches.filter(choice => recent.includes(choice.value) && !choice.disabled).sort((a, b) => recent.indexOf(a.value) - recent.indexOf(b.value)), ...matches.filter(choice => !recent.includes(choice.value) || choice.disabled)] : matches;
  useEffect(() => {if (open) document.getElementById(`${listId}-${active}`)?.scrollIntoView({block: "nearest"});}, [open, active, query, listId]);
  const choose = (value: string) => {
    if (!node.current || props.disabled || initialLoading || error) return;
    const option = Array.from(node.current.options).find(option => option.value === value);
    if (!option || option.disabled || (option.parentElement instanceof HTMLOptGroupElement && option.parentElement.disabled)) return;
    if (props.multiple) option.selected = !option.selected;
    else node.current.value = value;
    remember(value);
    node.current.dispatchEvent(new Event("change", {bubbles: true}));
    if (!props.multiple) setOpen(false);
    else setChoices(current => [...current]);
  };
  const empty = !hasChoices(children);
  return <Popover.Root open={open && !props.disabled && !initialLoading && !error} onOpenChange={setOpen}><Popover.Anchor asChild><select {...props} ref={element => { node.current = element; if (typeof ref === "function") ref(element); else if (ref) ref.current = element; }} aria-busy={loading || undefined} data-choice-state={initialLoading ? "loading" : error ? "error" : empty ? "empty" : "ready"}
    onChange={event => { remember(event.currentTarget.value); props.onChange?.(event); }}
    onPointerDown={event => { props.onPointerDown?.(event); if (!event.defaultPrevented && event.button === 0 && canSearch()) { event.preventDefault(); show(); } }}
    onKeyDown={event => { props.onKeyDown?.(event); if (!event.defaultPrevented && ["Enter", " "].includes(event.key) && canSearch()) { event.preventDefault(); show(); } }}>
    {initialLoading ? loadingChildren(children, loadingText) : children}
    {(initialLoading ? !hasPlaceholder(children) : error || empty) && <option disabled value="">
      {initialLoading ? loadingText : error ? "Could not load choices" : emptyText}
    </option>}
  </select></Popover.Anchor>
  <Popover.Portal><Popover.Content aria-label={`Search ${label}`} sideOffset={4} collisionPadding={12} onInteractOutside={() => {interactedOutside.current = true;}} onCloseAutoFocus={event => {event.preventDefault(); if (!interactedOutside.current) node.current?.focus();}} className="z-[1000] w-[max(16rem,var(--radix-popover-trigger-width))] max-w-[calc(100vw-1rem)] rounded-xl border bg-popover p-2 text-popover-foreground shadow-xl">
    <input autoFocus role="combobox" aria-label={`Search ${label}`} aria-controls={listId} aria-expanded="true" aria-autocomplete="list" aria-activedescendant={ordered[active] ? `${listId}-${active}` : undefined} className="mb-2 h-10 w-full rounded-md border bg-background px-3 text-sm" placeholder="Search choices…" value={query} onChange={event => {setQuery(event.target.value); setActive(0);}} onKeyDown={event => {
      if (event.key === "Escape") {event.preventDefault(); event.stopPropagation(); setOpen(false);}
      if (event.key === "ArrowDown" || event.key === "ArrowUp") { event.preventDefault(); setActive(index => Math.max(0, Math.min(ordered.length - 1, index + (event.key === "ArrowDown" ? 1 : -1)))); }
      if (event.key === "Enter") {event.preventDefault(); const choice = ordered[active]; if (choice && !choice.disabled) choose(choice.value);}
    }} />
    <div id={listId} role="listbox" aria-label={label} aria-multiselectable={props.multiple || undefined} className="max-h-64 overflow-y-auto">
      {ordered.map((choice, index) => <div key={`${choice.value}-${index}`} id={`${listId}-${index}`} role="option" aria-selected={Array.from(node.current?.selectedOptions || []).some(option => option.value === choice.value)} aria-disabled={choice.disabled || undefined} onPointerDown={event => event.preventDefault()} onMouseEnter={() => setActive(index)} onClick={() => !choice.disabled && choose(choice.value)} className={`cursor-pointer rounded-md px-3 py-2 text-sm ${index === active ? "bg-accent" : ""} ${choice.disabled ? "cursor-not-allowed opacity-50" : "hover:bg-accent"}`}>
        {choice.label}{choice.group && <span className="ml-2 text-xs text-muted-foreground">{choice.group}</span>}{!query.trim() && recent.includes(choice.value) && <span className="ml-2 text-xs text-muted-foreground">Recent</span>}
      </div>)}
      {!ordered.length && <p role="status" className="p-3 text-sm text-muted-foreground">No matching choices.</p>}
    </div>
    {props.multiple && <button type="button" className="mt-2 min-h-10 w-full rounded-md border px-3 text-sm" onClick={() => setOpen(false)}>Done</button>}
  </Popover.Content></Popover.Portal></Popover.Root>;
});
// CompactForm recognizes this as a field, exactly as it does a native select.
NativeSelect.displayName = "select";

import { useEffect, useId, useRef, useState } from "react";
import { Check, ChevronDown, Loader2, Plus, Search, X } from "lucide-react";
import "./smart-record-picker.css";

export type RecordSuggestion<T> = { id: string; label: string; description?: string; searchText?: string; record: T };
export default function SmartRecordPicker<T>({ name, value, search, onSearch, items, selected, onSelect, onClear, loading, error, retry, onCreate, hasMore, loadMore, inputId }: {
  inputId?: string; name: string; value: string; search: string; onSearch: (search: string) => void;
  items: RecordSuggestion<T>[]; selected?: RecordSuggestion<T>; onSelect: (record: T) => void; onClear: () => void;
  loading?: boolean; error?: string; retry?: () => void; onCreate?: (seedName: string) => void; hasMore?: boolean; loadMore?: () => void;
}) {
  const [open, setOpen] = useState(false), [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null), id = useId();
  const term = search.trim().toLocaleLowerCase();
  const matches = items.filter(item => !term || `${item.label} ${item.description || ""} ${item.searchText || ""}`.toLocaleLowerCase().includes(term));
  const ranked = [...matches].sort((a, b) => Number(b.label.toLocaleLowerCase().startsWith(term)) - Number(a.label.toLocaleLowerCase().startsWith(term)));
  const activeIndex = Math.min(active, Math.max(0, ranked.length - 1));
  useEffect(() => {
    if (open) document.getElementById(`${id}-option-${activeIndex}`)?.scrollIntoView({ block: "nearest" });
  }, [open, id, activeIndex]);
  const choose = (item: RecordSuggestion<T>) => { onSelect(item.record); onSearch(""); setOpen(false); };
  const createAction = onCreate && <button type="button" className="smart-record-create" onClick={event => { event.preventDefault(); event.stopPropagation(); onCreate(search.trim()); }}><Plus size={15}/> Create {name.toLowerCase()}{search.trim() ? ` “${search.trim()}”` : ""}</button>;
  return <div className="smart-record-picker" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) { setOpen(false); onSearch(""); } }}>
    <div className={`smart-record-input ${open ? "is-open" : ""}`}>
      <Search size={16} aria-hidden="true"/>
      <input id={inputId} ref={input} data-record-picker role="combobox" aria-label={`Search ${name.toLowerCase()}`} aria-autocomplete="list" aria-expanded={open}
        aria-controls={`${id}-list`} aria-activedescendant={open && ranked.length ? `${id}-option-${activeIndex}` : undefined}
        autoComplete="off" placeholder={`Search ${name.toLowerCase()} by name, email or phone…`}
        value={open ? search : selected?.label || (value ? `Selected ${name.toLowerCase()} #${value}` : "")}
        onFocus={() => { setOpen(true); setActive(0); }}
        onChange={event => { onSearch(event.target.value); setOpen(true); setActive(0); }}
        onKeyDown={event => {
          if (event.key === "Escape" && open) { event.preventDefault(); event.stopPropagation(); setOpen(false); onSearch(""); }
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault(); setOpen(true); setActive(previous => Math.max(0, Math.min(ranked.length - 1, previous + (event.key === "ArrowDown" ? 1 : -1))));
          }
          if (event.key === "Enter" && open) { event.preventDefault(); event.stopPropagation(); if (ranked[activeIndex]) choose(ranked[activeIndex]); }
        }}/>
      {value && <button type="button" aria-label={`Clear ${name.toLowerCase()}`} onClick={event => { event.preventDefault(); onClear(); onSearch(""); setOpen(false); }}><X size={15}/></button>}
      <button type="button" aria-label={`Show ${name.toLowerCase()} suggestions`} onClick={event => { event.preventDefault(); setOpen(!open); if (!open) input.current?.focus(); }}><ChevronDown size={15}/></button>
    </div>
    {open && <div className="smart-record-results">
      <div className="smart-record-result-header">{loading ? <><Loader2 size={13} className="animate-spin"/> Searching…</> : `${ranked.length} suggestion${ranked.length === 1 ? "" : "s"}`}{selected && <small>Selected: {selected.label}</small>}</div>
      <div role="listbox" id={`${id}-list`} aria-label={`${name} suggestions`} aria-busy={!!loading}>
        {ranked.map((item, index) => <button type="button" role="option" id={`${id}-option-${index}`} key={item.id} aria-selected={item.id === value}
          className={index === activeIndex ? "is-active" : ""} onMouseDown={event => event.preventDefault()} onMouseEnter={() => setActive(index)} onClick={event => { event.preventDefault(); choose(item); }}>
          <span><strong>{item.label}</strong>{item.description && <small>{item.description}</small>}</span>{item.id === value && <Check size={16}/>}
        </button>)}
      </div>
      {!loading && !ranked.length && !error && <p role="status">No matching {name.toLowerCase()} found. Try another name, email or phone.</p>}
      {error && <p role="alert">{error}{retry && <button type="button" onClick={retry}>Retry</button>}</p>}
      {hasMore && <button type="button" className="smart-record-more" disabled={loading} onClick={loadMore}>Load more suggestions</button>}
      {createAction}
    </div>}
    {!open && createAction}
    {!open && error && <p role="alert" className="smart-record-error">{error}{retry && <button type="button" onClick={retry}>Retry</button>}</p>}
  </div>;
}

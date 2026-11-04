import { useEffect, useId, useRef, useState } from "react";
import * as Popover from "@radix-ui/react-popover";
import { Check, ChevronDown, Search } from "lucide-react";
import definitions from "../../../../backend/app/core/business_forms.json";

const names = new Intl.DisplayNames(["en"], { type: "currency" });
function currencyDetails(code: string) {
  try {
    const symbol = new Intl.NumberFormat("en-IN", { style: "currency", currency: code, currencyDisplay: "narrowSymbol" }).formatToParts(0).find(part => part.type === "currency")?.value || code;
    return { code, symbol, name: names.of(code) || code };
  } catch { return { code, symbol: code, name: code }; }
}
const currencies = ["INR", ...definitions.currencies.filter(code => code !== "INR")].map(currencyDetails);

type Props = { value: string; onChange: (value: string) => void; label?: string; disabled?: boolean };
export function CurrencySelect({ value, onChange, label = "Currency", disabled = false }: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [active, setActive] = useState(0);
  const listId = useId();
  const list = useRef<HTMLDivElement>(null);
  const selected = currencies.find(currency => currency.code === value) || currencyDetails(value);
  const options = value && !currencies.some(currency => currency.code === value) ? [...currencies, selected] : currencies;
  const matches = options.filter(currency => `${currency.code} ${currency.name} ${currency.symbol}`.toLowerCase().includes(search.trim().toLowerCase()));
  useEffect(() => { list.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" }); }, [active, open]);
  const choose = (code: string) => { onChange(code); setOpen(false); };
  return <Popover.Root open={open && !disabled} onOpenChange={next => { setOpen(next); if (next) { setSearch(""); setActive(0); } }}>
    <Popover.Trigger asChild><button type="button" disabled={disabled} aria-label={label} aria-haspopup="listbox" aria-expanded={open && !disabled} aria-controls={open ? listId : undefined} title={selected.name} onKeyDown={event => { if (event.key === "ArrowDown") { event.preventDefault(); setSearch(""); setActive(0); setOpen(true); } }} style={{ width: 132, maxWidth: "100%", minHeight: 40, display: "inline-flex", alignItems: "center", justifyContent: "space-between", gap: 8, padding: "6px 10px", border: "1px solid hsl(var(--border, 214 32% 91%))", borderRadius: 7, background: "inherit", color: "inherit", font: "inherit" }} className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50">
      <span className="flex items-center gap-2"><span aria-hidden="true" className="text-lg text-muted-foreground">{selected.symbol === selected.code ? "¤" : selected.symbol}</span><span className="text-sm font-medium">{value || "Choose"}</span></span><ChevronDown size={14} aria-hidden="true" />
    </button></Popover.Trigger>
    <Popover.Portal><Popover.Content align="start" sideOffset={5} collisionPadding={8} className="z-[180] w-72 max-w-[calc(100vw-1rem)] rounded-xl border bg-popover p-1.5 text-popover-foreground shadow-xl" onKeyDown={event => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") { event.preventDefault(); setActive(index => Math.max(0, Math.min(matches.length - 1, index + (event.key === "ArrowDown" ? 1 : -1)))); }
      if (event.key === "Enter") { event.preventDefault(); if (matches[active]) choose(matches[active].code); }
    }}>
      <div className="mb-1 flex items-center gap-2 rounded-lg border px-2"><Search size={15} aria-hidden="true" className="shrink-0 text-muted-foreground" /><input autoFocus type="search" role="combobox" aria-label={`Search ${label.toLowerCase()}`} aria-autocomplete="list" aria-expanded="true" aria-controls={listId} aria-activedescendant={matches[active] ? `${listId}-${active}` : undefined} placeholder="Search currency or symbol" value={search} onChange={event => { setSearch(event.target.value); setActive(0); }} className="h-9 min-w-0 flex-1 bg-transparent text-sm outline-none" /></div>
      <div ref={list} id={listId} role="listbox" aria-label={label} className="max-h-64 overflow-y-auto overscroll-contain">
        {matches.map((currency, index) => <button type="button" role="option" tabIndex={-1} id={`${listId}-${index}`} data-index={index} key={currency.code} aria-selected={currency.code === value} onMouseMove={() => setActive(index)} onPointerDown={event => event.preventDefault()} onClick={() => choose(currency.code)} className={`flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left ${active === index ? "bg-accent text-accent-foreground" : "hover:bg-accent"}`}>
          <span aria-hidden="true" className="flex h-9 w-10 shrink-0 items-center justify-center rounded-md border bg-background text-base font-medium">{currency.symbol}</span><span className="min-w-0 flex-1"><span className="block text-sm font-semibold">{currency.code}</span><span className="block truncate text-xs text-muted-foreground">{currency.name}</span></span>{currency.code === value && <Check size={16} aria-hidden="true" />}
        </button>)}
        {!matches.length && <p role="status" className="p-4 text-center text-sm text-muted-foreground">No currencies found</p>}
      </div>
    </Popover.Content></Popover.Portal>
  </Popover.Root>;
}

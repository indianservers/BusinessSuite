import * as React from "react";
import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";

const ChoiceContext = React.createContext({ loading: false, error: false, recent: [] as string[] });
function Select({ loading = false, error = false, recentKey, ...props }: React.ComponentProps<typeof SelectPrimitive.Root> & { loading?: boolean; error?: boolean; recentKey?: string }) {
  const id = React.useId();
  const userId = useAuthStore(state => state.user?.id);
  const scope = () => { try { return `${sessionStorage.getItem("suite-organization") || ""}:${sessionStorage.getItem("suite-branch") || ""}`; } catch { return ""; } };
  const key = `suite:select:${userId}:${scope()}:${location.pathname}:${recentKey || props.name || id}`;
  const read = (): string[] => { try { const data = JSON.parse(localStorage.getItem(key) || "[]"); return Array.isArray(data) ? data.filter(value => typeof value === "string").slice(0, 5) : []; } catch { return []; } };
  const [recent, setRecent] = React.useState<string[]>(read);
  React.useEffect(() => setRecent(read()), [key]);
  return <ChoiceContext.Provider value={{ loading, error, recent }}><SelectPrimitive.Root {...props} onValueChange={value => {
    const next = [value, ...read().filter(item => item !== value)].slice(0, 5);
    try { localStorage.setItem(key, JSON.stringify(next)); } catch { /* Selection works without persistence. */ }
    setRecent(next); props.onValueChange?.(value);
  }} /></ChoiceContext.Provider>;
}
const SelectGroup = SelectPrimitive.Group;
const SelectValue = SelectPrimitive.Value;

const SelectTrigger = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>
>(({ className, children, ...props }, ref) => {
  const { loading } = React.useContext(ChoiceContext);
  return (
  <SelectPrimitive.Trigger
    ref={ref}
    className={cn(
      "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
      className
    )}
    {...props}
    aria-busy={loading || undefined}
  >
    <span className="min-w-0 flex-1 truncate text-left">{children}</span>
    <SelectPrimitive.Icon asChild>
      {loading ? <Loader2 aria-label="Loading choices" className="ml-2 h-4 w-4 shrink-0 motion-safe:animate-spin" /> : <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />}
    </SelectPrimitive.Icon>
  </SelectPrimitive.Trigger>
); });
SelectTrigger.displayName = SelectPrimitive.Trigger.displayName;

const SelectScrollUpButton = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.ScrollUpButton>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.ScrollUpButton>
>(({ className, ...props }, ref) => (
  <SelectPrimitive.ScrollUpButton ref={ref} className={cn("flex cursor-default items-center justify-center py-1", className)} {...props}>
    <ChevronUp className="h-4 w-4" />
  </SelectPrimitive.ScrollUpButton>
));
SelectScrollUpButton.displayName = SelectPrimitive.ScrollUpButton.displayName;

const SelectScrollDownButton = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.ScrollDownButton>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.ScrollDownButton>
>(({ className, ...props }, ref) => (
  <SelectPrimitive.ScrollDownButton ref={ref} className={cn("flex cursor-default items-center justify-center py-1", className)} {...props}>
    <ChevronDown className="h-4 w-4" />
  </SelectPrimitive.ScrollDownButton>
));
SelectScrollDownButton.displayName = SelectPrimitive.ScrollDownButton.displayName;

const SelectContent = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Content>
>(({ className, children, position = "popper", ...props }, ref) => {
  const { loading, error, recent } = React.useContext(ChoiceContext);
  const [query, setQuery] = React.useState("");
  const textOf = (nodes: React.ReactNode): string => React.Children.toArray(nodes).map(node => React.isValidElement<{children?: React.ReactNode}>(node) ? textOf(node.props.children) : String(node)).join(" ");
  const items = (nodes: React.ReactNode): React.ReactElement<{value: string; children?: React.ReactNode; disabled?: boolean}>[] => React.Children.toArray(nodes).flatMap(node => {
    if (!React.isValidElement<{value: string; children?: React.ReactNode; disabled?: boolean}>(node)) return [];
    return node.type === SelectItem ? [node] : items(node.props.children);
  });
  const choices = items(children);
  const searchable = choices.length > 8;
  const matches = choices.filter(item => textOf(item.props.children).toLowerCase().includes(query.toLowerCase()));
  const ordered = !query ? [...matches.filter(item => recent.includes(item.props.value)).sort((a,b) => recent.indexOf(a.props.value) - recent.indexOf(b.props.value)), ...matches.filter(item => !recent.includes(item.props.value))] : matches;
  const hasItems = (nodes: React.ReactNode): boolean => React.Children.toArray(nodes).some(node => {
    if (!React.isValidElement<{ children?: React.ReactNode }>(node)) return false;
    return node.type === SelectItem || hasItems(node.props.children);
  });
  return (
  <SelectPrimitive.Portal>
    <SelectPrimitive.Content
      ref={ref}
      className={cn(
        "relative z-[160] max-h-[min(24rem,var(--radix-select-content-available-height,24rem))] min-w-[8rem] max-w-[calc(100vw-1rem)] overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md",
        position === "popper" && "translate-y-1",
        className
      )}
      position={position}
      {...props}
      onCloseAutoFocus={event => {setQuery(""); props.onCloseAutoFocus?.(event);}}
    >
      {searchable && <input aria-label="Search choices" placeholder="Search choices…" value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => {
        if (event.key === "ArrowDown") {event.preventDefault(); event.currentTarget.parentElement?.querySelector<HTMLElement>('[role="option"]:not([data-disabled])')?.focus();}
        if (event.key !== "Escape" && event.key !== "Tab") event.stopPropagation();
      }} className="m-1 h-10 w-[calc(100%-0.5rem)] rounded-md border bg-background px-3 text-sm" />}
      <SelectScrollUpButton />
      <SelectPrimitive.Viewport className={cn("p-1", position === "popper" && "h-[var(--radix-select-trigger-height)] w-full min-w-[var(--radix-select-trigger-width)]")}>
        {searchable && !query && matches.some(item => recent.includes(item.props.value)) && <div className="px-2 py-1 text-xs text-muted-foreground">Recent choices first</div>}
        {searchable ? ordered : children}
        {searchable && !matches.length && <p role="status" className="p-2 text-sm text-muted-foreground">No matching choices.</p>}
        {(loading || error || !hasItems(children)) && <div role={error && !loading ? "alert" : "status"} className="flex items-center gap-2 px-2 py-2 text-xs text-muted-foreground">
          {loading && <Loader2 aria-hidden="true" className="h-3 w-3 shrink-0 motion-safe:animate-spin" />}
          {loading ? "Loading choices…" : error ? "Could not load choices" : "No data found"}
        </div>}
      </SelectPrimitive.Viewport>
      <SelectScrollDownButton />
    </SelectPrimitive.Content>
  </SelectPrimitive.Portal>
); });
SelectContent.displayName = SelectPrimitive.Content.displayName;

const SelectLabel = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Label>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Label>
>(({ className, ...props }, ref) => (
  <SelectPrimitive.Label ref={ref} className={cn("px-2 py-1.5 text-sm font-semibold", className)} {...props} />
));
SelectLabel.displayName = SelectPrimitive.Label.displayName;

const SelectItem = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Item>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Item
    ref={ref}
    className={cn(
      "relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
      className
    )}
    {...props}
  >
    <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
      <SelectPrimitive.ItemIndicator>
        <Check className="h-4 w-4" />
      </SelectPrimitive.ItemIndicator>
    </span>
    <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
  </SelectPrimitive.Item>
));
SelectItem.displayName = SelectPrimitive.Item.displayName;

const SelectSeparator = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Separator>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Separator>
>(({ className, ...props }, ref) => (
  <SelectPrimitive.Separator ref={ref} className={cn("-mx-1 my-1 h-px bg-muted", className)} {...props} />
));
SelectSeparator.displayName = SelectPrimitive.Separator.displayName;

export {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
};

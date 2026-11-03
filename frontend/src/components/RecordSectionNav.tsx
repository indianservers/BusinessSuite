import * as Tabs from "@radix-ui/react-tabs";
import { useId } from "react";

type Section = { value: string; label: string };
type Group = { label: string; sections: Section[] };

/** Four primary tabs at most; section selection preserves existing view keys and deep links. */
export default function RecordSectionNav({ groups, value, onChange, label = "Record sections" }: {
  groups: Group[]; value: string; onChange: (value: string) => void; label?: string;
}) {
  const id = useId();
  const index = Math.max(0, groups.findIndex(group => group.sections.some(section => section.value === value)));
  const selected = groups[index];
  return <div className="space-y-3 rounded-xl border bg-card p-2 shadow-sm">
    <Tabs.Root value={String(index)} onValueChange={next => onChange(groups[Number(next)].sections[0].value)}>
      <Tabs.List aria-label={label} className={`${groups.length === 4 ? "grid grid-cols-2 sm:flex" : "flex"} gap-1`}>
        {groups.map((group, i) => <Tabs.Trigger key={group.label} value={String(i)} className="min-h-11 min-w-0 flex-1 break-words rounded-lg px-2 py-2.5 text-center text-xs sm:px-3 sm:text-sm font-medium text-muted-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary data-[state=active]:bg-primary/10 data-[state=active]:text-primary">{group.label}</Tabs.Trigger>)}
      </Tabs.List>
    </Tabs.Root>
    {selected?.sections.length > 1 && <div className="flex flex-wrap items-center gap-2 border-t px-2 pt-3 pb-1"><label htmlFor={id} className="text-xs font-medium text-muted-foreground">Section</label><select id={id} aria-label={`${label} section`} className="h-11 min-w-0 max-w-full rounded-lg border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" value={value} onChange={event => onChange(event.target.value)}>{selected.sections.map(section => <option key={section.value} value={section.value}>{section.label}</option>)}</select></div>}
  </div>;
}

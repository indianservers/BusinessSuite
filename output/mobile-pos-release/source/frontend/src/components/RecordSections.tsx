import * as Tabs from "@radix-ui/react-tabs";
import { useState, type ReactNode } from "react";
import RecordSectionNav from "./RecordSectionNav";

export default function RecordSections({ sections, label, value, onValueChange }: {
  sections: { id: string; label: string; content: ReactNode }[]; label: string; value?: string; onValueChange?: (value: string) => void;
}) {
  const [selected, setSelected] = useState(sections[0]?.id);
  const active = value ?? (sections.some(section => section.id === selected) ? selected : sections[0]?.id);
  const change = (next: string) => {setSelected(next); onValueChange?.(next);};
  if (sections.length > 4) return <div className="space-y-4">
    <RecordSectionNav label={label} value={active} onChange={change} groups={[
      ...sections.slice(0,3).map(section => ({label:section.label,sections:[{value:section.id,label:section.label}]})),
      {label:"More details",sections:sections.slice(3).map(section => ({value:section.id,label:section.label}))},
    ]}/>
    {sections.map(section => <section key={section.id} role="tabpanel" aria-label={section.label} hidden={section.id !== active} className="space-y-4">{section.content}</section>)}
  </div>;
  return <Tabs.Root value={active} onValueChange={change} className="space-y-4">
    <Tabs.List aria-label={label} className={`${sections.length === 4 ? "grid grid-cols-2 sm:flex" : "flex"} gap-1 rounded-xl border bg-card p-2 shadow-sm`}>
      {sections.map(section => <Tabs.Trigger key={section.id} value={section.id} className="min-h-11 min-w-0 flex-1 break-words rounded-lg px-2 py-2.5 text-center text-xs sm:px-3 sm:text-sm font-medium text-muted-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary data-[state=active]:bg-primary/10 data-[state=active]:text-primary">{section.label}</Tabs.Trigger>)}
    </Tabs.List>
    {sections.map(section => <Tabs.Content key={section.id} value={section.id} forceMount className="space-y-4 outline-none data-[state=inactive]:hidden">{section.content}</Tabs.Content>)}
  </Tabs.Root>;
}

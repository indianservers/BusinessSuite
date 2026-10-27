import { useState } from "react";
import { BookOpen, CheckCircle2, Layers, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { blueprints, blueprintCategories, type Blueprint } from "../data/blueprints";

export default function BlueprintCatalog({ busy, onSelect }: { busy: boolean; onSelect: (blueprint: Blueprint) => void }) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [limit, setLimit] = useState(12);
  const query = search.trim().toLowerCase();
  const visible = blueprints.filter(item => (!category || item.category === category)
    && [item.name, item.category, item.useWhen, item.outcome, ...item.task_titles].join(" ").toLowerCase().includes(query));
  const categoryTip = blueprintCategories.find(item => item.name === category)?.tip;

  return <section className="space-y-5" aria-label="Blueprint catalog">
    <div className="rounded-xl border bg-primary/5 p-5 sm:p-6">
      <div className="flex items-center gap-3"><Layers aria-hidden="true" className="h-6 w-6 text-primary" /><h3 className="text-xl font-semibold">Start with a proven plan</h3></div>
      <p className="mt-2 text-sm text-muted-foreground">{blueprints.length} editable blueprints across {blueprintCategories.length} categories. Choose a starting point, make it yours, and turn the checklist into project tasks.</p>
      <ol className="mt-5 grid gap-4 text-sm sm:grid-cols-3">
        <li><strong>1. Choose an outcome</strong><p className="mt-1 text-muted-foreground">Search the work you need to finish, then compare the checklist with your situation.</p></li>
        <li><strong>2. Tailor the plan</strong><p className="mt-1 text-muted-foreground">Edit instructions, add or remove tasks, reorder steps, and choose a destination project.</p></li>
        <li><strong>3. Make it actionable</strong><p className="mt-1 text-muted-foreground">Create the tasks, then assign owners, dates, and dependencies in your workspace.</p></li>
      </ol>
      <details className="mt-5 rounded-lg border bg-background p-3 text-sm">
        <summary className="cursor-pointer font-medium"><BookOpen aria-hidden="true" className="mr-2 inline h-4 w-4" />Ideas for getting the most from blueprints</summary>
        <div className="mt-3 space-y-2 text-muted-foreground">
          <p><strong className="text-foreground">Repeat work consistently.</strong> Use New employee onboarding once per hire, or Month-end close coordination once per reporting period. Add the person or period to your saved copy's name.</p>
          <p><strong className="text-foreground">Connect teams.</strong> Pair Sales handover to delivery with Project kickoff in the same customer project. Review overlapping tasks before creating another checklist.</p>
          <p><strong className="text-foreground">Build your playbook.</strong> Owners and admins can save a customized workspace copy, improve it after a retrospective, and reuse the improved version next time.</p>
          <p><strong className="text-foreground">Define done.</strong> Add your actual deliverables and approval criteria to the instructions. After creation, assign one accountable owner per task and attach evidence before completing it.</p>
          <p>Each use creates a new set of tasks. Dates, assignees, recurring schedules, and dependencies are set on the created tasks; checklist order does not create dependencies automatically.</p>
        </div>
      </details>
    </div>
    <div className="grid gap-3 sm:grid-cols-[2fr_1fr]">
      <div className="relative"><Search aria-hidden="true" className="absolute left-3 top-3.5 h-4 w-4 text-muted-foreground" /><Input className="h-11 pl-9" aria-label="Search blueprint catalog" placeholder="Search onboarding, launch, close, research…" value={search} onChange={event => { setSearch(event.target.value); setLimit(12); }} /></div>
      <select aria-label="Blueprint category" className="h-11 min-w-0 rounded-md border bg-background px-3 text-sm" value={category} onChange={event => { setCategory(event.target.value); setLimit(12); }}><option value="">All {blueprintCategories.length} categories</option>{blueprintCategories.map(item => <option key={item.name} value={item.name}>{item.name} ({blueprints.filter(blueprint => blueprint.category === item.name).length})</option>)}</select>
    </div>
    {categoryTip && <p className="rounded-lg border bg-muted/30 p-3 text-sm">{categoryTip}</p>}
    <p role="status" className="text-sm text-muted-foreground">{visible.length} matching blueprints · showing {Math.min(limit, visible.length)}</p>
    {!visible.length && <div className="rounded-xl border border-dashed p-6 text-center"><p>No blueprints match these filters.</p><Button className="mt-3" variant="outline" onClick={() => { setSearch(""); setCategory(""); setLimit(12); }}>Clear catalog filters</Button></div>}
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {visible.slice(0, limit).map(item => <article key={item.id} className="flex min-w-0 flex-col rounded-xl border bg-background p-5 transition-shadow hover:shadow-md">
        <p className="text-xs font-medium text-primary">{item.category}</p>
        <h4 className="mt-2 text-lg font-semibold">{item.name}</h4>
        <p className="mt-2 text-sm text-muted-foreground">{item.useWhen}</p>
        <p className="mt-3 text-sm"><strong>Outcome:</strong> {item.outcome}</p>
        <ul className="my-4 space-y-2 text-sm text-muted-foreground">{item.task_titles.slice(0, 3).map(title => <li key={title} className="flex gap-2"><CheckCircle2 aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-primary" />{title}</li>)}</ul>
        <p className="mb-3 text-xs text-muted-foreground">{item.task_titles.length} editable tasks · built-in blueprint</p>
        <Button variant="outline" className="mt-auto w-full" disabled={busy} onClick={() => onSelect(item)}>Preview and customize<span className="sr-only"> {item.name}</span></Button>
      </article>)}
    </div>
    {visible.length > limit && <div className="text-center"><Button variant="outline" onClick={() => setLimit(current => current + 12)}>Show more blueprints ({visible.length - limit} remaining)</Button></div>}
  </section>;
}

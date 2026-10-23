import GanttPage from "./GanttPage";
import { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  CalendarDays,
  CheckSquare,
  ChevronDown,
  Columns3,
  ClipboardList,
  FileText,
  Flag,
  LayoutList,
  MoreHorizontal,
  Package,
  Plus,
  Rocket,
  Search,
  Star,
  UserPlus,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type LaunchStatus = "To Do" | "In Progress" | "Blocked" | "Done";
type LaunchCategory = "Lead gen" | "Go to market" | "Product" | "Design" | "Enablement" | "Analytics";

type LaunchItem = {
  id: number;
  key: string;
  summary: string;
  status: LaunchStatus;
  assignee: string;
  category: LaunchCategory;
  type: "Task" | "Story" | "Milestone";
  dueDate: string;
};

const people = ["Maya Nair", "Dev Patel", "Isha Rao", "Nora Khan", "Rahul Shah", "Current User"];
const categories: LaunchCategory[] = ["Lead gen", "Go to market", "Product", "Design", "Enablement", "Analytics"];
const statuses: LaunchStatus[] = ["To Do", "In Progress", "Blocked", "Done"];

const seedItems: LaunchItem[] = [
  { id: 1, key: "MGT-90", summary: "Cold leads outreach strategy", status: "To Do", assignee: "Isha Rao", category: "Lead gen", type: "Story", dueDate: "2026-05-18" },
  { id: 2, key: "SAL-2", summary: "Webinar lead generation", status: "In Progress", assignee: "Dev Patel", category: "Lead gen", type: "Task", dueDate: "2026-05-20" },
  { id: 3, key: "SAL-3", summary: "Target customer research", status: "In Progress", assignee: "Maya Nair", category: "Lead gen", type: "Task", dueDate: "2026-05-16" },
  { id: 4, key: "MKT-7", summary: "Create sales collateral", status: "To Do", assignee: "Nora Khan", category: "Go to market", type: "Story", dueDate: "2026-05-23" },
  { id: 5, key: "PMM-22", summary: "Sales enablement deck", status: "In Progress", assignee: "Rahul Shah", category: "Go to market", type: "Task", dueDate: "2026-05-24" },
  { id: 6, key: "PMM-38", summary: "Create product demo", status: "In Progress", assignee: "Isha Rao", category: "Go to market", type: "Milestone", dueDate: "2026-05-27" },
  { id: 7, key: "DSN-14", summary: "Launch page prototype", status: "To Do", assignee: "Nora Khan", category: "Design", type: "Task", dueDate: "2026-05-22" },
  { id: 8, key: "ANL-11", summary: "Activation dashboard tracking", status: "Blocked", assignee: "Dev Patel", category: "Analytics", type: "Task", dueDate: "2026-05-29" },
];

const tabs = [
  { label: "Summary", icon: ClipboardList },
  { label: "List", icon: LayoutList },
  { label: "Board", icon: Columns3 },
  { label: "Calendar", icon: CalendarDays },
  { label: "Timeline", icon: Flag },
  { label: "Reports", icon: BarChart3 },
  { label: "Releases", icon: Rocket },
  { label: "Pages", icon: FileText },
];

export default function ProductLaunchPage() {
  const [items, setItems] = useState<LaunchItem[]>(() => {
    const stored = localStorage.getItem("karyaflow-product-launch-items");
    return stored ? JSON.parse(stored) : seedItems;
  });
  const [activeTab, setActiveTab] = useState("List");
  const [query, setQuery] = useState("");
  const [groupBy, setGroupBy] = useState<"Category" | "Status">("Category");

  useEffect(() => {
    localStorage.setItem("karyaflow-product-launch-items", JSON.stringify(items));
  }, [items]);

  const filteredItems = useMemo(() => {
    const value = query.trim().toLowerCase();
    if (!value) return items;
    return items.filter((item) => `${item.key} ${item.summary} ${item.status} ${item.assignee} ${item.category}`.toLowerCase().includes(value));
  }, [items, query]);

  const groupedItems = useMemo(() => {
    const groups = groupBy === "Category" ? categories : statuses;
    return groups.map((group) => ({
      group,
      items: filteredItems.filter((item) => groupBy === "Category" ? item.category === group : item.status === group),
    })).filter((group) => group.items.length);
  }, [filteredItems, groupBy]);

  const updateItem = (id: number, patch: Partial<LaunchItem>) => {
    setItems((current) => current.map((item) => item.id === id ? { ...item, ...patch } : item));
  };

  const createItem = (category: LaunchCategory) => {
    const nextId = Math.max(...items.map((item) => item.id)) + 1;
    setItems((current) => [
      ...current,
      {
        id: nextId,
        key: `LCH-${nextId + 100}`,
        summary: "New launch work item",
        status: "To Do",
        assignee: "Current User",
        category,
        type: "Task",
        dueDate: "2026-06-01",
      },
    ]);
  };

  const progress = Math.round((items.filter((item) => item.status === "Done").length / items.length) * 100);
  const onTrack = items.filter((item) => item.status !== "Blocked").length;

  return (
    <div className="min-h-screen bg-[#f6f8fb]">
      <header className="border-b bg-white px-5 py-4">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-md bg-amber-400 text-white"><Package className="h-5 w-5" /></span>
              <h1 className="text-2xl font-semibold text-slate-950">New Product Launch</h1>
              <Star className="h-5 w-5 text-slate-500" />
              <ChevronDown className="h-4 w-4 text-slate-500" />
            </div>
            <nav className="mt-4 flex gap-5 overflow-x-auto text-sm font-medium text-slate-600">
              {tabs.map((tab) => (
                <button
                  key={tab.label}
                  type="button"
                  onClick={() => setActiveTab(tab.label)}
                  className={`inline-flex shrink-0 items-center gap-1.5 border-b-2 pb-3 ${activeTab === tab.label ? "border-blue-600 text-blue-700" : "border-transparent hover:text-slate-950"}`}
                >
                  <tab.icon className="h-4 w-4" />
                  {tab.label}
                </button>
              ))}
              <button className="inline-flex items-center gap-1.5 pb-3" type="button">Shortcuts <ChevronDown className="h-3.5 w-3.5" /></button>
              <button className="inline-flex items-center gap-1.5 pb-3" type="button">More <ChevronDown className="h-3.5 w-3.5" /></button>
            </nav>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge className="bg-emerald-100 px-3 py-1.5 text-emerald-800 hover:bg-emerald-100">On track</Badge>
            <Button size="sm"><Rocket className="h-4 w-4" />Launch room</Button>
            <Button variant="ghost" size="icon"><MoreHorizontal className="h-4 w-4" /></Button>
          </div>
        </div>
      </header>

      <main className="space-y-4 p-5">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative w-full sm:w-72">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
              <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search list" className="pl-9" />
            </div>
            <AvatarStack />
            <Button variant="outline" size="icon" className="rounded-full"><UserPlus className="h-4 w-4" /></Button>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => setGroupBy(groupBy === "Category" ? "Status" : "Category")}>Group by: {groupBy}</Button>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-4">
          <Metric label="Launch progress" value={`${progress}%`} />
          <Metric label="Work items" value={items.length.toString()} />
          <Metric label="On track" value={onTrack.toString()} />
          <Metric label="Blocked" value={items.filter((item) => item.status === "Blocked").length.toString()} danger />
        </div>

        {activeTab === "Timeline" ? (
          <div className="space-y-3"><p className="text-sm text-muted-foreground">Live project tasks. Select the launch project below to plan its schedule.</p><GanttPage /></div>
        ) : activeTab === "List" ? (
          <Card className="overflow-hidden border-slate-300">
            <CardContent className="p-0">
              <div className="grid grid-cols-[3.5rem_1fr_10rem_12rem_10rem] items-center border-b bg-white px-4 py-3 text-sm font-semibold text-slate-600">
                <span><input type="checkbox" className="h-4 w-4" /></span>
                <span className="inline-flex items-center gap-2"><ChevronDown className="h-4 w-4" />Aa Summary</span>
                <span>Status</span>
                <span>@ Assignee</span>
                <span>Category</span>
              </div>
              {groupedItems.map((group) => (
                <div key={group.group} className="border-b last:border-b-0">
                  <div className="flex items-center gap-2 bg-slate-50 px-4 py-3 text-sm font-semibold">
                    <ChevronDown className="h-4 w-4" />
                    <Badge variant="outline" className="bg-slate-200 text-base text-slate-900 hover:bg-slate-200">{group.group}</Badge>
                    <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs text-slate-600">{group.items.length}</span>
                  </div>
                  {group.items.map((item) => (
                    <LaunchRow key={item.id} item={item} onUpdate={updateItem} />
                  ))}
                  {groupBy === "Category" ? (
                    <button type="button" onClick={() => createItem(group.group as LaunchCategory)} className="flex w-full items-center gap-2 px-16 py-3 text-left text-sm text-slate-600 hover:bg-blue-50">
                      <Plus className="h-4 w-4" /> Create
                    </button>
                  ) : null}
                </div>
              ))}
            </CardContent>
          </Card>
        ) : activeTab === "Board" ? (
          <div className="grid gap-4 xl:grid-cols-4">
            {statuses.map((status) => (
              <div key={status} className="min-h-[28rem] rounded-lg bg-slate-100 p-3">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="text-sm font-semibold uppercase text-slate-600">{status}</h2>
                  <Badge variant="outline">{items.filter((item) => item.status === status).length}</Badge>
                </div>
                <div className="space-y-3">
                  {filteredItems.filter((item) => item.status === status).map((item) => (
                    <button key={item.id} type="button" onClick={() => updateItem(item.id, { status: nextStatus(item.status) })} className="w-full rounded-md border bg-white p-3 text-left shadow-sm hover:border-blue-400">
                      <p className="font-medium">{item.summary}</p>
                      <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                        <span>{item.key}</span>
                        <Badge className={categoryColor(item.category)}>{item.category}</Badge>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <Placeholder tab={activeTab} items={filteredItems} />
        )}
      </main>
    </div>
  );
}

function LaunchRow({ item, onUpdate }: { item: LaunchItem; onUpdate: (id: number, patch: Partial<LaunchItem>) => void }) {
  return (
    <div className="grid grid-cols-[3.5rem_1fr_10rem_12rem_10rem] items-center border-t bg-white px-4 py-3 text-sm hover:bg-slate-50">
      <span><input type="checkbox" className="h-4 w-4" /></span>
      <div className="flex min-w-0 items-center gap-3">
        <ChevronDown className="h-4 w-4 text-slate-500" />
        <span className={item.type === "Milestone" ? "text-amber-600" : "text-blue-600"}><CheckSquare className="h-4 w-4" /></span>
        <span className="font-medium text-slate-500">{item.key}</span>
        <Input value={item.summary} onChange={(event) => onUpdate(item.id, { summary: event.target.value })} className="h-8 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0" />
      </div>
      <select value={item.status} onChange={(event) => onUpdate(item.id, { status: event.target.value as LaunchStatus })} className="w-32 rounded border bg-white px-2 py-1 text-xs font-semibold text-blue-700">
        {statuses.map((status) => <option key={status}>{status}</option>)}
      </select>
      <div className="flex items-center gap-2">
        <Avatar name={item.assignee} />
        <select value={item.assignee} onChange={(event) => onUpdate(item.id, { assignee: event.target.value })} className="w-32 rounded border bg-white px-2 py-1 text-xs text-slate-600">
          {people.map((person) => <option key={person}>{person}</option>)}
        </select>
      </div>
      <select value={item.category} onChange={(event) => onUpdate(item.id, { category: event.target.value as LaunchCategory })} className={`w-32 rounded border px-2 py-1 text-xs font-semibold ${categoryColor(item.category)}`}>
        {categories.map((category) => <option key={category}>{category}</option>)}
      </select>
    </div>
  );
}

function AvatarStack() {
  return (
    <div className="flex -space-x-2">
      {people.slice(0, 4).map((person) => <Avatar key={person} name={person} />)}
      <span className="flex h-9 w-9 items-center justify-center rounded-full border-2 border-white bg-slate-100 text-sm font-semibold text-slate-600">+3</span>
    </div>
  );
}

function Avatar({ name }: { name: string }) {
  const initials = name.split(" ").map((part) => part[0]).join("").slice(0, 2);
  return <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 border-white bg-blue-100 text-xs font-bold text-blue-700">{initials}</span>;
}

function Metric({ label, value, danger = false }: { label: string; value: string; danger?: boolean }) {
  return (
    <div className="rounded-lg border bg-white p-4">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className={danger ? "mt-1 text-2xl font-semibold text-red-600" : "mt-1 text-2xl font-semibold text-slate-950"}>{value}</p>
    </div>
  );
}

function Placeholder({ tab, items }: { tab: string; items: LaunchItem[] }) {
  return (
    <Card>
      <CardContent className="grid gap-3 p-5 md:grid-cols-3">
        {items.slice(0, 6).map((item) => (
          <div key={item.id} className="rounded-lg border bg-white p-4">
            <Badge className={categoryColor(item.category)}>{item.category}</Badge>
            <h3 className="mt-3 font-semibold">{item.summary}</h3>
            <p className="mt-2 text-sm text-slate-500">{tab} view item due {item.dueDate}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function categoryColor(category: LaunchCategory) {
  const colors: Record<LaunchCategory, string> = {
    "Lead gen": "bg-emerald-100 text-emerald-800 hover:bg-emerald-100",
    "Go to market": "bg-amber-100 text-amber-800 hover:bg-amber-100",
    Product: "bg-blue-100 text-blue-800 hover:bg-blue-100",
    Design: "bg-sky-100 text-sky-800 hover:bg-sky-100",
    Enablement: "bg-orange-100 text-orange-800 hover:bg-orange-100",
    Analytics: "bg-purple-100 text-purple-800 hover:bg-purple-100",
  };
  return colors[category];
}

function nextStatus(status: LaunchStatus): LaunchStatus {
  const index = statuses.indexOf(status);
  return statuses[(index + 1) % statuses.length];
}

import GanttPage from "./GanttPage";
import { useMemo, useState } from "react";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  closestCorners,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { AppWindow, AtSign, Bot, CalendarDays, Check, ChevronDown, Figma, FileText, Github, GripVertical, Layers3, Link2, List, MessageSquare, Plus, Search, Sparkles, Target, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { formatDate, statusColor } from "@/lib/utils";
import { workGoals, WorkIssues, teamMembers, type WorkIssue } from "../workData";

const tabs = ["Summary", "Board", "List", "Calendar", "Timeline", "Forms", "Pages", "Issues", "Reports", "Shortcuts", "Apps"];
const boardColumns = ["To Do", "Drafting", "In Review", "Approved"] as const;
const statusMap: Record<string, string> = {
  Backlog: "To Do",
  Selected: "Drafting",
  "In Progress": "Drafting",
  "In Review": "In Review",
  Done: "Approved",
};

const contextAssets = [
  { icon: FileText, name: "Confluence PRD", detail: "Client approval requirements" },
  { icon: Figma, name: "Figma design", detail: "Portal approval screens" },
  { icon: Github, name: "GitHub branch", detail: "feature/client-approvals" },
  { icon: AppWindow, name: "Support tickets", detail: "4 related customer signals" },
];

const suggestedWork = [
  { key: "KAR-189", title: "Create approval audit timeline", selected: true, assignee: "Isha Rao", reason: "Frontend ownership and availability" },
  { key: "KAR-190", title: "Add rejection reason validation", selected: true, assignee: "Dev Patel", reason: "API validation expertise" },
  { key: "KAR-191", title: "Draft customer rollout checklist", selected: true, assignee: "Rahul Shah", reason: "Analyst and launch support" },
  { key: "KAR-192", title: "Prepare QA regression pack", selected: false, assignee: "Nora Khan", reason: "Quality lead for calendar and approval flows" },
];

type WorkItem = WorkIssue & { boardStatus: string };

export default function ImpactWorkHubPage() {
  const [activeTab, setActiveTab] = useState("List");
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<WorkItem[]>(() => WorkIssues.map((issue) => ({ ...issue, boardStatus: statusMap[issue.status] || "To Do" })));
  const [activeId, setActiveId] = useState<number | null>(null);
  const [aiItems, setAiItems] = useState(suggestedWork);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));
  const activeItem = items.find((item) => item.id === activeId);
  const filtered = useMemo(() => items.filter((item) => [item.key, item.summary, item.assignee, item.epic].join(" ").toLowerCase().includes(query.toLowerCase())), [items, query]);
  const goal = workGoals[0];

  const onDragStart = (event: DragStartEvent) => setActiveId(event.active.id as number);
  const onDragEnd = (event: DragEndEvent) => {
    setActiveId(null);
    if (!event.over) return;
    const target = String(event.over.id).startsWith("column:") ? String(event.over.id).replace("column:", "") : items.find((item) => item.id === event.over?.id)?.boardStatus;
    if (!target) return;
    setItems((rows) => rows.map((item) => (item.id === event.active.id ? { ...item, boardStatus: target } : item)));
  };

  const createSuggested = () => {
    const next = aiItems.filter((item) => item.selected);
    setItems((rows) => [
      ...next.map((item, index) => ({
        id: rows.length + index + 1,
        key: item.key,
        type: "Task" as const,
        summary: item.title,
        status: "Selected" as const,
        boardStatus: "To Do",
        priority: "Medium" as const,
        assignee: item.assignee,
        reporter: "KaryaFlow AI",
        storyPoints: 3,
        sprint: "Sprint 24",
        epic: "Client Experience",
        release: "v2.3",
        dueDate: "2026-05-24",
      })),
      ...rows,
    ]);
  };

  return (
    <div className="space-y-6">
      <div className="rounded-xl border bg-card">
        <div className="flex flex-col gap-4 border-b p-5 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-violet-100 text-violet-700"><Sparkles className="h-5 w-5" /></div>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">The Next Big Thing</h1>
              <p className="text-sm text-muted-foreground">Align strategy, teams, tasks, tickets, and assets before work starts.</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <AvatarStack names={teamMembers.map((member) => member.name)} />
            <Button variant="outline"><Users className="h-4 w-4" />Share</Button>
            <Button><Plus className="h-4 w-4" />Create</Button>
          </div>
        </div>
        <div className="flex gap-1 overflow-x-auto px-5">
          {tabs.map((tab) => (
            <button key={tab} type="button" onClick={() => setActiveTab(tab)} className={`border-b-2 px-3 py-3 text-sm font-medium ${activeTab === tab ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}>
              {tab}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_24rem]">
        <div className="space-y-4">
          <Card>
            <CardContent className="flex flex-col gap-3 p-3 md:flex-row md:items-center">
              <div className="flex min-w-0 flex-1 items-center gap-2 rounded-md border px-3 py-2">
                <Search className="h-4 w-4 text-muted-foreground" />
                <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search work, assignees, goals..." className="border-0 p-0 shadow-none focus-visible:ring-0" />
              </div>
              <Button variant="outline"><List className="h-4 w-4" />List</Button>
              <Button variant="outline"><Layers3 className="h-4 w-4" />Group</Button>
              <Button variant="outline">Sort<ChevronDown className="h-4 w-4" /></Button>
            </CardContent>
          </Card>

          <GoalAlignment goal={goal} items={items} />
          <AiPlanner items={aiItems} setItems={setAiItems} onCreate={createSuggested} />

          {activeTab === "Timeline" ? (
            <div className="space-y-3"><p className="text-sm text-muted-foreground">Live project tasks. Select a project below to plan its schedule.</p><GanttPage /></div>
          ) : activeTab === "Board" ? (
            <DndContext sensors={sensors} collisionDetection={closestCorners} onDragStart={onDragStart} onDragEnd={onDragEnd}>
              <div className="grid gap-4 xl:grid-cols-4">
                {boardColumns.map((column) => <BoardColumn key={column} column={column} items={filtered.filter((item) => item.boardStatus === column)} />)}
              </div>
              <DragOverlay>{activeItem ? <WorkCard item={activeItem} overlay /> : null}</DragOverlay>
            </DndContext>
          ) : (
            <WorkList items={filtered} setItems={setItems} />
          )}
        </div>

        <div className="space-y-4">
          <ContextPanel />
          <IssueDetail item={items[1]} />
        </div>
      </div>
    </div>
  );
}

function GoalAlignment({ goal, items }: { goal: (typeof workGoals)[number]; items: WorkItem[] }) {
  const linked = items.filter((item) => item.epic === "Client Experience");
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between">
        <div>
          <CardTitle className="flex items-center gap-2"><Target className="h-5 w-5 text-green-600" />Develop and Launch Customer Portal</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">Contributing work is connected to goals, owners, teams, risks, and decisions.</p>
        </div>
        <Badge className={statusColor(goal.status)}>{goal.status}</Badge>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 md:grid-cols-[1fr_14rem]">
          <div className="space-y-2">
            {linked.map((item) => (
              <div key={item.key} className="grid gap-3 rounded-lg border p-3 md:grid-cols-[7rem_1fr_7rem_7rem] md:items-center">
                <Badge variant="outline">{item.key}</Badge>
                <div><p className="font-medium">{item.summary}</p><p className="text-sm text-muted-foreground">{item.epic}</p></div>
                <Badge className={statusColor(item.boardStatus)}>{item.boardStatus}</Badge>
                <span className="text-sm text-muted-foreground">{item.assignee}</span>
              </div>
            ))}
          </div>
          <div className="rounded-lg border bg-muted/30 p-4">
            <p className="text-sm text-muted-foreground">Goal confidence</p>
            <p className="mt-1 text-3xl font-semibold">{goal.progress}</p>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-green-500" style={{ width: goal.progress }} />
            </div>
            <p className="mt-3 text-sm text-muted-foreground">Owner: {goal.owner}</p>
            <p className="text-sm text-muted-foreground">Target: {formatDate(goal.target)}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function AiPlanner({ items, setItems, onCreate }: { items: typeof suggestedWork; setItems: (items: typeof suggestedWork) => void; onCreate: () => void }) {
  return (
    <Card className="border-blue-200 bg-blue-50/40">
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2 text-base"><Bot className="h-5 w-5 text-blue-700" />AI Work Planner</CardTitle>
        <Badge variant="outline">Verify results</Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">Breaks goals into actionable work, chooses owners from skills/capacity, and links relevant context.</p>
        {items.map((item) => (
          <button key={item.key} type="button" className="grid w-full gap-3 rounded-lg border bg-background p-3 text-left md:grid-cols-[2rem_7rem_1fr_9rem] md:items-center" onClick={() => setItems(items.map((row) => row.key === item.key ? { ...row, selected: !row.selected } : row))}>
            <span className={`flex h-5 w-5 items-center justify-center rounded border ${item.selected ? "border-blue-600 bg-blue-600 text-white" : "bg-background"}`}>{item.selected ? <Check className="h-3 w-3" /> : null}</span>
            <span className="font-semibold">{item.key}</span>
            <span><span className="font-medium">{item.title}</span><span className="block text-xs text-muted-foreground">{item.reason}</span></span>
            <Badge variant="outline">{item.assignee}</Badge>
          </button>
        ))}
        <div className="flex justify-end gap-2"><Button variant="outline">Refine prompt</Button><Button onClick={onCreate}>Create selected</Button></div>
      </CardContent>
    </Card>
  );
}

function WorkList({ items, setItems }: { items: WorkItem[]; setItems: (items: WorkItem[]) => void }) {
  const cycleStatus = (item: WorkItem) => {
    const next = { "To Do": "Drafting", Drafting: "In Review", "In Review": "Approved", Approved: "To Do" }[item.boardStatus] || "To Do";
    setItems(items.map((row) => row.id === item.id ? { ...row, boardStatus: next } : row));
  };
  return (
    <Card>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr><th className="px-4 py-3">Type</th><th className="px-4 py-3">Priority</th><th className="px-4 py-3">Name</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Assignee</th><th className="px-4 py-3">Due</th></tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-t hover:bg-muted/30">
                  <td className="px-4 py-3"><Badge variant="outline">{item.type}</Badge></td>
                  <td className="px-4 py-3"><Badge className={statusColor(item.priority)}>{item.priority}</Badge></td>
                  <td className="px-4 py-3"><p className="font-medium">{item.summary}</p><p className="text-xs text-muted-foreground">{item.key} / {item.epic}</p></td>
                  <td className="px-4 py-3"><Button variant="outline" size="sm" onClick={() => cycleStatus(item)}>{item.boardStatus}</Button></td>
                  <td className="px-4 py-3"><AvatarName name={item.assignee} /></td>
                  <td className="px-4 py-3 text-muted-foreground">{formatDate(item.dueDate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function BoardColumn({ column, items }: { column: string; items: WorkItem[] }) {
  const { setNodeRef, isOver } = useDroppable({ id: `column:${column}` });
  return (
    <section ref={setNodeRef} className={`rounded-xl border bg-muted/35 p-3 ${isOver ? "ring-2 ring-primary/50" : ""}`}>
      <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">{column}</h2><Badge variant="outline">{items.length}</Badge></div>
      <SortableContext items={items.map((item) => item.id)} strategy={verticalListSortingStrategy}>
        <div className="min-h-64 space-y-3">
          {items.map((item) => <WorkCard key={item.id} item={item} />)}
        </div>
      </SortableContext>
    </section>
  );
}

function WorkCard({ item, overlay = false }: { item: WorkItem; overlay?: boolean }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.id });
  return (
    <article ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition }} className={`rounded-lg border bg-card p-3 shadow-sm ${isDragging ? "opacity-50" : ""} ${overlay ? "w-72 shadow-xl" : ""}`}>
      <div className="flex gap-2">
        <button type="button" className="rounded p-1 text-muted-foreground hover:bg-muted" {...attributes} {...listeners}><GripVertical className="h-4 w-4" /></button>
        <div><p className="font-medium">{item.summary}</p><p className="text-xs text-muted-foreground">{item.key} / {item.assignee}</p></div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2"><Badge className={statusColor(item.priority)}>{item.priority}</Badge><Badge variant="outline">{item.storyPoints} pts</Badge></div>
    </article>
  );
}

function ContextPanel() {
  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Link2 className="h-5 w-5 text-primary" />Connected Context</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {contextAssets.map((asset) => <div key={asset.name} className="flex gap-3 rounded-lg border bg-muted/30 p-3"><asset.icon className="h-5 w-5 text-primary" /><div><p className="font-medium">{asset.name}</p><p className="text-sm text-muted-foreground">{asset.detail}</p></div></div>)}
      </CardContent>
    </Card>
  );
}

function IssueDetail({ item }: { item: WorkItem }) {
  return (
    <Card className="bg-slate-950 text-slate-100">
      <CardHeader><CardTitle>{item.summary}</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm"><AtSign className="h-4 w-4" />Attach</Button>
          <Button variant="secondary" size="sm"><Link2 className="h-4 w-4" />Link issue</Button>
          <Button variant="secondary" size="sm"><Figma className="h-4 w-4" />Figma</Button>
          <Button variant="secondary" size="sm"><Github className="h-4 w-4" />GitHub</Button>
        </div>
        <div><p className="text-sm font-semibold">Description</p><p className="mt-2 text-sm text-slate-300">The team is on track, but approval work depends on API validation and rollout communications. Keep linked issues visible before moving to approved.</p></div>
        <div className="rounded-lg border border-slate-700 p-3">
          <p className="text-sm font-semibold">Details</p>
          <div className="mt-3 grid gap-2 text-sm">
            <Detail label="Assignee" value={item.assignee} />
            <Detail label="Sprint" value={item.sprint} />
            <Detail label="Priority" value={item.priority} />
            <Detail label="Story points" value={`${item.storyPoints}`} />
            <Detail label="Release" value={item.release} />
          </div>
        </div>
        <div className="space-y-2"><p className="text-sm font-semibold">Activity</p><div className="flex gap-3 text-sm text-slate-300"><AvatarDot name="Colin Chu" /><p><span className="font-medium text-white">Colin Chu</span> linked dependency KAR-103 and added rollout notes.</p></div></div>
      </CardContent>
    </Card>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div className="flex justify-between gap-4"><span className="text-slate-400">{label}</span><span>{value}</span></div>;
}

function AvatarStack({ names }: { names: string[] }) {
  return <div className="flex -space-x-2">{names.slice(0, 4).map((name) => <AvatarDot key={name} name={name} />)}<span className="flex h-8 w-8 items-center justify-center rounded-full border bg-muted text-xs">+{Math.max(0, names.length - 4)}</span></div>;
}

function AvatarName({ name }: { name: string }) {
  return <div className="flex items-center gap-2"><AvatarDot name={name} /><span>{name}</span></div>;
}

function AvatarDot({ name }: { name: string }) {
  const initials = name.split(" ").map((part) => part[0]).join("").slice(0, 2);
  return <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 border-background bg-primary text-xs font-semibold text-primary-foreground">{initials}</span>;
}


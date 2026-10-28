import {
  cloneElement,
  useEffect,
  useId,
  useState,
  type ReactElement,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Save,
  Copy,
  Eye,
  Send,
  CalendarClock,
  RefreshCw,
} from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";

type Row = Record<string, any>;
type Level = "beginner" | "intermediate" | "advanced";
type Criterion = {
  key: string;
  label: string;
  points: number;
  description: string;
};
type Variant = {
  title: string;
  instructions: string;
  deliverables: string;
  rubric: Criterion[];
};
type Step = {
  key: string;
  week: number;
  due_day: number;
  depends_on: string[];
  variants: Record<Level, Variant>;
};
type Pack = {
  id?: number;
  project_id: number;
  name: string;
  description: string;
  steps: Step[];
  is_active: boolean;
  version?: number;
};
type Assignment = {
  task_id: number;
  user_id: number;
  employee_id: number;
  intern: string;
  task: string;
  status: string;
  due_date: string | null;
};
const root = "/interns-hub/management/learning";
const levels: Level[] = ["beginner", "intermediate", "advanced"];
const inputClass =
  "w-full rounded-md border border-input bg-background px-3 py-2 text-sm";
const panel = "rounded-xl border bg-card p-4 space-y-4";
const today = () => new Date().toLocaleDateString("en-CA");
const keyOf = (r: Assignment) => `${r.task_id}:${r.user_id}`;
function Field({
  label,
  children,
}: {
  label: string;
  children: ReactElement<{ id?: string }>;
}) {
  const id = useId();
  return (
    <div className="grid gap-2 text-sm">
      <label htmlFor={id} className="font-medium">
        {label}
      </label>
      {cloneElement(children, { id })}
    </div>
  );
}
function newStep(index: number): Step {
  return {
    key: `week_${index}`,
    week: index,
    due_day: 4,
    depends_on: [],
    variants: Object.fromEntries(
      levels.map((level) => [
        level,
        {
          title: `${level[0].toUpperCase() + level.slice(1)} weekly assignment`,
          instructions:
            level === "beginner"
              ? "Follow the provided example and explain each step."
              : level === "intermediate"
                ? "Complete the assignment independently and explain your decisions."
                : "Extend the solution, consider edge cases and explain your trade-offs.",
          deliverables:
            "Submit your work, evidence links and a brief explanation.",
          rubric: [
            {
              key: "correctness",
              label: "Correctness",
              points: 50,
              description: "Meets the stated requirements",
            },
            {
              key: "quality",
              label: "Quality",
              points: 30,
              description: "Clear, complete and well-structured work",
            },
            {
              key: "explanation",
              label: "Explanation",
              points: 20,
              description: "Explains the approach and evidence",
            },
          ],
        },
      ]),
    ) as Record<Level, Variant>,
  };
}

export default function InternTaskProgramsPanel({
  options,
}: {
  options?: Row;
}) {
  const qc = useQueryClient();
  const [tab, setTab] = useState("Task packs");
  const [project, setProject] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [edit, setEdit] = useState<Pack | null>(null);
  const [level, setLevel] = useState<Level>("beginner");
  const [packId, setPackId] = useState("");
  const [batchId, setBatchId] = useState("");
  const [startDate, setStartDate] = useState(today);
  const [reviewer, setReviewer] = useState("");
  const [selection, setSelection] = useState<Record<number, Level>>({});
  const [packPreview, setPackPreview] = useState<Row | null>(null);
  const [packPreviewKey, setPackPreviewKey] = useState("");
  const [packRequest, setPackRequest] = useState(() => crypto.randomUUID());
  const [page, setPage] = useState(1);
  const [chosen, setChosen] = useState<Record<string, Assignment>>({});
  const [deadline, setDeadline] = useState("");
  const [reason, setReason] = useState("");
  const [deadlinePreview, setDeadlinePreview] = useState<Row | null>(null);
  const [deadlinePreviewKey, setDeadlinePreviewKey] = useState("");
  const [deadlineRequest, setDeadlineRequest] = useState(() =>
    crypto.randomUUID(),
  );
  const queryPrefix = ["intern-management", "task-programs"];
  const packs = useQuery<Pack[]>({
    queryKey: [...queryPrefix, "packs", project],
    queryFn: async () =>
      (await api.get(root + "/packs", { params: { project_id: project } }))
        .data,
    enabled: !!project,
  });
  const roster = useQuery<{
    total: number;
    items: { id: number; name: string; code: string }[];
  }>({
    queryKey: [...queryPrefix, "roster", batchId],
    queryFn: async () =>
      (await api.get(`${root}/batches/${batchId}/recipients`)).data,
    enabled: !!batchId && tab === "Assign pack",
  });
  const assignments = useQuery<{ total: number; items: Assignment[] }>({
    queryKey: [...queryPrefix, "assignments", project, batchId, page],
    queryFn: async () =>
      (
        await api.get(root + "/assignments", {
          params: { project_id: project, batch_id: batchId || undefined, page },
        })
      ).data,
    enabled: !!project && tab === "Extend deadlines",
  });
  const history = useQuery<{ total: number; items: Row[] }>({
    queryKey: [...queryPrefix, "deadline-history", project],
    queryFn: async () =>
      (
        await api.get(root + "/deadlines/history", {
          params: { project_id: project },
        })
      ).data,
    enabled: !!project && tab === "Extend deadlines",
  });
  const runs = useQuery<{ total: number; items: Row[] }>({
    queryKey: [...queryPrefix, "runs", project],
    queryFn: async () =>
      (await api.get(root + "/runs", { params: { project_id: project } })).data,
    enabled: !!project && tab === "Assign pack",
  });
  const pack = packs.data?.find((p) => String(p.id) === packId);
  const publishBody = {
    batch_id: Number(batchId),
    pack_version: pack?.version,
    start_date: startDate,
    reviewer_user_id: Number(reviewer),
    levels: Object.fromEntries(
      levels.map((l) => [
        l,
        Object.entries(selection)
          .filter(([, v]) => v === l)
          .map(([id]) => Number(id)),
      ]),
    ),
    request_key: packRequest,
  };
  const publishKey = JSON.stringify(publishBody);
  const deadlineBody = {
    project_id: Number(project),
    due_date: deadline,
    reason,
    assignments: Object.values(chosen).map((a) => ({
      task_id: a.task_id,
      user_id: a.user_id,
      expected_due_date: a.due_date,
    })),
    request_key: deadlineRequest,
  };
  const deadlineKey = JSON.stringify(deadlineBody);
  useEffect(() => {
    setPackPreview(null);
    setPackPreviewKey("");
    setPackRequest(crypto.randomUUID());
  }, [project, packId, batchId, startDate, reviewer, selection]);
  useEffect(() => {
    setDeadlinePreview(null);
    setDeadlinePreviewKey("");
    setDeadlineRequest(crypto.randomUUID());
  }, [project, chosen, deadline, reason]);
  useEffect(() => {
    setEdit(null);
    setPackId("");
    setChosen({});
    setPage(1);
  }, [project]);
  useEffect(() => {
    setSelection({});
    setChosen({});
    setPage(1);
  }, [batchId]);
  async function refresh() {
    await qc.invalidateQueries({ queryKey: queryPrefix });
    await qc.invalidateQueries({ queryKey: ["pms-my-assignments"] });
    await qc.invalidateQueries({ queryKey: ["pms-work"] });
  }
  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setMessage("");
    try {
      await action();
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      const text =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail
                .map((d: Row) => `${d.loc?.slice(-1)[0]}: ${d.msg}`)
                .join("; ")
            : "Could not complete the action. Check your fields and permissions.";
      setMessage(text);
      toast({
        title: "Action not completed",
        description: text,
        variant: "destructive",
      });
    } finally {
      setBusy(false);
    }
  }
  function changeStep(index: number, changes: Partial<Step>) {
    if (edit)
      setEdit({
        ...edit,
        steps: edit.steps.map((s, i) =>
          i === index ? { ...s, ...changes } : s,
        ),
      });
  }
  function changeVariant(index: number, changes: Partial<Variant>) {
    if (edit)
      changeStep(index, {
        variants: {
          ...edit.steps[index].variants,
          [level]: { ...edit.steps[index].variants[level], ...changes },
        },
      });
  }
  function toggle(row: Assignment, checked: boolean) {
    setChosen((current) => {
      const next = { ...current };
      if (checked) next[keyOf(row)] = row;
      else delete next[keyOf(row)];
      return next;
    });
  }
  const selectedCount = Object.keys(chosen).length;
  return (
    <section className="space-y-4" aria-label="Intern task programs">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">
            Task packs & deadline extensions
          </h2>
          <p className="text-sm text-muted-foreground">
            Plan weekly work by skill level and manage individual assignment
            deadlines.
          </p>
        </div>
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => void run(refresh)}
        >
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh programs
        </Button>
      </div>
      <Field label="Program PMS project">
        <select
          className={inputClass}
          value={project}
          onChange={(e) => setProject(e.target.value)}
        >
          <option value="">Choose a project</option>
          {options?.projects
            ?.filter((p: Row) => p.can_assign)
            .map((p: Row) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
        </select>
      </Field>
      <div
        className="flex flex-wrap gap-2"
        role="tablist"
        aria-label="Task program tools"
      >
        {["Task packs", "Assign pack", "Extend deadlines"].map((name) => (
          <Button
            key={name}
            role="tab"
            aria-selected={tab === name}
            variant={tab === name ? "default" : "outline"}
            onClick={() => setTab(name)}
          >
            {name}
          </Button>
        ))}
      </div>
      {message && (
        <p role="status" className="rounded border p-3 text-sm">
          {message}
        </p>
      )}
      {packs.isError && (
        <p role="alert">
          Unable to load task packs. Refresh or check your project access.
        </p>
      )}
      {!project ? (
        <p className="text-sm text-muted-foreground">
          Choose a PMS project to manage packs and deadlines.
        </p>
      ) : (
        <>
          {tab === "Task packs" && (
            <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
              <aside className={panel}>
                <Button
                  onClick={() =>
                    setEdit({
                      project_id: Number(project),
                      name: "",
                      description: "",
                      steps: [newStep(1)],
                      is_active: true,
                    })
                  }
                >
                  <Plus className="mr-2 h-4 w-4" />
                  New task pack
                </Button>
                {packs.data?.map((p) => (
                  <button
                    key={p.id}
                    className="block w-full rounded border p-3 text-left text-sm hover:bg-muted"
                    onClick={() => setEdit(structuredClone(p))}
                  >
                    <strong className="block">{p.name}</strong>
                    <span className="text-xs text-muted-foreground">
                      v{p.version} · {p.steps.length} steps ·{" "}
                      {p.is_active ? "Active" : "Archived"}
                    </span>
                  </button>
                ))}
                {packs.data?.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    Create your first reusable pack.
                  </p>
                )}
              </aside>
              <div className={panel}>
                {!edit ? (
                  <p className="text-sm text-muted-foreground">
                    Select a pack to edit. Published assignments keep their
                    original instructions and rubric.
                  </p>
                ) : (
                  <form
                    className="space-y-4"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void run(async () => {
                        const { id, ...data } = edit;
                        const response = await api.request({
                          method: id ? "put" : "post",
                          url: root + `/packs${id ? `/${id}` : ""}`,
                          data,
                        });
                        setEdit(response.data);
                        await refresh();
                        setMessage(
                          "Task pack saved. You can now assign it to a batch.",
                        );
                      });
                    }}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h3 className="font-semibold">
                        {edit.id ? "Edit task pack" : "New task pack"}
                      </h3>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() =>
                          setEdit({
                            ...edit,
                            id: undefined,
                            version: undefined,
                            name: `${edit.name} copy`.slice(0, 160),
                          })
                        }
                      >
                        <Copy className="mr-2 h-4 w-4" />
                        Duplicate pack
                      </Button>
                    </div>
                    <Field label="Pack name">
                      <Input
                        required
                        maxLength={160}
                        value={edit.name}
                        onChange={(e) =>
                          setEdit({ ...edit, name: e.target.value })
                        }
                      />
                    </Field>
                    <Field label="Pack description">
                      <textarea
                        className={inputClass}
                        maxLength={2000}
                        value={edit.description}
                        onChange={(e) =>
                          setEdit({ ...edit, description: e.target.value })
                        }
                      />
                    </Field>
                    <div
                      className="flex flex-wrap gap-2"
                      role="group"
                      aria-label="Edit skill variant"
                    >
                      {levels.map((l) => (
                        <Button
                          type="button"
                          key={l}
                          variant={l === level ? "default" : "outline"}
                          aria-pressed={l === level}
                          onClick={() => setLevel(l)}
                        >
                          {l[0].toUpperCase() + l.slice(1)}
                        </Button>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Each step has three variants. Dates and dependencies apply
                      to all levels. Day 0 is the pack start day; week 2 begins
                      seven days later.
                    </p>
                    {edit.steps.map((step, index) => {
                      const variant = step.variants[level];
                      return (
                        <fieldset
                          key={index}
                          className="space-y-4 rounded-lg border p-4"
                        >
                          <legend className="px-2 font-semibold">
                            Step {index + 1} · {level}
                          </legend>
                          <div className="grid gap-3 sm:grid-cols-3">
                            <Field label={`Step ${index + 1} key`}>
                              <Input
                                required
                                pattern="[a-z][a-z0-9_]{0,39}"
                                value={step.key}
                                onChange={(e) => {
                                  const previous = step.key;
                                  setEdit({
                                    ...edit,
                                    steps: edit.steps.map((s, i) =>
                                      i === index
                                        ? { ...s, key: e.target.value }
                                        : {
                                            ...s,
                                            depends_on: s.depends_on.map((k) =>
                                              k === previous
                                                ? e.target.value
                                                : k,
                                            ),
                                          },
                                    ),
                                  });
                                }}
                              />
                            </Field>
                            <Field label={`Step ${index + 1} week`}>
                              <Input
                                required
                                type="number"
                                min={1}
                                max={52}
                                value={step.week}
                                onChange={(e) =>
                                  changeStep(index, {
                                    week: Number(e.target.value),
                                  })
                                }
                              />
                            </Field>
                            <Field label={`Step ${index + 1} due day (0–6)`}>
                              <Input
                                required
                                type="number"
                                min={0}
                                max={6}
                                value={step.due_day}
                                onChange={(e) =>
                                  changeStep(index, {
                                    due_day: Number(e.target.value),
                                  })
                                }
                              />
                            </Field>
                          </div>
                          <Field label={`Step ${index + 1} title`}>
                            <Input
                              required
                              maxLength={180}
                              value={variant.title}
                              onChange={(e) =>
                                changeVariant(index, { title: e.target.value })
                              }
                            />
                          </Field>
                          <Field label={`Step ${index + 1} instructions`}>
                            <textarea
                              required
                              rows={4}
                              maxLength={5000}
                              className={inputClass}
                              value={variant.instructions}
                              onChange={(e) =>
                                changeVariant(index, {
                                  instructions: e.target.value,
                                })
                              }
                            />
                          </Field>
                          <Field label={`Step ${index + 1} deliverables`}>
                            <textarea
                              required
                              rows={3}
                              maxLength={3000}
                              className={inputClass}
                              value={variant.deliverables}
                              onChange={(e) =>
                                changeVariant(index, {
                                  deliverables: e.target.value,
                                })
                              }
                            />
                          </Field>
                          {index > 0 && (
                            <div className="space-y-2 text-sm">
                              <p className="font-medium">
                                Requires approval of your own earlier
                                assignments
                              </p>
                              {edit.steps.slice(0, index).map((s) => (
                                <label
                                  key={s.key}
                                  className="mr-3 inline-flex items-center gap-2"
                                >
                                  <input
                                    type="checkbox"
                                    checked={step.depends_on.includes(s.key)}
                                    onChange={(e) =>
                                      changeStep(index, {
                                        depends_on: e.target.checked
                                          ? [...step.depends_on, s.key]
                                          : step.depends_on.filter(
                                              (k) => k !== s.key,
                                            ),
                                      })
                                    }
                                  />
                                  {s.key}
                                </label>
                              ))}
                            </div>
                          )}
                          <div className="space-y-3">
                            <h4 className="text-sm font-medium">
                              Evaluation rubric ·{" "}
                              {variant.rubric.reduce((n, c) => n + c.points, 0)}{" "}
                              points
                            </h4>
                            {variant.rubric.map((criterion, ci) => {
                              const update = (changes: Partial<Criterion>) =>
                                changeVariant(index, {
                                  rubric: variant.rubric.map((c, i) =>
                                    i === ci ? { ...c, ...changes } : c,
                                  ),
                                });
                              return (
                                <div
                                  key={ci}
                                  className="grid gap-2 rounded border p-3 sm:grid-cols-3"
                                >
                                  <Field
                                    label={`Step ${index + 1} criterion ${ci + 1} key`}
                                  >
                                    <Input
                                      required
                                      pattern="[a-z][a-z0-9_]{0,39}"
                                      value={criterion.key}
                                      onChange={(e) =>
                                        update({ key: e.target.value })
                                      }
                                    />
                                  </Field>
                                  <Field
                                    label={`Step ${index + 1} criterion ${ci + 1} label`}
                                  >
                                    <Input
                                      required
                                      maxLength={120}
                                      value={criterion.label}
                                      onChange={(e) =>
                                        update({ label: e.target.value })
                                      }
                                    />
                                  </Field>
                                  <Field
                                    label={`Step ${index + 1} criterion ${ci + 1} points`}
                                  >
                                    <Input
                                      required
                                      type="number"
                                      min={1}
                                      max={1000}
                                      value={criterion.points}
                                      onChange={(e) =>
                                        update({
                                          points: Number(e.target.value),
                                        })
                                      }
                                    />
                                  </Field>
                                  <div className="sm:col-span-2">
                                    <Field
                                      label={`Step ${index + 1} criterion ${ci + 1} guidance`}
                                    >
                                      <Input
                                        maxLength={1000}
                                        value={criterion.description}
                                        onChange={(e) =>
                                          update({
                                            description: e.target.value,
                                          })
                                        }
                                      />
                                    </Field>
                                  </div>
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    disabled={variant.rubric.length <= 1}
                                    onClick={() =>
                                      changeVariant(index, {
                                        rubric: variant.rubric.filter(
                                          (_, i) => i !== ci,
                                        ),
                                      })
                                    }
                                  >
                                    Remove criterion
                                  </Button>
                                </div>
                              );
                            })}
                            <Button
                              type="button"
                              variant="outline"
                              disabled={variant.rubric.length >= 15}
                              onClick={() => {
                                let n = 1;
                                while (
                                  variant.rubric.some(
                                    (c) => c.key === `criterion_${n}`,
                                  )
                                )
                                  n++;
                                changeVariant(index, {
                                  rubric: [
                                    ...variant.rubric,
                                    {
                                      key: `criterion_${n}`,
                                      label: "New criterion",
                                      points: 10,
                                      description: "",
                                    },
                                  ],
                                });
                              }}
                            >
                              Add criterion
                            </Button>
                          </div>
                          <Button
                            type="button"
                            variant="ghost"
                            disabled={edit.steps.length <= 1}
                            onClick={() =>
                              setEdit({
                                ...edit,
                                steps: edit.steps
                                  .filter((_, i) => i !== index)
                                  .map((s) => ({
                                    ...s,
                                    depends_on: s.depends_on.filter(
                                      (k) => k !== step.key,
                                    ),
                                  })),
                              })
                            }
                          >
                            Remove step
                          </Button>
                        </fieldset>
                      );
                    })}
                    <div className="flex flex-wrap items-center gap-3">
                      <Button
                        type="button"
                        variant="outline"
                        disabled={edit.steps.length >= 20}
                        onClick={() => {
                          let index = edit.steps.length + 1;
                          while (
                            edit.steps.some((s) => s.key === `week_${index}`)
                          )
                            index++;
                          const step = newStep(index);
                          step.week = Math.min(
                            52,
                            Math.max(...edit.steps.map((s) => s.week)) + 1,
                          );
                          setEdit({ ...edit, steps: [...edit.steps, step] });
                        }}
                      >
                        <Plus className="mr-2 h-4 w-4" />
                        Add weekly step
                      </Button>
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={edit.is_active}
                          onChange={(e) =>
                            setEdit({ ...edit, is_active: e.target.checked })
                          }
                        />
                        Active pack
                      </label>
                      <Button disabled={busy}>
                        <Save className="mr-2 h-4 w-4" />
                        Save task pack
                      </Button>
                    </div>
                  </form>
                )}
              </div>
            </div>
          )}
          {tab === "Assign pack" && (
            <div className="space-y-4">
              <div className={panel}>
                <h3 className="font-semibold">Assign a task pack to a batch</h3>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Saved task pack">
                    <select
                      className={inputClass}
                      value={packId}
                      onChange={(e) => setPackId(e.target.value)}
                    >
                      <option value="">Choose a pack</option>
                      {packs.data
                        ?.filter((p) => p.is_active)
                        .map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name} · v{p.version}
                          </option>
                        ))}
                    </select>
                  </Field>
                  <Field label="Task pack batch">
                    <select
                      className={inputClass}
                      value={batchId}
                      onChange={(e) => setBatchId(e.target.value)}
                    >
                      <option value="">Choose a batch</option>
                      {options?.batches?.map((b: Row) => (
                        <option key={b.id} value={b.id}>
                          {b.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Pack start date">
                    <Input
                      type="date"
                      min={today()}
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                    />
                  </Field>
                  <Field label="Pack reviewer">
                    <select
                      className={inputClass}
                      value={reviewer}
                      onChange={(e) => setReviewer(e.target.value)}
                    >
                      <option value="">Choose an authorized reviewer</option>
                      {options?.staff?.map((s: Row) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                </div>
                {roster.isError && (
                  <p role="alert">
                    Unable to load this batch. Check your batch access.
                  </p>
                )}
                {roster.data && (
                  <>
                    <div className="flex flex-wrap items-center gap-2">
                      <strong className="text-sm">
                        {Object.keys(selection).length} interns selected
                      </strong>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          setSelection(
                            Object.fromEntries(
                              roster.data.items
                                .slice(0, 500)
                                .map((p) => [p.id, "beginner"]),
                            ),
                          )
                        }
                      >
                        Select batch as beginner
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelection({})}
                      >
                        Clear selection
                      </Button>
                    </div>
                    {roster.data.total > 500 && (
                      <p role="alert" className="text-sm">
                        This batch has more than 500 eligible interns. Split it
                        into smaller groups before publishing.
                      </p>
                    )}
                    <div className="max-h-80 space-y-2 overflow-auto">
                      {roster.data.items.slice(0, 500).map((person) => (
                        <div
                          key={person.id}
                          className="flex flex-wrap items-center justify-between gap-2 rounded border p-3 text-sm"
                        >
                          <span>
                            {person.name} · {person.code}
                          </span>
                          <select
                            aria-label={`Skill level for ${person.name}`}
                            className={`${inputClass} max-w-[200px]`}
                            value={selection[person.id] || ""}
                            onChange={(e) =>
                              setSelection((current) => {
                                const next = { ...current };
                                if (e.target.value)
                                  next[person.id] = e.target.value as Level;
                                else delete next[person.id];
                                return next;
                              })
                            }
                          >
                            <option value="">Not selected</option>
                            {levels.map((l) => (
                              <option key={l} value={l}>
                                {l[0].toUpperCase() + l.slice(1)}
                              </option>
                            ))}
                          </select>
                        </div>
                      ))}
                    </div>
                  </>
                )}
                <p className="text-xs text-muted-foreground">
                  Each selected intern receives one variant per step. Their own
                  prerequisites must be approved before dependent work opens.
                  Publishing saves a snapshot of this pack version.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    disabled={
                      busy ||
                      !pack ||
                      !batchId ||
                      !reviewer ||
                      !startDate ||
                      !Object.keys(selection).length
                    }
                    onClick={() =>
                      void run(async () => {
                        setPackPreview(
                          (
                            await api.post(
                              `${root}/packs/${packId}/preview`,
                              publishBody,
                            )
                          ).data,
                        );
                        setPackPreviewKey(publishKey);
                      })
                    }
                  >
                    <Eye className="mr-2 h-4 w-4" />
                    Preview task pack
                  </Button>
                  <Button
                    disabled={
                      busy || !packPreview || publishKey !== packPreviewKey
                    }
                    onClick={() =>
                      void run(async () => {
                        const result = (
                          await api.post(
                            `${root}/packs/${packId}/publish`,
                            publishBody,
                          )
                        ).data;
                        setPackPreview(null);
                        setPackRequest(crypto.randomUUID());
                        await refresh();
                        setMessage(
                          `Published ${result.assignments} assignments for ${result.interns} interns. Notifications are available in their accounts.`,
                        );
                      })
                    }
                  >
                    <Send className="mr-2 h-4 w-4" />
                    Publish task pack
                  </Button>
                </div>
              </div>
              {packPreview && publishKey === packPreviewKey && (
                <div className={panel}>
                  <h3 className="font-semibold">
                    Preview: {packPreview.assignments} individual assignments ·{" "}
                    {packPreview.interns} interns
                  </h3>
                  <div className="overflow-auto">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr>
                          {[
                            "Week",
                            "Variant",
                            "Task",
                            "Due date",
                            "Interns",
                            "Prerequisites",
                          ].map((h) => (
                            <th className="p-2" key={h}>
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {packPreview.schedule.map((entry: Row) => (
                          <tr
                            className="border-t"
                            key={`${entry.step_key}:${entry.level}`}
                          >
                            <td className="p-2">{entry.week}</td>
                            <td>{entry.level}</td>
                            <td>{entry.title}</td>
                            <td className="whitespace-nowrap">
                              {entry.due_date}
                            </td>
                            <td>{entry.recipients}</td>
                            <td>{entry.depends_on.join(", ") || "None"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              <div className={panel}>
                <h3 className="font-semibold">Recent pack runs</h3>
                {runs.isError && (
                  <p role="alert">Pack history could not be loaded.</p>
                )}
                {runs.data?.items.map((r) => (
                  <p key={r.id} className="border-b pb-2 text-sm">
                    {r.name} · v{r.pack_version} · {r.interns} interns ·{" "}
                    {r.assignments} assignments · Run #{r.id}
                  </p>
                ))}
                {runs.data?.total === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No packs published in this project yet.
                  </p>
                )}
              </div>
            </div>
          )}
          {tab === "Extend deadlines" && (
            <div className="space-y-4">
              <div className={panel}>
                <h3 className="flex items-center gap-2 font-semibold">
                  <CalendarClock className="h-5 w-5" />
                  Bulk deadline extension
                </h3>
                <p className="text-sm text-muted-foreground">
                  Select individual assignments below. Only selected interns’
                  deadlines change. Completed and cancelled work is excluded.
                </p>
                <Field label="Deadline batch filter">
                  <select
                    className={inputClass}
                    value={batchId}
                    onChange={(e) => setBatchId(e.target.value)}
                  >
                    <option value="">
                      All authorized interns in this project
                    </option>
                    {options?.batches?.map((b: Row) => (
                      <option key={b.id} value={b.id}>
                        {b.name}
                      </option>
                    ))}
                  </select>
                </Field>
                {assignments.isError && (
                  <p role="alert">
                    Unable to load assignments. Refresh and try again.
                  </p>
                )}
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={
                      !assignments.data?.items.length || selectedCount >= 500
                    }
                    onClick={() =>
                      setChosen((current) => {
                        const next = { ...current };
                        for (const row of assignments.data?.items || [])
                          if (row.due_date && Object.keys(next).length < 500)
                            next[keyOf(row)] = row;
                        return next;
                      })
                    }
                  >
                    Select current page
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setChosen({})}
                  >
                    Clear selected assignments
                  </Button>
                  <span className="self-center text-sm">
                    {selectedCount} selected (maximum 500)
                  </span>
                </div>
                <div className="overflow-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr>
                        {[
                          "Select",
                          "Intern",
                          "Task",
                          "Status",
                          "Current deadline",
                        ].map((h) => (
                          <th key={h} className="p-2">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {assignments.data?.items.map((a) => (
                        <tr className="border-t" key={keyOf(a)}>
                          <td className="p-2">
                            <input
                              type="checkbox"
                              aria-label={`Extend ${a.task} for ${a.intern}`}
                              checked={!!chosen[keyOf(a)]}
                              disabled={
                                !a.due_date ||
                                (selectedCount >= 500 && !chosen[keyOf(a)])
                              }
                              onChange={(e) => toggle(a, e.target.checked)}
                            />
                          </td>
                          <td className="p-2">{a.intern}</td>
                          <td className="p-2">{a.task}</td>
                          <td className="p-2">{a.status}</td>
                          <td className="p-2 whitespace-nowrap">
                            {a.due_date || "No deadline set"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {assignments.data?.total === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No unfinished intern assignments match this selection.
                  </p>
                )}
                <div className="flex items-center justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page === 1 || assignments.isFetching}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    Previous assignments
                  </Button>
                  <span className="text-xs">Page {page}</span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={
                      page * 50 >= (assignments.data?.total || 0) ||
                      assignments.isFetching
                    }
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next assignments
                  </Button>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="New deadline">
                    <Input
                      type="date"
                      min={today()}
                      value={deadline}
                      onChange={(e) => setDeadline(e.target.value)}
                    />
                  </Field>
                  <Field label="Extension reason">
                    <textarea
                      className={inputClass}
                      minLength={5}
                      maxLength={2000}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                  </Field>
                </div>
                <p className="text-xs text-muted-foreground">
                  The new date must be later than every selected deadline. The
                  reason and old/new dates are recorded in PMS, and each
                  affected intern receives an in-app notification.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    disabled={
                      busy ||
                      !selectedCount ||
                      !deadline ||
                      reason.trim().length < 5
                    }
                    onClick={() =>
                      void run(async () => {
                        setDeadlinePreview(
                          (
                            await api.post(
                              root + "/deadlines/preview",
                              deadlineBody,
                            )
                          ).data,
                        );
                        setDeadlinePreviewKey(deadlineKey);
                      })
                    }
                  >
                    <Eye className="mr-2 h-4 w-4" />
                    Preview extension
                  </Button>
                  <Button
                    disabled={
                      busy ||
                      !deadlinePreview ||
                      deadlinePreviewKey !== deadlineKey
                    }
                    onClick={() =>
                      void run(async () => {
                        const result = (
                          await api.post(
                            root + "/deadlines/extend",
                            deadlineBody,
                          )
                        ).data;
                        setChosen({});
                        setDeadlinePreview(null);
                        setDeadlineRequest(crypto.randomUUID());
                        await refresh();
                        setMessage(
                          `Extended ${result.count} deadlines and notified the affected interns.`,
                        );
                      })
                    }
                  >
                    Extend selected deadlines
                  </Button>
                </div>
                {deadlinePreview && deadlinePreviewKey === deadlineKey && (
                  <div className="rounded border p-3 text-sm">
                    <strong>
                      {deadlinePreview.count} assignments will change to{" "}
                      {deadline}
                    </strong>
                    <p className="mt-1 whitespace-pre-wrap">Reason: {reason}</p>
                    <ul className="mt-2 list-disc space-y-1 pl-5">
                      {deadlinePreview.changes.map((c: Row) => (
                        <li key={`${c.task_id}:${c.user_id}`}>
                          {chosen[`${c.task_id}:${c.user_id}`]?.intern} ·{" "}
                          {c.title}: {c.old_due_date} → {c.new_due_date}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
              <div className={panel}>
                <h3 className="font-semibold">Recent deadline changes</h3>
                {history.isError && (
                  <p role="alert">Deadline history could not be loaded.</p>
                )}
                {history.data?.items.map((item) => (
                  <details key={item.id} className="rounded border p-3 text-sm">
                    <summary className="cursor-pointer">
                      {item.count} assignments · {item.reason}
                    </summary>
                    <p className="mt-2 text-xs text-muted-foreground">
                      Change #{item.id} · Actor #{item.created_by} ·{" "}
                      {new Date(item.created_at).toLocaleString()}
                    </p>
                    <ul className="mt-2 space-y-1">
                      {item.changes.map((c: Row) => (
                        <li key={`${c.task_id}:${c.user_id}`}>
                          {c.title} · Intern account #{c.user_id} ·{" "}
                          {c.old_due_date} → {c.new_due_date}
                        </li>
                      ))}
                    </ul>
                  </details>
                ))}
                {history.data?.total === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No bulk extensions recorded yet.
                  </p>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}

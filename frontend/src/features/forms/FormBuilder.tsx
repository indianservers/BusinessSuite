import { useRef, useState, type ReactNode } from "react";
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  closestCenter,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  sortableKeyboardCoordinates,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import FormResponse from "./FormResponse";
import FormAppearance from "./FormAppearance";
import {
  download,
  fresh,
  kinds,
  question,
  type Definition,
  type Kind,
  type Question,
} from "./formsTypes";
function CanvasDropZone({children}:{children:ReactNode}) {
  const {setNodeRef,isOver}=useDroppable({id:"form-canvas"});
  return <main ref={setNodeRef} className={`forms-canvas ${isOver?"ring-2 ring-primary":""}`}>{children}</main>;
}
function Palette({
  kind,
  label,
  icon,
  add,
}: {
  kind: Kind;
  label: string;
  icon: string;
  add: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({
    id: "palette:" + kind,
  });
  return (
    <button
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform) }}
      {...attributes}
      {...listeners}
      onClick={add}
      type="button"
      className="form-palette-item"
    >
      <span>{icon}</span>
      {label}
    </button>
  );
}
function Item({
  field,
  index,
  active,
  select,
  remove,
  duplicate,
  move,
}: {
  field: Question;
  index: number;
  active: boolean;
  select: () => void;
  remove: () => void;
  duplicate: () => void;
  move: (d: number) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({ id: field.id });
  return (
    <article
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={"form-question " + (active ? "selected" : "")}
    >
      <div className="form-question-tools">
        <button
          {...attributes}
          {...listeners}
          aria-label={`Drag ${field.label}`}
          className="form-grip"
        >
          ⠿
        </button>
        <span>
          {String(index + 1).padStart(2, "0")} ·{" "}
          {kinds.find((k) => k[0] === field.type)?.[1]}
        </span>
        <button aria-label={`Move ${field.label} up`} onClick={() => move(-1)}>
          ↑
        </button>
        <button aria-label={`Move ${field.label} down`} onClick={() => move(1)}>
          ↓
        </button>
        <button aria-label={`Duplicate ${field.label}`} onClick={duplicate}>
          ⧉
        </button>
        <button aria-label={`Delete ${field.label}`} onClick={remove}>
          ×
        </button>
      </div>
      <button className="form-question-select" onClick={select}>
        <strong>
          {field.label}
          {field.required && <em> *</em>}
        </strong>
        {field.help && <small>{field.help}</small>}
        <div className="form-field-ghost">
          {field.type === "section"
            ? "Section divider"
            : ["select", "radio", "multiselect"].includes(field.type)
              ? field.options.join(" · ")
              : field.placeholder || "Answer goes here"}
        </div>
        {field.condition && <small>⑂ Conditional question</small>}
      </button>
    </article>
  );
}
export default function FormBuilder({
  draft,
  selected,
  setSelected,
  edit,
  error,
  importForm,
  share,
  close,
  open,
}: {
  draft: Definition;
  selected: string;
  setSelected: (s: string) => void;
  edit: (d: Definition) => void;
  error: (s: string) => void;
  importForm: (d: unknown) => Promise<void>;
  share: () => void;
  close: () => void;
  open: boolean;
}) {
  const [search, setSearch] = useState("");
  const [canvas, setCanvas] = useState(true);
  const [mobile, setMobile] = useState(false);
  const [pendingTemplate, setPendingTemplate] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const field = draft.fields.find((f) => f.id === selected);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );
  const patch = (id: string, data: Partial<Question>) =>
    edit({
      ...draft,
      fields: draft.fields.map((f) => (f.id === id ? { ...f, ...data } : f)),
    });
  function add(type: Kind, at = draft.fields.length) {
    if (draft.fields.length >= 60) {
      error("A form supports up to 60 fields.");
      return;
    }
    const f = question(type);
    const fields = [...draft.fields];
    fields.splice(at, 0, f);
    edit({ ...draft, fields });
    setSelected(f.id);
  }
  function reorder(from: number, to: number) {
    if (to < 0 || to >= draft.fields.length) return;
    const fields = arrayMove(draft.fields, from, to);
    const seen = new Set<string>();
    if (
      fields.some((f) => {
        const invalid = f.condition && !seen.has(f.condition.field);
        seen.add(f.id);
        return invalid;
      })
    ) {
      error("Keep conditional questions after their source question.");
      return;
    }
    edit({ ...draft, fields });
  }
  function dragEnd(e: DragEndEvent) {
    if (!e.over) return;
    const id = String(e.active.id);
    if (id.startsWith("palette:"))
      add(
        id.slice(8) as Kind,
        Math.max(
          0,
          e.over.id === "form-canvas" ? draft.fields.length : draft.fields.findIndex((f) => f.id === e.over!.id),
        ),
      );
    else
      reorder(
        draft.fields.findIndex((f) => f.id === id),
        e.over.id === "form-canvas" ? draft.fields.length - 1 : draft.fields.findIndex((f) => f.id === e.over!.id),
      );
  }
  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={dragEnd}
    >
      <div className="forms-builder">
        <aside className="forms-panel">
          <details open={window.innerWidth > 700}>
            <summary>Field library · add questions</summary>
            <p>Click to add. Drag to place.</p>
            <input
              aria-label="Search fields"
              placeholder="Search fields…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <div className="form-palette">
              {kinds
                .filter((k) =>
                  k[1].toLowerCase().includes(search.toLowerCase()),
                )
                .map(([kind, label, icon]) => (
                  <Palette
                    key={kind}
                    kind={kind}
                    label={label}
                    icon={icon}
                    add={() => add(kind)}
                  />
                ))}
            </div>
            <h3>Start with a template</h3>
            {pendingTemplate && <p role="status">Click {pendingTemplate} again to replace the current questions. <button type="button" onClick={() => setPendingTemplate("")}>Cancel</button></p>}
            {["Internship application", "Support request", "Project brief", "Feedback survey"].map(
              (name) => (
                <button
                  className="form-template"
                  key={name}
                  onClick={() => {
                    if (pendingTemplate !== name) { setPendingTemplate(name); return; }
                    setPendingTemplate("");
                    const d = fresh();
                    d.name = name;
                    if (name === "Internship application") {
                      d.name = "Join our internship program";
                      d.description = "Register your details to apply for internship opportunities.";
                      d.accent = "#4255ff";
                      d.submit_label = "Submit application";
                      d.settings = {...d.settings!, columns: 3, intro_enabled: true, intro_badge: "Build your future", intro_title: "Kickstart your career with real-world experience", intro_text: "Join our internship program and gain hands-on experience, learn from industry experts, and turn your skills into opportunities.", surface: "soft"};
                      d.fields = ([['text','Full name'], ['text','Parent / guardian name'], ['phone','Mobile number'], ['email','Email address'], ['select','Current degree'], ['date','Date of birth'], ['text','College / university'], ['text','Branch / specialization'], ['select','Internship mode'], ['textarea','Current address'], ['checkbox','I confirm that my details are correct']] as [Kind,string][]).map(([type,label]) => ({...question(type,label), required:true, width: type === 'textarea' || type === 'checkbox' ? 'full' as const : 'auto' as const, options: label === 'Current degree' ? ['B.Tech / B.E.', 'B.Sc', 'B.Com', 'Other'] : ['On-site', 'Remote', 'Hybrid']}));
                      d.workflow.title_field = d.fields[0].id;
                    }
                    if (name === "Feedback survey")
                      d.fields.push(
                        question("rating", "How was your experience?"),
                      );
                    if (name === "Project brief")
                      d.fields.push(question("date", "Target launch date"));
                    edit(d);
                    setSelected(d.fields[0].id);
                  }}
                >
                  ▧ {name}
                </button>
              ),
            )}
            <button onClick={() => fileRef.current?.click()}>
              Import form JSON
            </button>
            <input
              hidden
              ref={fileRef}
              type="file"
              accept="application/json,.json"
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (!file) return;
                if (file.size > 200000) {
                  error("Import limit: 200 KB");
                  return;
                }
                void file
                  .text()
                  .then((text) => importForm(JSON.parse(text)))
                  .catch(() => error("Could not import this form definition."));
              }}
            />
          </details>
        </aside>
        <CanvasDropZone>
          <div className="form-visual-toolbar" role="group" aria-label="Canvas view">
            <button aria-pressed={canvas} onClick={() => setCanvas(true)}>✦ Visual editor</button>
            <button aria-pressed={!canvas} onClick={() => setCanvas(false)}>☷ Arrange fields</button>
            <button aria-pressed={mobile} onClick={() => setMobile(!mobile)}>{mobile ? "Desktop view" : "Mobile view"}</button>
          </div>
          <div className="form-canvas-heading">
            <input
              aria-label="Form name"
              maxLength={120}
              value={draft.name}
              onChange={(e) => edit({ ...draft, name: e.target.value })}
            />
            <textarea
              aria-label="Form description"
              maxLength={2000}
              value={draft.description}
              onChange={(e) => edit({ ...draft, description: e.target.value })}
            />
          </div>
          {canvas ? <FormResponse definition={draft} mobile={mobile} disabled={false} submit={async () => {}} editor={{ selected, select: setSelected, label: (id, label) => patch(id, {label}) }} /> : <SortableContext
            items={draft.fields.map((f) => f.id)}
            strategy={verticalListSortingStrategy}
          >
            {draft.fields.map((f, i) => (
              <Item
                key={f.id}
                field={f}
                index={i}
                active={selected === f.id}
                select={() => setSelected(f.id)}
                duplicate={() => {
                  if (draft.fields.length >= 60) {
                    error("Limit: 60 fields");
                    return;
                  }
                  const copy = {
                    ...f,
                    id: question(f.type).id,
                    label: f.label + " (copy)",
                  };
                  const fields = [...draft.fields];
                  fields.splice(i + 1, 0, copy);
                  edit({ ...draft, fields });
                  setSelected(copy.id);
                }}
                move={(d) => reorder(i, i + d)}
                remove={() => {
                  if (draft.fields.some((q) => q.condition?.field === f.id)) {
                    error("Remove conditions referencing this question first.");
                    return;
                  }
                  edit({
                    ...draft,
                    fields: draft.fields.filter((q) => q.id !== f.id),
                  });
                }}
              />
            ))}
          </SortableContext>}
          <button className="form-add-question" onClick={() => add("text")}>
            ＋ Add question
          </button>
        </CanvasDropZone>
        <aside className="forms-panel forms-properties">
          <h2>
            {field
              ? kinds.find((k) => k[0] === field.type)?.[1]
              : "Question settings"}
          </h2>
          <p>Configure this field · General & rules</p>
          <details className="form-appearance-details"><summary>Layout & appearance</summary><FormAppearance draft={draft} edit={edit} /></details>
          {field ? (
            <>
              <label>
                Field width
                <select value={field.width || "auto"} onChange={e => patch(field.id, {width: e.target.value as "auto" | "full"})}>
                  <option value="auto">Fit grid column</option><option value="full">Full row</option>
                </select>
              </label>
              <label>
                Label
                <input
                  value={field.label}
                  maxLength={160}
                  onChange={(e) => patch(field.id, { label: e.target.value })}
                />
              </label>
              <label>
                Helper text
                <textarea
                  maxLength={500}
                  value={field.help}
                  onChange={(e) => patch(field.id, { help: e.target.value })}
                />
              </label>
              <label>
                Placeholder
                <input
                  maxLength={160}
                  value={field.placeholder}
                  onChange={(e) =>
                    patch(field.id, { placeholder: e.target.value })
                  }
                />
              </label>
              {field.type !== "section" && (
                <label className="form-choice">
                  <input
                    type="checkbox"
                    checked={field.required}
                    onChange={(e) =>
                      patch(field.id, { required: e.target.checked })
                    }
                  />
                  Required question
                </label>
              )}
              {["select", "radio", "multiselect"].includes(field.type) && (
                <label>
                  Options · one per line
                  <textarea
                    value={field.options.join("\n")}
                    onChange={(e) =>
                      patch(field.id, { options: e.target.value.split("\n") })
                    }
                  />
                </label>
              )}
              {field.type === "number" && (
                <div className="form-grid-two">
                  {(["min", "max"] as const).map((key) => (
                    <label key={key}>
                      {key}
                      <input
                        type="number"
                        value={field[key] ?? ""}
                        onChange={(e) =>
                          patch(field.id, {
                            [key]:
                              e.target.value === ""
                                ? null
                                : Number(e.target.value),
                          })
                        }
                      />
                    </label>
                  ))}
                </div>
              )}
              <h3>Conditional logic</h3>
              <label>
                Show this question
                <select
                  value={field.condition?.field || ""}
                  onChange={(e) =>
                    patch(field.id, {
                      condition: e.target.value
                        ? {
                            field: e.target.value,
                            operator: "equals",
                            value: "",
                          }
                        : null,
                    })
                  }
                >
                  <option value="">Always</option>
                  {draft.fields
                    .slice(0, draft.fields.indexOf(field))
                    .filter(
                      (f) => !["section", "page", "file"].includes(f.type),
                    )
                    .map((f) => (
                      <option key={f.id} value={f.id}>
                        When: {f.label}
                      </option>
                    ))}
                </select>
              </label>
              {field.condition && (
                <>
                  <select
                    aria-label="Condition operator"
                    value={field.condition.operator}
                    onChange={(e) =>
                      patch(field.id, {
                        condition: {
                          ...field.condition!,
                          operator: e.target.value as "equals",
                        },
                      })
                    }
                  >
                    {[
                      ["equals", "Equals"],
                      ["not_equals", "Does not equal"],
                      ["contains", "Contains"],
                      ["not_empty", "Is answered"],
                    ].map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                  {field.condition.operator !== "not_empty" && (
                    <input
                      aria-label="Condition value"
                      value={field.condition.value}
                      onChange={(e) =>
                        patch(field.id, {
                          condition: {
                            ...field.condition!,
                            value: e.target.value,
                          },
                        })
                      }
                    />
                  )}
                </>
              )}
            </>
          ) : (
            <p>Select a question to edit its settings.</p>
          )}
          <hr />
          <h3>Form appearance</h3>
          <label>
            Accent color
            <input
              type="color"
              value={draft.accent}
              onChange={(e) => edit({ ...draft, accent: e.target.value })}
            />
          </label>
          <label>
            Submit button
            <input
              maxLength={60}
              value={draft.submit_label}
              onChange={(e) => edit({ ...draft, submit_label: e.target.value })}
            />
          </label>
          <label>
            Success message
            <textarea
              maxLength={500}
              value={draft.success_message}
              onChange={(e) =>
                edit({ ...draft, success_message: e.target.value })
              }
            />
          </label>
          <button
            onClick={() =>
              download(
                JSON.stringify(draft, null, 2),
                "form-definition.json",
                "application/json",
              )
            }
          >
            Export form definition
          </button>
          <button disabled={!open} onClick={share}>
            Publishing settings
          </button>
          {open && <button onClick={close}>Close responses</button>}
        </aside>
      </div>
    </DndContext>
  );
}

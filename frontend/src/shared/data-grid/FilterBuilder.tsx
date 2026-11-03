import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Filter, Plus, Trash2, X } from "lucide-react";
import type { GridColumn, GridFilter, GridOperator } from "./types";
import { isGroup } from "./state";
export const operators: [GridOperator, string][] = [
  ["equals", "Equals"],
  ["not_equals", "Does not equal"],
  ["contains", "Contains"],
  ["starts_with", "Starts with"],
  ["ends_with", "Ends with"],
  ["between", "Between"],
  ["gt", "Greater than"],
  ["gte", "At least"],
  ["lt", "Less than"],
  ["lte", "At most"],
  ["empty", "Is empty"],
  ["not_empty", "Is not empty"],
];
export default function FilterBuilder<T>({
  columns,
  value,
  close,
  apply,
}: {
  columns: GridColumn<T>[];
  value: GridFilter;
  close: () => void;
  apply: (filter: GridFilter) => void;
}) {
  const [draft, setDraft] = useState<GridFilter>(() => structuredClone(value));
  const available = columns.filter((c) => c.filterable !== false);
  function groupEditor(
    group: GridFilter,
    change: (filter: GridFilter) => void,
    depth = 0,
  ) {
    return (
      <section className="udg-filter-group">
        <header>
          <span>Match</span>
          <select
            aria-label={`Filter logic level ${depth + 1}`}
            value={group.logic}
            onChange={(e) =>
              change({ ...group, logic: e.target.value as "and" | "or" })
            }
          >
            <option value="and">All conditions (AND)</option>
            <option value="or">Any condition (OR)</option>
          </select>
        </header>
        {group.rules.map((rule, index) => (
          <div
            key={index}
            className={isGroup(rule) ? "udg-filter-nested" : "udg-filter-rule"}
          >
            {isGroup(rule) ? (
              groupEditor(
                rule,
                (next) =>
                  change({
                    ...group,
                    rules: group.rules.map((r, i) => (i === index ? next : r)),
                  }),
                depth + 1,
              )
            ) : (
              <>
                <select
                  aria-label={`Filter column ${index + 1}`}
                  value={rule.field}
                  onChange={(e) =>
                    change({
                      ...group,
                      rules: group.rules.map((r, i) =>
                        i === index
                          ? {
                              field: e.target.value,
                              operator: "equals",
                              value: "",
                            }
                          : r,
                      ),
                    })
                  }
                >
                  {available.map((column) => (
                    <option key={column.id} value={column.id}>
                      {column.title}
                    </option>
                  ))}
                </select>
                <select
                  aria-label={`Filter operator ${index + 1}`}
                  value={rule.operator}
                  onChange={(e) =>
                    change({
                      ...group,
                      rules: group.rules.map((r, i) =>
                        i === index
                          ? {
                              ...rule,
                              operator: e.target.value as GridOperator,
                            }
                          : r,
                      ),
                    })
                  }
                >
                  {operators
                    .filter(
                      ([op]) =>
                        !["number", "currency", "date", "datetime"].includes(
                          available.find((c) => c.id === rule.field)?.type ||
                            "text",
                        ) ||
                        !["contains", "starts_with", "ends_with"].includes(op),
                    )
                    .map(([op, text]) => (
                      <option key={op} value={op}>
                        {text}
                      </option>
                    ))}
                  {rule.operator === "in" && (
                    <option value="in">Is one of</option>
                  )}
                </select>
                {!["empty", "not_empty"].includes(rule.operator) && (
                  <input
                    aria-label={`Filter value ${index + 1}`}
                    type={
                      ["date", "datetime"].includes(
                        available.find((c) => c.id === rule.field)?.type || "",
                      )
                        ? available.find((c) => c.id === rule.field)?.type ===
                          "date"
                          ? "date"
                          : "datetime-local"
                        : ["number", "currency"].includes(
                              available.find((c) => c.id === rule.field)
                                ?.type || "",
                            )
                          ? "number"
                          : "text"
                    }
                    value={
                      Array.isArray(rule.value)
                        ? rule.value.join(",")
                        : String(rule.value ?? "")
                    }
                    onChange={(e) =>
                      change({
                        ...group,
                        rules: group.rules.map((r, i) =>
                          i === index
                            ? {
                                ...rule,
                                value:
                                  rule.operator === "in"
                                    ? e.target.value.split(",")
                                    : e.target.value,
                              }
                            : r,
                        ),
                      })
                    }
                  />
                )}{" "}
                {rule.operator === "between" && (
                  <input
                    aria-label={`Filter upper value ${index + 1}`}
                    type={
                      ["date", "datetime"].includes(
                        available.find((c) => c.id === rule.field)?.type || "",
                      )
                        ? available.find((c) => c.id === rule.field)?.type ===
                          "datetime"
                          ? "datetime-local"
                          : "date"
                        : "number"
                    }
                    value={String(rule.value2 ?? "")}
                    onChange={(e) =>
                      change({
                        ...group,
                        rules: group.rules.map((r, i) =>
                          i === index ? { ...rule, value2: e.target.value } : r,
                        ),
                      })
                    }
                  />
                )}
              </>
            )}
            <button
              type="button"
              aria-label={`Remove condition ${index + 1}`}
              onClick={() =>
                change({
                  ...group,
                  rules: group.rules.filter((_, i) => i !== index),
                })
              }
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
        <footer>
          <button
            type="button"
            onClick={() =>
              change({
                ...group,
                rules: [
                  ...group.rules,
                  { field: available[0].id, operator: "contains", value: "" },
                ],
              })
            }
          >
            <Plus size={14} />
            Condition
          </button>
          {depth < 3 && (
            <button
              type="button"
              onClick={() =>
                change({
                  ...group,
                  rules: [...group.rules, { logic: "or", rules: [] }],
                })
              }
            >
              <Plus size={14} />
              AND/OR group
            </button>
          )}
        </footer>
      </section>
    );
  }
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open) close();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="udg-overlay" />
        <Dialog.Content className="udg-dialog">
          <header>
            <Filter size={18} />
            <div>
              <Dialog.Title>Advanced filters</Dialog.Title>
              <Dialog.Description>
                Conditions run on the full permitted dataset.
              </Dialog.Description>
            </div>
            <Dialog.Close aria-label="Close filter builder">
              <X size={18} />
            </Dialog.Close>
          </header>
          {groupEditor(draft, setDraft)}
          <footer className="udg-dialog-footer">
            <button onClick={() => setDraft({ logic: "and", rules: [] })}>
              Clear conditions
            </button>
            <button onClick={close}>Cancel</button>
            <button className="udg-primary" onClick={() => apply(draft)}>
              Apply filters
            </button>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

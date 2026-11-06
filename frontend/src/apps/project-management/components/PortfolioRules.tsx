import type { PMSProject } from "../types";
import { NativeSelect } from "@/components/ui/native-select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
export type PortfolioRule = { field: string; operator: string; value: string };
const fields = [
  ["name", "Project name"],
  ["project_key", "Project code"],
  ["client_name", "Client"],
  ["owner_name", "Owner"],
  ["team", "Team member"],
  ["status", "Status"],
  ["priority", "Priority"],
  ["progress", "Progress %"],
  ["start_date", "Start date"],
  ["due_date", "Due date"],
  ["created_at", "Created date"],
  ["updated_at", "Last updated"],
];
export const readRules = (value: string): PortfolioRule[] => {
  try {
    const rules = JSON.parse(value);
    return Array.isArray(rules)
      ? rules.filter(
          (r) =>
            r &&
            typeof r.field === "string" &&
            typeof r.operator === "string" &&
            typeof r.value === "string",
        )
      : [];
  } catch {
    return [];
  }
};
export function matchesRules(
  project: PMSProject,
  rules: PortfolioRule[],
  mode: string,
) {
  const match = (r: PortfolioRule) => {
    const value =
      r.field === "progress"
        ? (project.calculated_progress ?? project.progress_percent)
        : r.field === "team"
          ? project.team?.map((m) => m.name).join(", ")
          : project[r.field as keyof PMSProject];
    const raw = String(value ?? "").toLowerCase(),
      target = r.value.toLowerCase();
    if (r.operator === "empty") return !raw;
    if (r.operator === "contains") return raw.includes(target);
    if (r.operator === "equals") return raw === target;
    if (r.operator === "not") return raw !== target;
    if (!raw || !target) return false;
    const a = r.field === "progress" ? Number(raw) : raw.slice(0, 10),
      b = r.field === "progress" ? Number(target) : target;
    return r.operator === "gte" ? a >= b : a <= b;
  };
  return (
    !rules.length || (mode === "any" ? rules.some(match) : rules.every(match))
  );
}
export default function PortfolioRules({
  rules,
  mode,
  onChange,
  onMode,
}: {
  rules: PortfolioRule[];
  mode: string;
  onChange: (rules: PortfolioRule[]) => void;
  onMode: (mode: string) => void;
}) {
  const update = (index: number, patch: Partial<PortfolioRule>) =>
    onChange(rules.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  return (
    <details className="portfolio-rule-builder">
      <summary>
        Combine filter conditions {rules.length ? `(${rules.length})` : ""}
      </summary>
      <div className="grid gap-2 pt-3">
        <div className="flex items-center gap-2">
          <span>Match</span>
          <NativeSelect
            aria-label="Filter condition matching"
            value={mode}
            onChange={(e) => onMode(e.target.value)}
          >
            <option value="all">All conditions (AND)</option>
            <option value="any">Any condition (OR)</option>
          </NativeSelect>
        </div>
        {rules.map((r, i) => (
          <div key={i} className="flex flex-wrap items-center gap-2">
            <NativeSelect
              aria-label={`Condition ${i + 1} field`}
              value={r.field}
              onChange={(e) => update(i, { field: e.target.value })}
            >
              {fields.map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </NativeSelect>
            <NativeSelect
              aria-label={`Condition ${i + 1} operator`}
              value={r.operator}
              onChange={(e) => update(i, { operator: e.target.value })}
            >
              <option value="contains">Contains</option>
              <option value="equals">Equals</option>
              <option value="not">Does not equal</option>
              <option value="gte">On or after / at least</option>
              <option value="lte">On or before / at most</option>
              <option value="empty">Is empty</option>
            </NativeSelect>
            {r.operator !== "empty" && (
              <Input
                className="max-w-48"
                aria-label={`Condition ${i + 1} value`}
                type={
                  r.field === "progress"
                    ? "number"
                    : r.field.endsWith("_date") || r.field.endsWith("_at")
                      ? "date"
                      : "text"
                }
                value={r.value}
                onChange={(e) => update(i, { value: e.target.value })}
              />
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onChange(rules.filter((_, n) => n !== i))}
              aria-label={`Remove condition ${i + 1}`}
            >
              Remove
            </Button>
          </div>
        ))}
        <Button
          className="w-fit"
          variant="outline"
          size="sm"
          onClick={() =>
            onChange([
              ...rules,
              { field: "name", operator: "contains", value: "" },
            ])
          }
        >
          Add condition
        </Button>
      </div>
    </details>
  );
}

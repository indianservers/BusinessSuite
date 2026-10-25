import { useState, type ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Check, Search, X } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import {
  emptyFilters,
  type DashboardFilters,
  type Scope,
  type Widget,
  type Catalog,
  type Configuration,
} from "./model";
export function Panel({
  title,
  description,
  open,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  description: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(v) => {
        if (!v) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="db-panel-overlay" />
        <Dialog.Content
          className={`db-panel ${wide ? "db-panel-wide" : ""}`}
          onPointerDownOutside={(e) => e.preventDefault()}
        >
          <header>
            <div>
              <Dialog.Title>{title}</Dialog.Title>
              <Dialog.Description>{description}</Dialog.Description>
            </div>
            <button onClick={onClose} aria-label={`Close ${title}`}>
              <X size={20} />
            </button>
          </header>
          <div className="db-panel-body">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function Choice({
  label,
  value,
  onChange,
  options,
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  disabled?: boolean;
}) {
  return (
    <label className="db-field">
      <span>{label}</span>
      <Select
        value={value || "__empty"}
        disabled={disabled}
        onValueChange={(v) => onChange(v === "__empty" ? "" : v)}
      >
        <SelectTrigger aria-label={label}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent className="db-select-options">
          {options.map((o) => (
            <SelectItem key={o.value || "__empty"} value={o.value || "__empty"}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </label>
  );
}
export function MultiChoice({
  label,
  values,
  onChange,
  options,
}: {
  label: string;
  values: (string | number)[];
  onChange: (values: any[]) => void;
  options: { value: string | number; label: string }[];
}) {
  const [search, setSearch] = useState("");
  return (
    <details className="db-multi">
      <summary>
        {label}
        <span>{values.length || "All"}</span>
      </summary>
      <div>
        <label className="db-mini-search">
          <Search size={15} />
          <input
            aria-label={`Search ${label}`}
            placeholder="Search…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        {options
          .filter((o) => o.label.toLowerCase().includes(search.toLowerCase()))
          .map((o) => (
            <label key={o.value}>
              <input
                type="checkbox"
                checked={values.includes(o.value)}
                onChange={(e) =>
                  onChange(
                    e.target.checked
                      ? [...values, o.value]
                      : values.filter((v) => v !== o.value),
                  )
                }
              />
              {o.label}
            </label>
          ))}
        {!options.length && <small>No accessible options.</small>}
        <button type="button" onClick={() => onChange([])}>
          Clear selection
        </button>
      </div>
    </details>
  );
}
export function applyPreset(
  preset: string,
  filters: DashboardFilters,
): DashboardFilters {
  if (preset === "all") return { ...filters, date_from: null, date_to: null };
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: filters.timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value);
  const today = new Date(Date.UTC(get("year"), get("month") - 1, get("day")));
  let start = new Date(today),
    end = new Date(today);
  if (preset === "yesterday")
    (start.setUTCDate(start.getUTCDate() - 1), (end = new Date(start)));
  if (preset === "7" || preset === "30")
    start.setUTCDate(start.getUTCDate() - Number(preset) + 1);
  if (preset === "month") start.setUTCDate(1);
  if (preset === "last_month") {
    start.setUTCMonth(start.getUTCMonth() - 1, 1);
    end = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), 0));
  }
  if (preset === "quarter")
    start = new Date(
      Date.UTC(
        today.getUTCFullYear(),
        Math.floor(today.getUTCMonth() / 3) * 3,
        1,
      ),
    );
  if (preset === "year")
    start = new Date(Date.UTC(today.getUTCFullYear(), 0, 1));
  return {
    ...filters,
    date_from: start.toISOString().slice(0, 10),
    date_to: end.toISOString().slice(0, 10),
  };
}
export function FilterFields({
  value,
  onChange,
  scope,
}: {
  value: DashboardFilters;
  onChange: (next: DashboardFilters) => void;
  scope?: Scope;
}) {
  const set = (key: keyof DashboardFilters, next: any) =>
    onChange({ ...value, [key]: next });
  return (
    <div className="db-filter-fields">
      <Choice
        label="Date range preset"
        value="custom"
        onChange={(v) => v !== "custom" && onChange(applyPreset(v, value))}
        options={[
          ["all", "All time"],
          ["today", "Today"],
          ["yesterday", "Yesterday"],
          ["7", "Last 7 days"],
          ["30", "Last 30 days"],
          ["month", "This month"],
          ["last_month", "Last month"],
          ["quarter", "This quarter"],
          ["year", "This year"],
          ["custom", "Custom range"],
        ].map(([value, label]) => ({ value, label }))}
      />
      <div className="db-field-pair">
        <label className="db-field">
          <span>From date</span>
          <input
            type="date"
            value={value.date_from || ""}
            onChange={(e) => set("date_from", e.target.value || null)}
          />
        </label>
        <label className="db-field">
          <span>To date</span>
          <input
            type="date"
            value={value.date_to || ""}
            onChange={(e) => set("date_to", e.target.value || null)}
          />
        </label>
      </div>
      <Choice
        label="Date field"
        value={value.date_field}
        onChange={(v) => set("date_field", v)}
        options={["created_at", "due_date", "completed_at", "start_date"].map(
          (v) => ({ value: v, label: v.replace(/_/g, " ") }),
        )}
      />
      <Choice
        label="IANA timezone"
        value={value.timezone}
        onChange={(v) => set("timezone", v)}
        options={[
          ...new Set([
            value.timezone,
            "UTC",
            ...((Intl as any).supportedValuesOf?.("timeZone") || [
              "Asia/Kolkata",
              "Asia/Dubai",
              "Europe/London",
              "America/New_York",
            ]),
          ]),
        ].map((zone) => ({ value: String(zone), label: String(zone) }))}
      />
      <MultiChoice
        label="Projects"
        values={value.project_ids}
        onChange={(v) => set("project_ids", v)}
        options={(scope?.projects || []).map((p) => ({
          value: p.id,
          label: p.name,
        }))}
      />
      <MultiChoice
        label="Project statuses"
        values={value.project_statuses}
        onChange={(v) => set("project_statuses", v)}
        options={[...new Set((scope?.projects || []).map((p) => p.status))].map(
          (v) => ({ value: v, label: v }),
        )}
      />
      <MultiChoice
        label="Task statuses"
        values={value.statuses}
        onChange={(v) => set("statuses", v)}
        options={[
          "Backlog",
          "To Do",
          "In Progress",
          "In Review",
          "Blocked",
          "Done",
        ].map((v) => ({ value: v, label: v }))}
      />
      <MultiChoice
        label="Priorities"
        values={value.priorities}
        onChange={(v) => set("priorities", v)}
        options={["Low", "Medium", "High", "Urgent", "Critical"].map((v) => ({
          value: v,
          label: v,
        }))}
      />
      <MultiChoice
        label="Assignees"
        values={value.assignee_ids}
        onChange={(v) => set("assignee_ids", v)}
        options={(scope?.people || []).map((p) => ({
          value: p.id,
          label: p.name,
        }))}
      />
      <MultiChoice
        label="Teams"
        values={value.team_ids}
        onChange={(v) => set("team_ids", v)}
        options={(scope?.teams || []).map((p) => ({
          value: p.id,
          label: p.name,
        }))}
      />
      <MultiChoice
        label="Sprints"
        values={value.sprint_ids}
        onChange={(v) => set("sprint_ids", v)}
        options={(scope?.sprints || []).map((p) => ({
          value: p.id,
          label: p.name,
        }))}
      />
      <MultiChoice
        label="Tags"
        values={value.tag_ids}
        onChange={(v) => set("tag_ids", v)}
        options={(scope?.tags || []).map((p) => ({
          value: p.id,
          label: p.name,
        }))}
      />
      <Choice
        label="Custom field filter"
        value={String(value.custom_field_id || "")}
        onChange={(v) => set("custom_field_id", v ? Number(v) : null)}
        options={[
          { value: "", label: "No custom field filter" },
          ...(scope?.custom_fields || []).map((f) => ({
            value: String(f.id),
            label: f.name,
          })),
        ]}
      />
      {value.custom_field_id && (
        <label className="db-field">
          <span>Exact custom field value</span>
          <input
            value={value.custom_field_value}
            onChange={(e) => set("custom_field_value", e.target.value)}
          />
        </label>
      )}
      <small>
        Task-specific filters apply to task-based widgets. Time widgets use log
        dates. Financial data and time entries retain server access
        restrictions.
      </small>
    </div>
  );
}
export function WidgetSettings({
  initial,
  catalog,
  scope,
  onApply,
  onClose,
}: {
  initial: Widget;
  catalog: Catalog;
  scope?: Scope;
  onApply: (widget: Widget) => void;
  onClose: () => void;
}) {
  const [value, setValue] = useState(initial);
  const [tab, setTab] = useState("General");
  const patch = (key: keyof Widget, v: any) =>
    setValue((current) => ({ ...current, [key]: v }));
  const spec = catalog.widgets.find((w) => w.id === value.type)!;
  const supported = catalog.sources[value.source] || ["count"];
  return (
    <Panel
      open
      title="Widget settings"
      description="Changes apply only to this widget. Apply to preview them on the dashboard."
      onClose={onClose}
    >
      <div className="db-panel-tabs">
        {["General", "Data", "Appearance", "Filters"].map((t) => (
          <button key={t} aria-pressed={tab === t} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>
      {tab === "General" && (
        <>
          <label className="db-field">
            <span>Widget title</span>
            <input
              maxLength={120}
              value={value.title}
              onChange={(e) => patch("title", e.target.value)}
            />
          </label>
          <label className="db-field">
            <span>Description</span>
            <textarea
              maxLength={500}
              value={value.description}
              onChange={(e) => patch("description", e.target.value)}
            />
          </label>
          <Choice
            label="Widget icon"
            value={value.icon || "auto"}
            onChange={(v) => patch("icon", v)}
            options={[
              "auto",
              "chart",
              "tasks",
              "projects",
              "team",
              "calendar",
              "time",
              "target",
              "activity",
              "notes",
            ].map((v) => ({ value: v, label: v }))}
          />
          <Choice
            label="Data source"
            value={value.source}
            onChange={(v) =>
              setValue({
                ...value,
                source: v,
                metric: "count",
                aggregation: "count",
              })
            }
            options={Object.keys(catalog.sources).map((v) => ({
              value: v,
              label: v,
            }))}
          />
          <small>
            Specialized widgets use their named authoritative source. Generic
            charts, tables and datasets use the source you select.
          </small>
          {["notes", "bookmark", "image"].includes(value.type) && (
            <label className="db-field">
              <span>
                {value.type === "notes" ? "Note text (Markdown)" : "HTTPS URL"}
              </span>
              {value.type === "notes" && (
                <small>
                  Use # headings, **bold**, _italic_, `code`, and - list items.
                  HTML is displayed as text.
                </small>
              )}
              {value.type === "notes" ? (
                <textarea
                  rows={6}
                  maxLength={5000}
                  value={value.notes}
                  onChange={(e) => patch("notes", e.target.value)}
                />
              ) : (
                <input
                  type="url"
                  value={value.url}
                  onChange={(e) => patch("url", e.target.value)}
                />
              )}
            </label>
          )}
        </>
      )}
      {tab === "Data" && (
        <>
          <Choice
            label="Metric"
            value={value.metric}
            onChange={(v) =>
              setValue({
                ...value,
                metric: v,
                aggregation: v === "count" ? "count" : value.aggregation,
              })
            }
            options={supported.map((v) => ({
              value: v,
              label: v.replace(/_/g, " "),
            }))}
          />
          <Choice
            label="Aggregation"
            value={value.aggregation}
            onChange={(v) => patch("aggregation", v)}
            options={(value.metric === "count"
              ? ["count", "percentage"]
              : [
                  "count",
                  "sum",
                  "average",
                  "minimum",
                  "maximum",
                  "median",
                  "distinct_count",
                  "percentage",
                ]
            ).map((v) => ({ value: v, label: v.replace(/_/g, " ") }))}
          />
          <Choice
            label="Group by"
            value={value.group_by}
            onChange={(v) => patch("group_by", v)}
            options={[
              "status",
              "priority",
              "project",
              "assignee",
              "day",
              "week",
              "month",
              "quarter",
              "year",
            ].map((v) => ({ value: v, label: v }))}
          />
          <Choice
            label="Sort"
            value={value.sort}
            onChange={(v) => patch("sort", v)}
            options={[
              { value: "value_desc", label: "Value descending" },
              { value: "value_asc", label: "Value ascending" },
              { value: "name", label: "Name" },
            ]}
          />
          <label className="db-field">
            <span>Record or group limit</span>
            <input
              type="number"
              min={1}
              max={100}
              value={value.limit}
              onChange={(e) =>
                patch(
                  "limit",
                  Math.max(1, Math.min(100, Number(e.target.value))),
                )
              }
            />
          </label>
          {["formula", "radial", "gauge"].includes(value.type) && (
            <Choice
              label="Approved formula"
              value={value.formula}
              onChange={(v) => patch("formula", v)}
              options={[
                "completion_rate",
                "on_time_rate",
                "remaining_hours",
                "budget_utilization",
              ].map((v) => ({ value: v, label: v.replace(/_/g, " ") }))}
            />
          )}
          <label className="db-check">
            <input
              type="checkbox"
              checked={value.comparison}
              onChange={(e) => patch("comparison", e.target.checked)}
            />
            Compare metric with the previous equal date period
          </label>
          <small>
            Only recorded data is compared. No comparison is shown for missing
            or zero-baseline data. Custom SQL and executable formulas are not
            accepted.
          </small>
        </>
      )}
      {tab === "Appearance" && (
        <>
          <label className="db-field">
            <span>Chart color</span>
            <input
              type="color"
              value={value.color}
              onChange={(e) => patch("color", e.target.value)}
            />
          </label>
          <Choice
            label="Width"
            value={String(value.w)}
            onChange={(v) =>
              setValue({
                ...value,
                w: Number(v),
                x: Math.min(value.x, 12 - Number(v)),
              })
            }
            options={[
              [2, "⅙"],
              [3, "¼"],
              [4, "⅓"],
              [6, "½"],
              [8, "⅔"],
              [9, "¾"],
              [12, "Full width"],
            ].map(([v, l]) => ({ value: String(v), label: String(l) }))}
          />
          <label className="db-field">
            <span>Height in grid units</span>
            <input
              type="number"
              min={3}
              max={24}
              value={value.h}
              onChange={(e) =>
                patch("h", Math.max(3, Math.min(24, Number(e.target.value))))
              }
            />
          </label>
          <Choice
            label="Number format"
            value={value.number_format}
            onChange={(v) => patch("number_format", v)}
            options={["number", "percent", "hours"].map((v) => ({
              value: v,
              label: v,
            }))}
          />
          <label className="db-field">
            <span>Decimal places</span>
            <input
              type="number"
              min={0}
              max={4}
              value={value.decimals}
              onChange={(e) =>
                patch(
                  "decimals",
                  Math.max(0, Math.min(4, Number(e.target.value))),
                )
              }
            />
          </label>
          {(
            ["legend", "gridlines", "labels", "tooltips", "locked"] as const
          ).map((key) => (
            <label key={key} className="db-check">
              <input
                type="checkbox"
                checked={value[key]}
                onChange={(e) => patch(key, e.target.checked)}
              />
              {key === "locked" ? "Lock position" : key}
            </label>
          ))}
        </>
      )}
      {tab === "Filters" && (
        <>
          <label className="db-check">
            <input
              type="checkbox"
              checked={!!value.filters}
              onChange={(e) =>
                patch("filters", e.target.checked ? emptyFilters() : null)
              }
            />
            Override global filters for this widget
          </label>
          {value.filters && (
            <FilterFields
              value={value.filters}
              onChange={(v) => patch("filters", v)}
              scope={scope}
            />
          )}
        </>
      )}
      <div className="db-setting-preview">
        <strong>{value.title || spec.title}</strong>
        <small>
          {spec.title} · {value.source} · {value.w}/12 columns · {value.h} grid
          units
        </small>
        {spec.requirement && <p>{spec.requirement}</p>}
      </div>
      <footer className="db-panel-actions">
        <Button variant="outline" onClick={() => setValue(initial)}>
          Reset
        </Button>
        <Button variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button
          onClick={() => {
            onApply(value);
            onClose();
          }}
        >
          Apply & preview
        </Button>
      </footer>
    </Panel>
  );
}

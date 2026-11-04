import { NativeSelect } from "@/components/ui/native-select";
import { useEffect, useState } from "react";
import * as Popover from "@radix-ui/react-popover";
import * as Context from "@radix-ui/react-context-menu";
import {
  ArrowLeft,
  ArrowRight,
  Bookmark,
  Check,
  Columns3,
  Copy,
  Download,
  Filter,
  GripVertical,
  Layers,
  LayoutGrid,
  List,
  MoreHorizontal,
  Pin,
  Plus,
  RotateCcw,
  Save,
  Search,
  SlidersHorizontal,
  Table2,
  Trash2,
  Undo2,
  X,
} from "lucide-react";
import type {
  GridAction,
  GridColumn,
  GridDataSource,
  GridExportRequest,
  GridFilter,
  GridLayout,
  GridQuery,
  GridSavedView,
  GridValue,
} from "./types";
import { filterRules, setFieldFilter, removeField } from "./state";

export function GridContextMenu<T>({
  children,
  row,
  actions,
  open,
  copy,
  canCopy,
  run,
}: {
  children: React.ReactElement;
  row: T;
  actions: GridAction<T>[];
  open?: () => void;
  copy: () => void;
  canCopy: boolean;
  run: (action: GridAction<T>, row: T) => void;
}) {
  return (
    <Context.Root>
      <Context.Trigger asChild>{children}</Context.Trigger>
      <Context.Portal>
        <Context.Content className="udg-menu">
          {open && (
            <Context.Item onSelect={open}>
              <Table2 size={14} />
              Open record
            </Context.Item>
          )}
          <Context.Item disabled={!canCopy} onSelect={copy}>
            <Copy size={14} />
            Copy row
          </Context.Item>
          {actions
            .filter((a) => !a.visible || a.visible(row))
            .map((action) => (
              <Context.Item
                key={action.id}
                className={action.danger ? "danger" : ""}
                onSelect={() => run(action, row)}
              >
                {action.icon && <action.icon size={14} />} {action.label}
              </Context.Item>
            ))}
        </Context.Content>
      </Context.Portal>
    </Context.Root>
  );
}

export function ColumnManager<T>({
  columns,
  layout,
  update,
  autoFit,
}: {
  columns: GridColumn<T>[];
  layout: GridLayout;
  update: (layout: GridLayout) => void;
  autoFit: (id?: string) => void;
}) {
  function move(id: string, direction: number) {
    const order = [...layout.order],
      index = order.indexOf(id),
      next = Math.max(0, Math.min(order.length - 1, index + direction));
    order.splice(index, 1);
    order.splice(next, 0, id);
    update({ ...layout, order });
  }
  return (
    <Popover.Root>
      <Popover.Trigger className="udg-control">
        <Columns3 size={15} />
        Columns
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          className="udg-popover udg-column-manager"
          align="end"
          sideOffset={8}
        >
          <header>
            <strong>Manage columns</strong>
            <Popover.Close aria-label="Close column manager">
              <X size={15} />
            </Popover.Close>
          </header>
          <p>Drag headers, or use the arrow buttons.</p>
          {layout.order.map((id, index) => {
            const column = columns.find((c) => c.id === id);
            if (!column) return null;
            return (
              <div key={id} className="udg-column-option">
                <label>
                  <input
                    type="checkbox"
                    checked={layout.visibility[id] !== false}
                    onChange={(e) =>
                      update({
                        ...layout,
                        visibility: {
                          ...layout.visibility,
                          [id]: e.target.checked,
                        },
                      })
                    }
                  />
                  {column.title}
                </label>
                <button
                  aria-label={`Move ${column.title} left`}
                  disabled={!index}
                  onClick={() => move(id, -1)}
                >
                  <ArrowLeft size={13} />
                </button>
                <button
                  aria-label={`Move ${column.title} right`}
                  disabled={index === layout.order.length - 1}
                  onClick={() => move(id, 1)}
                >
                  <ArrowRight size={13} />
                </button>
                <NativeSelect
                  aria-label={`Pin ${column.title}`}
                  value={
                    layout.pinning.left?.includes(id)
                      ? "left"
                      : layout.pinning.right?.includes(id)
                        ? "right"
                        : "none"
                  }
                  onChange={(e) => {
                    const left = (layout.pinning.left || []).filter(
                        (v) => v !== id,
                      ),
                      right = (layout.pinning.right || []).filter(
                        (v) => v !== id,
                      );
                    if (e.target.value === "left") left.push(id);
                    if (e.target.value === "right") right.push(id);
                    update({ ...layout, pinning: { left, right } });
                  }}
                >
                  <option value="none">Unpinned</option>
                  <option value="left">Left</option>
                  <option value="right">Right</option>
                </NativeSelect>
              </div>
            );
          })}
          <button className="udg-control" onClick={() => autoFit()}>
            Auto-fit all columns
          </button>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function SavedViewsManager({
  views,
  save,
  load,
  remove,
}: {
  views: GridSavedView[];
  save: (name: string) => void;
  load: (view: GridSavedView) => void;
  remove: (id: string) => void;
}) {
  const [name, setName] = useState("");
  return (
    <Popover.Root>
      <Popover.Trigger className="udg-control">
        <Bookmark size={15} />
        Saved views
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="udg-popover" align="end" sideOffset={8}>
          <header>
            <strong>My saved views</strong>
            <Popover.Close aria-label="Close saved views">
              <X size={15} />
            </Popover.Close>
          </header>
          {views.map((view) => (
            <div className="udg-view-option" key={view.id}>
              <button onClick={() => load(view)}>
                <Bookmark size={13} />
                {view.name}
              </button>
              <button
                aria-label={`Delete view ${view.name}`}
                onClick={() => remove(view.id)}
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
          {!views.length && <p>No saved views yet.</p>}
          <input
            aria-label="Saved view name"
            placeholder="Name this view…"
            maxLength={80}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <button
            className="udg-primary"
            disabled={!name.trim()}
            onClick={() => {
              save(name.trim());
              setName("");
            }}
          >
            <Save size={14} />
            Save current view
          </button>
          <small>
            Includes columns, pinning, density, sorting, filters and grouping.
          </small>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function GridExportMenu({
  selectedCount,
  visibleCount,
  allowed,
  columns,
  selectedColumns,
  setColumns,
  run,
  busy,
  formats,
}: {
  selectedCount: number;
  visibleCount: number;
  allowed: boolean;
  columns: { id: string; title: string }[];
  selectedColumns: string[];
  setColumns: (ids: string[]) => void;
  run: (
    format: GridExportRequest["format"],
    scope: GridExportRequest["scope"],
    groups: boolean,
    summaries: boolean,
  ) => void;
  busy: boolean;
  formats?: GridExportRequest["format"][];
}) {
  const [scope, setScope] = useState<GridExportRequest["scope"]>("visible"),
    [groups, setGroups] = useState(false),
    [summaries, setSummaries] = useState(true);
  if (!allowed) return null;
  return (
    <Popover.Root>
      <Popover.Trigger className="udg-control" disabled={busy}>
        <Download size={15} />
        {busy ? "Exporting…" : "Export"}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="udg-popover" align="end" sideOffset={8}>
          <header>
            <strong>Export data</strong>
            <Popover.Close aria-label="Close export menu">
              <X size={15} />
            </Popover.Close>
          </header>
          <label>
            Rows
            <NativeSelect
              aria-label="Export rows"
              value={scope}
              onChange={(e) => setScope(e.target.value as typeof scope)}
            >
              <option value="visible">
                Current loaded rows ({visibleCount})
              </option>
              <option value="selected" disabled={!selectedCount}>
                Selected rows ({selectedCount})
              </option>
              <option value="filtered">All filtered rows</option>
            </NativeSelect>
          </label>
          <details>
            <summary>Export columns ({selectedColumns.length})</summary>
            {columns.map((c) => (
              <label className="udg-check" key={c.id}>
                <input
                  type="checkbox"
                  checked={selectedColumns.includes(c.id)}
                  onChange={(e) =>
                    setColumns(
                      e.target.checked
                        ? [...selectedColumns, c.id]
                        : selectedColumns.filter((id) => id !== c.id),
                    )
                  }
                />
                {c.title}
              </label>
            ))}
          </details>
          <label className="udg-check">
            <input
              type="checkbox"
              checked={groups}
              onChange={(e) => setGroups(e.target.checked)}
            />
            Include group labels
          </label>
          <label className="udg-check">
            <input
              type="checkbox"
              checked={summaries}
              onChange={(e) => setSummaries(e.target.checked)}
            />
            Include summaries
          </label>
          <div className="udg-export-formats">
            {(
              [
                ["xlsx", "Excel (.xlsx)"],
                ["csv", "CSV"],
                ["pdf", "PDF"],
                ["clipboard", "Copy to clipboard"],
              ] as const
            ).filter(([format]) => !formats || formats.includes(format)).map(([format, label]) => (
              <button
                key={format}
                disabled={
                  busy ||
                  !selectedColumns.length ||
                  (scope === "selected" && !selectedCount)
                }
                onClick={() => run(format, scope, groups, summaries)}
              >
                {format === "clipboard" ? (
                  <Copy size={14} />
                ) : (
                  <Download size={14} />
                )}{" "}
                {label}
              </button>
            ))}
          </div>
          <small>
            Exports use server permissions and the active filters. Excel/CSV:
            20,000 rows; PDF: 2,000.
          </small>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function GridToolbar({
  search,
  setSearch,
  filterCount,
  openFilters,
  layout,
  updateLayout,
  views,
  extra,
  children,
  undo,
  reset,
  searchPlaceholder,
}: {
  search: string;
  setSearch: (s: string) => void;
  filterCount: number;
  openFilters: () => void;
  layout: GridLayout;
  updateLayout: (layout: GridLayout) => void;
  views: GridLayout["view"][];
  extra?: React.ReactNode;
  children: React.ReactNode;
  undo?: () => void;
  reset: () => void;
  searchPlaceholder?: string;
}) {
  return (
    <div className="udg-toolbar">
      <label className="udg-search">
        <Search size={16} />
        <input
          aria-label="Search grid"
          placeholder={searchPlaceholder || "Search all records…"}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {search && (
          <button aria-label="Clear grid search" onClick={() => setSearch("")}>
            <X size={13} />
          </button>
        )}
      </label>
      <button
        className={`udg-control ${filterCount ? "is-active" : ""}`}
        onClick={openFilters}
      >
        <Filter size={14} />
        Filters{filterCount > 0 && <b>{filterCount}</b>}
      </button>
      {children}
      <Popover.Root>
        <Popover.Trigger
          className="udg-control"
          aria-label="Grid display options"
        >
          <SlidersHorizontal size={15} />
        </Popover.Trigger>
        <Popover.Portal>
          <Popover.Content className="udg-popover" align="end">
            <strong>Display & layout</strong>
            <label>
              Density
              <NativeSelect
                aria-label="Grid density"
                value={layout.density}
                onChange={(e) =>
                  updateLayout({
                    ...layout,
                    density: e.target.value as GridLayout["density"],
                    rowHeight: e.target.value === "compact" ? 38 : 54,
                  })
                }
              >
                <option value="compact">Compact</option>
                <option value="comfortable">Comfortable</option>
              </NativeSelect>
            </label>
            <label>
              Row height: {layout.rowHeight}px
              <input
                aria-label="Row height"
                type="range"
                min="32"
                max="88"
                value={layout.rowHeight}
                onChange={(e) =>
                  updateLayout({ ...layout, rowHeight: Number(e.target.value) })
                }
              />
            </label>
            {views.length > 1 && (
              <label>
                View
                <NativeSelect
                  aria-label="Grid view"
                  value={layout.view}
                  onChange={(e) =>
                    updateLayout({
                      ...layout,
                      view: e.target.value as GridLayout["view"],
                    })
                  }
                >
                  {views.map((v) => (
                    <option value={v} key={v}>
                      {v}
                    </option>
                  ))}
                </NativeSelect>
              </label>
            )}
            <button className="udg-control" onClick={reset}>
              <RotateCcw size={14} />
              Reset columns
            </button>
            <button className="udg-control" disabled={!undo} onClick={undo}>
              <Undo2 size={14} />
              Undo layout change
            </button>
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>
      {extra}
    </div>
  );
}

export function ColumnValueFilter<T>({
  column,
  source,
  query,
  apply,
}: {
  column: GridColumn<T>;
  source: GridDataSource<T>;
  query: GridQuery;
  apply: (filter: GridFilter) => void;
}) {
  const [open, setOpen] = useState(false),
    [search, setSearch] = useState(""),
    [choices, setChoices] = useState<
      { value: GridValue; label: string; count?: number }[]
    >([]),
    [more, setMore] = useState(false),
    [error, setError] = useState(""),
    [checked, setChecked] = useState<GridValue[]>([]);
  useEffect(() => {
    if (!open) return;
    const rule = filterRules(query.filters).find(
      (r) => r.field === column.id && r.operator === "in",
    );
    setChecked(Array.isArray(rule?.value) ? rule.value : []);
  }, [open, column.id]);
  useEffect(() => {
    if (!open || !source.facets) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      source.facets!(column.id, search, query, controller.signal)
        .then((r) => {
          setChoices(r.values);
          setMore(!!r.hasMore);
          setError("");
        })
        .catch(() => {
          if (!controller.signal.aborted)
            setError("Could not load filter values.");
        });
    }, 200);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [
    open,
    search,
    column.id,
    source.key,
    JSON.stringify(query.filters),
    query.search,
  ]);
  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger
        className={`udg-header-filter ${filterRules(query.filters).some((r) => r.field === column.id) ? "is-active" : ""}`}
        aria-label={`Filter ${column.title}`}
      >
        <Filter size={13} />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          className="udg-popover udg-facets"
          align="start"
          sideOffset={7}
        >
          <header>
            <strong>{column.title} filter</strong>
            <Popover.Close aria-label="Close column filter">
              <X size={14} />
            </Popover.Close>
          </header>
          <label className="udg-search">
            <Search size={14} />
            <input
              aria-label={`Search ${column.title} filter values`}
              placeholder="Search values…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          {error && <p role="alert">{error}</p>}
          <div className="udg-facet-values">
            {choices.map((choice, index) => (
              <label className="udg-check" key={index}>
                <input
                  type="checkbox"
                  checked={checked.includes(choice.value)}
                  onChange={(e) =>
                    setChecked(
                      e.target.checked
                        ? [...checked, choice.value]
                        : checked.filter((v) => v !== choice.value),
                    )
                  }
                />
                <span>{choice.label}</span>
                <small>{choice.count}</small>
              </label>
            ))}
          </div>
          {more && <small>Refine your search to see more values.</small>}
          <div className="udg-popover-actions">
            <button
              onClick={() => {
                apply(removeField(query.filters, column.id));
                setOpen(false);
              }}
            >
              Clear field
            </button>
            <button
              className="udg-primary"
              onClick={() => {
                apply(
                  setFieldFilter(query.filters, {
                    field: column.id,
                    operator: "in",
                    value: checked,
                  }),
                );
                setOpen(false);
              }}
            >
              Apply
            </button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

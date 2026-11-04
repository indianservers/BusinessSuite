import { SuiteDistribution, SuiteIllustration } from "@/components/visuals/SuiteVisuals";
import { useMobile } from "@/components/mobile/useMobile";
import PhoneActions, { isPhoneField } from "@/components/PhoneActions";
import { NativeSelect } from "@/components/ui/native-select";
import { recordPreviewProps } from "@/components/RecordQuickPreview";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  useReactTable,
  getCoreRowModel,
  getExpandedRowModel,
  type ColumnDef,
  type Column,
  type ExpandedState,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  DndContext,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  useDroppable,
  closestCenter,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  horizontalListSortingStrategy,
  sortableKeyboardCoordinates,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import * as Dropdown from "@radix-ui/react-dropdown-menu";
import * as Context from "@radix-ui/react-context-menu";
import {
  ArrowDown,
  ArrowUp,
  ArrowDownUp,
  ArrowLeft,
  ArrowRight,
  ChevronDown,
  ChevronRight,
  Copy,
  GripVertical,
  Layers,
  Maximize2,
  MoreHorizontal,
  Pin,
  PinOff,
  Plus,
  RefreshCw,
  Search,
  SquarePen,
  X,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import type {
  GridColumn,
  GridGroup,
  GridLayout,
  GridQuery,
  GridResult,
  GridSavedView,
  GridExportRequest,
  GridAction,
  SharedDataGridProps,
} from "./types";
import { emptyQuery } from "./types";
import {
  defaultLayout,
  filterRules,
  querySignature,
  removeRule,
  sanitizeLayout,
  sanitizeQuery,
} from "./state";
import FilterBuilder from "./FilterBuilder";
import {
  ColumnManager,
  ColumnValueFilter,
  GridContextMenu,
  GridExportMenu,
  GridToolbar,
  SavedViewsManager,
} from "./GridControls";
import "./data-grid.css";
import GridRecordPane from "./GridRecordPane";
import { Eye } from "lucide-react";
import { useLocation } from "react-router-dom";

type Node<T> = {
  id: string;
  record?: T;
  group?: GridGroup;
  more?: { path: GridGroup["path"]; page: number; parent: string };
  children?: Node<T>[];
};
const groupId = (path: GridGroup["path"]) => `group:${JSON.stringify(path)}`;
const errorText = (e: unknown) => {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response
    ?.data?.detail;
  return typeof detail === "string"
    ? detail
    : "The grid request could not be completed. Check your connection and filter values, then retry.";
};
const formatMoney = (value: number, currency?: string) => {
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency || "INR",
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return `${currency || ""} ${value.toLocaleString()}`;
  }
};

function GroupChip({
  id,
  title,
  remove,
}: {
  id: string;
  title: string;
  remove: () => void;
}) {
  const drag = useSortable({ id: `group-column:${id}` });
  return (
    <span
      ref={drag.setNodeRef}
      style={{
        transform: CSS.Transform.toString(drag.transform),
        transition: drag.transition,
      }}
    >
      <button
        aria-label={`Reorder group ${title}`}
        {...drag.attributes}
        {...drag.listeners}
      >
        <GripVertical size={12} />
      </button>
      {title}
      <button aria-label={`Remove grouping ${title}`} onClick={remove}>
        <X size={12} />
      </button>
    </span>
  );
}
export function GroupingPanel({
  columns,
  query,
  change,
}: {
  columns: { id: string; title: string; groupable?: boolean }[];
  query: GridQuery;
  change: (query: GridQuery) => void;
}) {
  const drop = useDroppable({ id: "grid-group-zone" });
  return (
    <div
      className={`udg-grouping ${drop.isOver ? "is-over" : ""}`}
      ref={drop.setNodeRef}
    >
      <Layers size={15} />
      <span>Group by</span>
      <SortableContext
        items={query.grouping.map((id) => `group-column:${id}`)}
        strategy={horizontalListSortingStrategy}
      >
        {query.grouping.map((id) => (
          <GroupChip
            key={id}
            id={id}
            title={columns.find((c) => c.id === id)?.title || id}
            remove={() =>
              change({
                ...query,
                grouping: query.grouping.filter((v) => v !== id),
                path: [],
                page: 1,
              })
            }
          />
        ))}
      </SortableContext>
      {!query.grouping.length && (
        <small>Drag a column here to group the full dataset</small>
      )}
      <NativeSelect
        aria-label="Add grouping column"
        value=""
        onChange={(e) => {
          if (e.target.value)
            change({
              ...query,
              grouping: [...query.grouping, e.target.value],
              path: [],
              page: 1,
            });
        }}
      >
        <option value="">+ Add group</option>
        {columns
          .filter(
            (c) =>
              c.groupable !== false &&
              !query.grouping.includes(c.id) &&
              query.grouping.length < 4,
          )
          .map((c) => (
            <option key={c.id} value={c.id}>
              {c.title}
            </option>
          ))}
      </NativeSelect>
    </div>
  );
}

function Header<T>({
  column,
  definition,
  style,
  source,
  query,
  change,
  autoFit,
  move,
  resizeHandler,
  resizeKey,
}: {
  column: Column<Node<T>, unknown>;
  definition: GridColumn<T>;
  style: CSSProperties;
  source: SharedDataGridProps<T>["dataSource"];
  query: GridQuery;
  change: (query: GridQuery) => void;
  autoFit: (id?: string) => void;
  move: (id: string, delta: number) => void;
  resizeHandler: (event: unknown) => void;
  resizeKey: (delta: number) => void;
}) {
  const drag = useSortable({ id: `column:${column.id}` });
  const sort = column.getIsSorted();
  const Icon = definition.icon;
  return (
    <div
      role="columnheader"
      aria-colindex={column.getIndex() + 2}
      aria-sort={sort ? (sort === "asc" ? "ascending" : "descending") : "none"}
      className={`udg-th udg-align-${definition.align || (["number", "currency"].includes(definition.type || "") ? "right" : "left")}`}
      data-column={column.id}
      ref={drag.setNodeRef}
      style={{
        ...style,
        transform: CSS.Transform.toString(drag.transform),
        transition: drag.transition,
        opacity: drag.isDragging ? 0.5 : 1,
      }}
    >
      <button
        className="udg-column-grip"
        aria-label={`Drag ${definition.title} column`}
        {...drag.attributes}
        {...drag.listeners}
      >
        <GripVertical size={12} />
      </button>
      {definition.header ? <div className="udg-legacy-heading">{definition.header}</div> : <button
        type="button"
        className="udg-sort-button"
        disabled={definition.sortable === false}
        onClick={column.getToggleSortingHandler()}
        title="Click to sort; Shift-click for multiple columns"
      >
        {Icon && <Icon size={13} />}
        <span>{definition.title}</span>
        {sort ? (
          sort === "asc" ? (
            <ArrowUp size={13} />
          ) : (
            <ArrowDown size={13} />
          )
        ) : (
          <ArrowDownUp size={11} className="udg-sort-hint" />
        )}
        {sort && query.sorting.length > 1 && (
          <small>
            {query.sorting.findIndex((s) => s.id === column.id) + 1}
          </small>
        )}
      </button>}
      {definition.filterable !== false && source.facets && (
        <ColumnValueFilter
          column={definition}
          source={source}
          query={query}
          apply={(filters) => change({ ...query, filters, page: 1 })}
        />
      )}
      <Dropdown.Root>
        <Dropdown.Trigger
          className="udg-column-more"
          aria-label={`Column menu ${definition.title}`}
        >
          <MoreHorizontal size={14} />
        </Dropdown.Trigger>
        <Dropdown.Portal>
          <Dropdown.Content className="udg-menu" align="start" sideOffset={7}>
            {definition.sortable !== false && (
              <>
                <Dropdown.Item
                  onSelect={() => column.toggleSorting(false, true)}
                >
                  <ArrowUp size={14} />
                  Sort ascending
                </Dropdown.Item>
                <Dropdown.Item
                  onSelect={() => column.toggleSorting(true, true)}
                >
                  <ArrowDown size={14} />
                  Sort descending
                </Dropdown.Item>
                <Dropdown.Item onSelect={() => column.clearSorting()}>
                  <X size={14} />
                  Clear sorting
                </Dropdown.Item>
                <Dropdown.Separator />
              </>
            )}
            <Dropdown.Item onSelect={() => column.pin("left")}>
              <Pin size={14} />
              Pin left
            </Dropdown.Item>
            <Dropdown.Item onSelect={() => column.pin("right")}>
              <Pin size={14} />
              Pin right
            </Dropdown.Item>
            <Dropdown.Item onSelect={() => column.pin(false)}>
              <PinOff size={14} />
              Unpin
            </Dropdown.Item>
            <Dropdown.Item onSelect={() => autoFit(column.id)}>
              <Maximize2 size={14} />
              Auto-fit column
            </Dropdown.Item>
            <Dropdown.Item onSelect={() => move(column.id, -1)}>
              <ArrowLeft size={14} />
              Move left
            </Dropdown.Item>
            <Dropdown.Item onSelect={() => move(column.id, 1)}>
              <ArrowRight size={14} />
              Move right
            </Dropdown.Item>
            {definition.groupable !== false &&
              !query.grouping.includes(column.id) &&
              query.grouping.length < 4 && (
                <Dropdown.Item
                  onSelect={() =>
                    change({
                      ...query,
                      grouping: [...query.grouping, column.id],
                      page: 1,
                      path: [],
                    })
                  }
                >
                  <Layers size={14} />
                  Group by this column
                </Dropdown.Item>
              )}
            <Dropdown.Item onSelect={() => column.toggleVisibility(false)}>
              <X size={14} />
              Hide column
            </Dropdown.Item>
          </Dropdown.Content>
        </Dropdown.Portal>
      </Dropdown.Root>
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label={`Resize ${definition.title}`}
        aria-valuenow={Math.round(column.getSize())}
        tabIndex={0}
        className={`udg-resize ${column.getIsResizing() ? "is-resizing" : ""}`}
        onMouseDown={resizeHandler}
        onTouchStart={resizeHandler}
        onDoubleClick={() => autoFit(column.id)}
        onKeyDown={(e) => {
          if (["ArrowLeft", "ArrowRight"].includes(e.key)) {
            e.preventDefault();
            resizeKey(e.key === "ArrowLeft" ? -10 : 10);
          }
        }}
      />
    </div>
  );
}

function validateGridResult<T>(result: GridResult<T>): GridResult<T> {
  if (!result || !Array.isArray(result.rows) || !Number.isFinite(result.total)) {
    throw new Error("The table response was incomplete. Refresh to try again.");
  }
  return result;
}

export default function SharedDataGrid<T>(props: SharedDataGridProps<T>) {
  const [focused, setFocused] = useState<T>();
  const location = useLocation();
  useEffect(() => setFocused(undefined), [props.dataSource.key, location.pathname, location.search]);
  const canPreview = props.detailsEnabled !== false && !props.onSelectRecord;
  const preview = (row: T) => setFocused(row);
  const titleColumn = props.columns.find(c => !/^(select|actions?|quick actions)$/i.test(c.title)) || props.columns[0];
  const title = focused === undefined ? "" : String(titleColumn?.accessor?.(focused) ?? (focused as Record<string, unknown>)[titleColumn?.id] ?? "Record");
  return <div className={`udg-workspace ${focused !== undefined ? "has-details" : ""}`}>
    <div className="udg-workspace-main"><GridEngine {...props}
      onSelectRecord={props.onSelectRecord || (canPreview ? preview : undefined)}
      onOpen={props.onOpen || (canPreview ? preview : undefined)}
      rowActions={canPreview ? [{ id: "suite-preview", label: "Preview record", icon: Eye, quick: true, run: preview }, ...(props.rowActions || [])] : props.rowActions}
    /></div>
    {focused !== undefined && <GridRecordPane title={title} close={() => setFocused(undefined)} expand={props.onOpen ? () => props.onOpen?.(focused) : undefined}>
      {props.renderDetails ? props.renderDetails(focused) : <dl className="udg-details-fields">{props.columns.filter(c => c.id !== "actions").map(column => {
        const value = column.accessor ? column.accessor(focused) : (focused as Record<string, unknown>)[column.id];
        return <div key={column.id}><dt>{column.title}</dt><dd>{value == null || value === "" ? "—" : String(value)}</dd></div>;
      })}</dl>}
    </GridRecordPane>}
  </div>;
}

function GridEngine<T>(props: SharedDataGridProps<T>) {
  const {
    columns,
    dataSource,
    getRowId,
    onOpen,
    onEdit,
    rowActions = [],
    gridId,
  } = props;
  const user = useAuthStore((s) => s.user),
    client = useQueryClient();
  const preferenceKey = `suite-grid:v1:${props.organizationId ?? user?.access?.companyId ?? 0}:${props.userId ?? user?.id ?? 0}:${props.workspaceId ?? "organization"}:${gridId}`;
  const initial = useMemo(() => {
    let saved: {
      layout?: GridLayout;
      query?: GridQuery;
      views?: GridSavedView[];
    } = {};
    try {
      saved = JSON.parse(localStorage.getItem(preferenceKey) || "{}");
    } catch {
      /* Defaults remain usable. */
    }
    return {
      layout: sanitizeLayout(
        { ...defaultLayout(columns), ...props.initialLayout, ...saved.layout },
        columns,
      ),
      query: sanitizeQuery(
        {
          ...emptyQuery(),
          ...props.initialQuery,
          ...saved.query,
          ...props.queryState,
          page: props.queryState?.page || 1,
          path: [],
        },
        columns,
      ),
      views: Array.isArray(saved.views)
        ? saved.views
            .filter(
              (view) =>
                view &&
                typeof view.name === "string" &&
                typeof view.id === "string",
            )
            .slice(0, 50)
            .map((view) => ({
              ...view,
              layout: sanitizeLayout(view.layout, columns),
              query: sanitizeQuery(view.query, columns),
            }))
        : [],
    };
  }, [preferenceKey]);
  const [layout, setLayout] = useState(initial.layout),
    [query, setQuery] = useState<GridQuery>(initial.query),
    [views, setViews] = useState<GridSavedView[]>(initial.views);
  const mobile = useMobile();
  const effectiveRowHeight = mobile ? Math.max(48, layout.rowHeight) : layout.rowHeight;
  const restoredViewQuery = useRef<string>();
  const selectRecordTimer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => () => clearTimeout(selectRecordTimer.current), [dataSource.key]);
  function selectRecord(row: T) {
    clearTimeout(selectRecordTimer.current);
    if (props.onSelectRecord) selectRecordTimer.current = setTimeout(() => props.onSelectRecord?.(row), 250);
  }
  const [search, setSearch] = useState(initial.query.search),
    [filterOpen, setFilterOpen] = useState(false),
    [notice, setNotice] = useState(""),
    [actionError, setActionError] = useState("");
  const [children, setChildren] = useState<Record<string, Node<T>[]>>({}),
    [expanded, setExpanded] = useState<ExpandedState>({}),
    [loadingGroups, setLoadingGroups] = useState<Set<string>>(new Set());
  const [internalSelection, setInternalSelection] = useState<string[]>([]),
    selection = props.selectedIds ?? internalSelection;
  const selectedCache = useRef(new Map<string, T>()),
    lastSelected = useRef<string>(),
    history = useRef<GridLayout[]>([]);
  const [historySize, setHistorySize] = useState(0),
    [exportBusy, setExportBusy] = useState(false),
    [exportColumns, setExportColumns] = useState(
      props.defaultExportColumns || columns.map((c) => c.id),
    );
  const [edit, setEdit] = useState<{
    row: string;
    column: string;
    value: string;
    error?: string;
    busy?: boolean;
  }>();
  const [active, setActive] = useState<{ row: string; column: string }>(),
    [range, setRange] = useState<{
      start: { row: string; column: string };
      end: { row: string; column: string };
    }>();
  const scroll = useRef<HTMLDivElement>(null),
    currentQuery = useRef(querySignature(query)),
    mounted = useRef(true);
  useEffect(
    () => () => {
      mounted.current = false;
    },
    [],
  );
  useEffect(() => {
    setLayout(initial.layout);
    setQuery(initial.query);
    setViews(initial.views);
    setSearch(initial.query.search);
    setChildren({});
    setExpanded({});
    history.current = [];
    selectedCache.current.clear();
  }, [preferenceKey]);
  useEffect(() => {
    if (
      props.queryState &&
      JSON.stringify(props.queryState) !== JSON.stringify(query)
    ) {
      setQuery(props.queryState);
      setSearch(props.queryState.search);
    }
  }, [JSON.stringify(props.queryState)]);
  useEffect(() => {
    const timer = setTimeout(
      () =>
        setQuery((q) => (q.search === search ? q : { ...q, search, page: 1 })),
      300,
    );
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    try {
      localStorage.setItem(
        preferenceKey,
        JSON.stringify({
          layout,
          query: { ...query, path: [], page: 1 },
          views,
        }),
      );
    } catch {
      setNotice("Layout could not be saved in this browser.");
    }
  }, [preferenceKey, layout, query, views]);
  useEffect(() => {
    const handled = restoredViewQuery.current === JSON.stringify(query);
    restoredViewQuery.current = undefined;
    if (!handled) props.onQueryChange?.(query);
  }, [JSON.stringify(query)]);
  const selectionContext = JSON.stringify({
    search: query.search,
    filters: query.filters,
    source: dataSource.key,
    preferenceKey,
  });
  const previousSelectionContext = useRef(selectionContext);
  useEffect(() => {
    if (previousSelectionContext.current !== selectionContext) {
      previousSelectionContext.current = selectionContext;
      emitSelection([]);
      lastSelected.current = undefined;
      setRange(undefined);
    }
  }, [selectionContext]);
  const signature = querySignature(query);
  useEffect(() => {
    currentQuery.current = signature;
    setChildren({});
    setExpanded({});
  }, [signature, query.page, props.refreshKey, dataSource.key]);
  const request = useQuery({
    queryKey: [
      "shared-grid",
      preferenceKey,
      dataSource.key,
      query,
      props.refreshKey,
    ],
    queryFn: async ({ signal }) => validateGridResult(await dataSource.load(query, signal)),
    staleTime: 15000,
    gcTime: 60000,
    refetchOnWindowFocus: true,
    retry: 1,
  });
  useEffect(() => {
    if (request.data) props.onResult?.(request.data);
  }, [request.data]);
  const result = request.data,
    permissions = result?.permissions || {};
  const normalize = useCallback(
    (result: GridResult<T>): Node<T>[] =>
      result.groups?.length
        ? result.groups.map((group) => ({ id: groupId(group.path), group }))
        : result.rows.map((record) => ({ id: getRowId(record), record })),
    [getRowId],
  );
  const nodes = useMemo(() => {
    function populate(items: Node<T>[]): Node<T>[] {
      return items.map((node) =>
        node.group && children[node.id]
          ? { ...node, children: populate(children[node.id]) }
          : node,
      );
    }
    return populate(result ? normalize(result) : []);
  }, [result, children, normalize]);
  const updateLayout = useCallback(
    (next: GridLayout) => {
      history.current = [
        ...history.current.slice(-19),
        structuredClone(layout),
      ];
      setHistorySize(history.current.length);
      setLayout(sanitizeLayout(next, columns));
    },
    [layout, columns],
  );
  function undo() {
    const previous = history.current.pop();
    if (previous) {
      setLayout(previous);
      setHistorySize(history.current.length);
    }
  }
  const changeQuery = (next: GridQuery) => {
    setQuery(next);
    setSearch(next.search);
    setActionError("");
  };
  const [viewportWidth, setViewportWidth] = useState(0);
  useEffect(() => {
    const element = scroll.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) =>
      setViewportWidth(entries[0].contentRect.width),
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [layout.view]);
  const effectivePinning = useMemo(
    () =>
      viewportWidth > 0 && viewportWidth < 650
        ? { left: (layout.pinning.left || []).slice(0, 1), right: [] }
        : layout.pinning,
    [layout.pinning, viewportWidth],
  );
  const effectiveSizes = useMemo(() => {
    const first = effectivePinning.left?.[0];
    if (!first || !viewportWidth || viewportWidth >= 650) return layout.sizes;
    return {
      ...layout.sizes,
      [first]: Math.min(
        layout.sizes[first] ||
          columns.find((c) => c.id === first)?.width ||
          160,
        Math.max(100, Math.min(180, viewportWidth - 160)),
      ),
    };
  }, [layout.sizes, effectivePinning, viewportWidth, columns]);
  const columnDefs = useMemo<ColumnDef<Node<T>>[]>(
    () =>
      columns.map((c) => ({
        id: c.id,
        header: c.title,
        size: c.width || 160,
        minSize: c.minWidth || 70,
        maxSize: 800,
        enableSorting: c.sortable !== false,
        accessorFn: (node) =>
          node.record
            ? c.accessor
              ? c.accessor(node.record)
              : (node.record as Record<string, unknown>)[c.id]
            : undefined,
      })),
    [columns],
  );
  const table = useReactTable({
    data: nodes,
    columns: columnDefs,
    getRowId: (node) => node.id,
    getSubRows: (node) => node.children,
    getRowCanExpand: (row) => !!row.original.group,
    getCoreRowModel: getCoreRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
    manualPagination: true,
    manualSorting: true,
    manualFiltering: true,
    manualGrouping: true,
    enableMultiSort: true,
    maxMultiSortColCount: 6,
    columnResizeMode: "onChange",
    state: {
      columnOrder: layout.order,
      columnVisibility: layout.visibility,
      columnPinning: effectivePinning,
      columnSizing: effectiveSizes,
      sorting: query.sorting,
      expanded,
    },
    onExpandedChange: setExpanded,
    onSortingChange: (updater) =>
      setQuery((q) => ({
        ...q,
        sorting: typeof updater === "function" ? updater(q.sorting) : updater,
        page: 1,
      })),
    onColumnPinningChange: (updater) =>
      updateLayout({
        ...layout,
        pinning:
          typeof updater === "function" ? updater(layout.pinning) : updater,
      }),
    onColumnVisibilityChange: (updater) =>
      updateLayout({
        ...layout,
        visibility:
          typeof updater === "function" ? updater(layout.visibility) : updater,
      }),
    onColumnSizingChange: (updater) =>
      setLayout((l) => ({
        ...l,
        sizes: typeof updater === "function" ? updater(l.sizes) : updater,
      })),
  });
  const modelRows = table.getRowModel().rows,
    recordNodes = modelRows.filter((row) => row.original.record),
    visibleRecords = recordNodes.map((row) => row.original.record!);
  const left = table.getLeftVisibleLeafColumns(),
    center = table.getCenterVisibleLeafColumns(),
    right = table.getRightVisibleLeafColumns(),
    ordered = [...left, ...center, ...right];
  const rowVirtual = useVirtualizer({
    count: modelRows.length,
    getScrollElement: () => scroll.current,
    estimateSize: () => effectiveRowHeight,
    overscan: 8,
    scrollMargin: 40,
    scrollPaddingStart: 40,
    getItemKey: (index) => modelRows[index]?.id || index,
  });
  const columnVirtual = useVirtualizer({
    count: center.length,
    horizontal: true,
    getScrollElement: () => scroll.current,
    estimateSize: (index) => center[index]?.getSize() || 160,
    overscan: 3,
    scrollMargin: 40 + table.getLeftTotalSize(),
    getItemKey: (index) => center[index]?.id || index,
  });
  useEffect(() => {
    rowVirtual.measure();
  }, [effectiveRowHeight]);
  useEffect(() => {
    columnVirtual.measure();
  }, [effectiveSizes, layout.order, layout.visibility, effectivePinning]);
  const virtualColumns = columnVirtual.getVirtualItems(),
    virtualRows = rowVirtual.getVirtualItems();
  const horizontal = center.length > 24;
  const centerColumns = horizontal
    ? virtualColumns.map((v) => center[v.index]).filter(Boolean)
    : center;
  const before =
    horizontal && virtualColumns.length
      ? Math.max(0, virtualColumns[0].start - 40 - table.getLeftTotalSize())
      : 0;
  const after =
    horizontal && virtualColumns.length
      ? Math.max(
          0,
          table.getCenterTotalSize() -
            (virtualColumns[virtualColumns.length - 1].end -
              40 -
              table.getLeftTotalSize()),
        )
      : 0;
  const actionWidth = rowActions.length ? Math.min(4, rowActions.filter(action => action.quick).length) * 34 + 40 : 0;
  const selectionWidth = props.selectionEnabled === false ? 0 : 40;
  const totalWidth = table.getTotalSize() + selectionWidth + actionWidth;
  function style(
    column: Column<Node<T>, unknown>,
    header = false,
  ): CSSProperties {
    const pin = column.getIsPinned();
    return {
      width: column.getSize(),
      minWidth: column.getSize(),
      maxWidth: column.getSize(),
      position: pin ? "sticky" : undefined,
      left: pin === "left" ? selectionWidth + column.getStart("left") : undefined,
      right:
        pin === "right" ? actionWidth + column.getAfter("right") : undefined,
      zIndex: pin ? (header ? 34 : 5) : undefined,
    };
  }
  function autoFit(id?: string) {
    const canvas = document.createElement("canvas"),
      ctx = canvas.getContext("2d");
    if (ctx) ctx.font = "12px Inter, sans-serif";
    const widths = { ...layout.sizes };
    for (const def of columns.filter((c) => !id || c.id === id)) {
      const text = [
        def.title,
        ...visibleRecords
          .slice(0, 100)
          .map(
            (row) =>
              def.exportValue?.(row) ||
              String(
                def.accessor
                  ? def.accessor(row)
                  : ((row as Record<string, unknown>)[def.id] ?? ""),
              ),
          ),
      ];
      widths[def.id] = Math.min(
        480,
        Math.max(
          def.minWidth || 80,
          ...text.map(
            (value) => (ctx?.measureText(value).width || value.length * 7) + 64,
          ),
        ),
      );
    }
    updateLayout({ ...layout, sizes: widths });
  }
  function moveColumn(id: string, delta: number) {
    const from = layout.order.indexOf(id),
      to = Math.max(0, Math.min(layout.order.length - 1, from + delta));
    updateLayout({ ...layout, order: arrayMove(layout.order, from, to) });
  }
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );
  function dragEnd(event: DragEndEvent) {
    const from = String(event.active.id),
      to = String(event.over?.id || "");
    if (from.startsWith("column:")) {
      const id = from.slice(7);
      if (to === "grid-group-zone") {
        if (
          columns.find((c) => c.id === id)?.groupable !== false &&
          !query.grouping.includes(id) &&
          query.grouping.length < 4
        )
          changeQuery({
            ...query,
            grouping: [...query.grouping, id],
            path: [],
            page: 1,
          });
      } else if (to.startsWith("column:"))
        updateLayout({
          ...layout,
          order: arrayMove(
            layout.order,
            layout.order.indexOf(id),
            layout.order.indexOf(to.slice(7)),
          ),
        });
    } else if (
      from.startsWith("group-column:") &&
      to.startsWith("group-column:")
    )
      changeQuery({
        ...query,
        grouping: arrayMove(
          query.grouping,
          query.grouping.indexOf(from.slice(13)),
          query.grouping.indexOf(to.slice(13)),
        ),
        page: 1,
        path: [],
      });
  }
  async function loadBranch(path: GridGroup["path"], parent: string, page = 1) {
    const originalSignature = currentQuery.current;
    setLoadingGroups((s) => new Set(s).add(parent));
    try {
      const branchQuery = { ...query, path, page };
      const response = await client.fetchQuery({
        queryKey: [
          "shared-grid-branch",
          preferenceKey,
          dataSource.key,
          branchQuery,
          props.refreshKey,
        ],
        queryFn: async ({ signal }) => validateGridResult(await dataSource.load(branchQuery, signal)),
        staleTime: 15000,
      });
      if (originalSignature !== currentQuery.current) return;
      const normalized = normalize(response),
        loaded = (page - 1) * query.pageSize + normalized.length;
      const items =
        loaded < response.pageTotal
          ? [
              ...normalized,
              { id: `more:${parent}`, more: { path, page: page + 1, parent } },
            ]
          : normalized;
      setChildren((existing) => ({
        ...existing,
        [parent]:
          page === 1
            ? items
            : [...(existing[parent] || []).filter((n) => !n.more), ...items],
      }));
    } catch (e) {
      setActionError(errorText(e));
    } finally {
      setLoadingGroups((s) => {
        const next = new Set(s);
        next.delete(parent);
        return next;
      });
    }
  }
  async function expand(id: string, group: GridGroup) {
    const row = table.getRow(id);
    if (!row.getIsExpanded() && !children[id]) await loadBranch(group.path, id);
    row.toggleExpanded();
  }
  function emitSelection(ids: string[]) {
    setInternalSelection(ids);
    for (const row of visibleRecords)
      if (ids.includes(getRowId(row)))
        selectedCache.current.set(getRowId(row), row);
    for (const id of [...selectedCache.current.keys()])
      if (!ids.includes(id)) selectedCache.current.delete(id);
    props.onSelectionChange?.(
      ids
        .map((id) => selectedCache.current.get(id))
        .filter((row): row is T => !!row),
      ids,
    );
  }
  function selectRow(node: Node<T>, checked: boolean, shift = false) {
    if (!node.record) return;
    const id = node.id;
    let affected = [id];
    if (shift && lastSelected.current) {
      const ids = recordNodes.map((r) => r.id),
        from = ids.indexOf(lastSelected.current),
        to = ids.indexOf(id);
      if (from >= 0 && to >= 0)
        affected = ids.slice(Math.min(from, to), Math.max(from, to) + 1);
    }
    lastSelected.current = id;
    emitSelection(
      checked
        ? [...new Set([...selection, ...affected])]
        : selection.filter((id) => !affected.includes(id)),
    );
  }
  const allSelected =
    visibleRecords.length > 0 &&
    visibleRecords.every((row) => selection.includes(getRowId(row)));
  const [bulkBusy, setBulkBusy] = useState<string>();
  const selectedRecords = selection.map(id => selectedCache.current.get(id)).filter((row): row is T => row !== undefined);
  async function runBulkAction(action: NonNullable<SharedDataGridProps<T>["bulkActions"]>[number]) {
    if (bulkBusy || selectedRecords.length !== selection.length || action.disabled?.(selectedRecords)) return;
    if (action.confirm && !window.confirm(action.confirm(selectedRecords))) return;
    setBulkBusy(action.id); setActionError("");
    try { await action.run(selectedRecords); emitSelection([]); await request.refetch(); }
    catch (error) { setActionError(errorText(error)); }
    finally { setBulkBusy(undefined); }
  }
  async function runAction(action: GridAction<T>, row: T) {
    if (action.disabled?.(row)) { setActionError(action.disabledReason || "This action is unavailable for this record."); return; }
    try {
      setActionError("");
      await action.run(row);
    } catch (e) {
      setActionError(errorText(e));
    }
  }
  function rowMenu(row: T) {
    return rowActions
      .filter((action) => !action.visible || action.visible(row))
      .map((action) => (
        <Context.Item
          key={action.id}
          disabled={action.disabled?.(row)}
          className={action.danger ? "danger" : ""}
          onSelect={() => void runAction(action, row)}
        >
          {action.icon && <action.icon size={14} />} {action.label}
        </Context.Item>
      ));
  }
  function cancelEdit() {
    const cell = edit;
    setEdit(undefined);
    if (cell)
      requestAnimationFrame(() =>
        scroll.current
          ?.querySelector<HTMLElement>(
            `[data-row-id="${globalThis.CSS.escape(cell.row)}"][data-cell-id="${globalThis.CSS.escape(cell.column)}"]`,
          )
          ?.focus(),
      );
  }
  function startEdit(node: Node<T>, def: GridColumn<T>) {
    if (
      !node.record ||
      !onEdit ||
      !permissions.edit ||
      !(typeof def.editable === "function"
        ? def.editable(node.record)
        : def.editable)
    )
      return;
    const value = def.accessor
      ? def.accessor(node.record)
      : (node.record as Record<string, unknown>)[def.id];
    const localDate =
      def.editor === "datetime-local" && value
        ? new Date(String(value))
        : undefined;
    const editorValue =
      localDate && !Number.isNaN(localDate.getTime())
        ? new Date(localDate.getTime() - localDate.getTimezoneOffset() * 60000)
            .toISOString()
            .slice(0, 16)
        : value == null
          ? ""
          : String(value).slice(0, def.editor === "date" ? 10 : undefined);
    setEdit({ row: node.id, column: def.id, value: editorValue });
  }
  async function commitEdit(node: Node<T>, def: GridColumn<T>) {
    if (!edit || !node.record || edit.busy) return;
    const validation = def.validate?.(edit.value, node.record);
    if (validation) {
      setEdit({ ...edit, error: validation });
      return;
    }
    setEdit({ ...edit, busy: true, error: undefined });
    try {
      await onEdit?.(node.record, def.id, edit.value);
      setEdit(undefined);
      void request.refetch();
      setNotice(`${def.title} saved.`);
    } catch (e) {
      setEdit({ ...edit, error: errorText(e), busy: false });
    }
  }
  function focusCell(index: number, columnIndex: number) {
    index = Math.max(0, Math.min(modelRows.length - 1, index));
    columnIndex = Math.max(0, Math.min(ordered.length - 1, columnIndex));
    const node = modelRows[index]?.original,
      def = ordered[columnIndex];
    if (!node || !def) return;
    setActive({ row: node.id, column: def.id });
    rowVirtual.scrollToIndex(index, { align: "auto" });
    const centerIndex = center.findIndex((c) => c.id === def.id);
    if (centerIndex >= 0)
      columnVirtual.scrollToIndex(centerIndex, { align: "auto" });
    requestAnimationFrame(() =>
      scroll.current
        ?.querySelector<HTMLElement>(
          `[data-row-id="${globalThis.CSS.escape(node.id)}"][data-cell-id="${globalThis.CSS.escape(def.id)}"]`,
        )
        ?.focus(),
    );
  }
  function cellKey(
    event: KeyboardEvent,
    node: Node<T>,
    column: string,
    index: number,
  ) {
    if (edit || (event.target !== event.currentTarget && (event.target as HTMLElement).closest('button,a,input,select,textarea,[contenteditable="true"]'))) return;
    const col = ordered.findIndex((c) => c.id === column);
    if (event.key === "Enter" || event.key === "F2") {
      event.preventDefault();
      const def = columns.find((c) => c.id === column)!;
      if (def.editable) startEdit(node, def);
      else if (node.record) onOpen?.(node.record);
    }
    if (
      ["ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Tab"].includes(
        event.key,
      )
    ) {
      event.preventDefault();
      let nextRow =
          index +
          (event.key === "ArrowDown" ? 1 : event.key === "ArrowUp" ? -1 : 0),
        nextCol =
          col +
          (event.key === "ArrowLeft"
            ? -1
            : event.key === "ArrowRight"
              ? 1
              : event.key === "Tab"
                ? event.shiftKey
                  ? -1
                  : 1
                : 0);
      if (nextCol >= ordered.length) {
        nextCol = 0;
        nextRow++;
      }
      if (nextCol < 0) {
        nextCol = ordered.length - 1;
        nextRow--;
      }
      if (event.shiftKey && event.key !== "Tab") {
        const target = {
          row: modelRows[Math.max(0, Math.min(modelRows.length - 1, nextRow))]
            ?.id,
          column:
            ordered[Math.max(0, Math.min(ordered.length - 1, nextCol))]?.id,
        };
        if (target.row && target.column)
          setRange({
            start: range?.start || { row: node.id, column },
            end: target,
          });
      } else setRange(undefined);
      focusCell(nextRow, nextCol);
    }
    if (event.key === "Escape") {
      setRange(undefined);
      setEdit(undefined);
    }
  }
  function textFor(row: T, def: GridColumn<T>) {
    return (
      def.exportValue?.(row) ||
      String(
        def.accessor
          ? def.accessor(row)
          : ((row as Record<string, unknown>)[def.id] ?? ""),
      )
    );
  }
  function displayFor(row: T, def: GridColumn<T>) {
    if (isPhoneField(def.id)) {
      return <PhoneActions value={def.accessor ? def.accessor(row) : (row as Record<string, unknown>)[def.id]} record={row} field={def.id} />;
    }
    return def.render ? def.render(row) : textFor(row, def);
  }
  async function copyCells() {
    try {
      if (!permissions.export) {
        setNotice("Copying data requires export permission.");
        return;
      }
      const start = range?.start || active,
        end = range?.end || active;
      if (!start || !end) return;
      const a = modelRows.findIndex((r) => r.id === start.row),
        b = modelRows.findIndex((r) => r.id === end.row),
        c = ordered.findIndex((col) => col.id === start.column),
        d = ordered.findIndex((col) => col.id === end.column);
      const copied = modelRows
        .slice(Math.min(a, b), Math.max(a, b) + 1)
        .filter((r) => r.original.record)
        .map((r) =>
          ordered
            .slice(Math.min(c, d), Math.max(c, d) + 1)
            .map((col) =>
              safeClipboard(
                textFor(
                  r.original.record!,
                  columns.find((def) => def.id === col.id)!,
                ),
              ),
            )
            .join("\t"),
        )
        .join("\n");
      await navigator.clipboard.writeText(copied);
      setNotice("Selected cells copied.");
    } catch {
      setActionError(
        "Clipboard access is unavailable. Use CSV export instead.",
      );
    }
  }
  async function exportData(
    format: GridExportRequest["format"],
    scope: GridExportRequest["scope"],
    includeGroups: boolean,
    includeSummaries: boolean,
  ) {
    if (!dataSource.export) return;
    setExportBusy(true);
    setActionError("");
    try {
      const response = await dataSource.export({
        format,
        scope,
        ids: scope === "selected" ? selection : visibleRecords.map(getRowId),
        columns: exportColumns.filter((id) => layout.visibility[id] !== false),
        includeGroups,
        includeSummaries,
        query,
      });
      if (format === "clipboard") {
        await navigator.clipboard.writeText(
          typeof response === "string" ? response : await response.text(),
        );
        setNotice("Export copied to clipboard.");
      } else {
        const url = URL.createObjectURL(
            typeof response === "string" ? new Blob([response]) : response,
          ),
          anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = `${gridId}.${format}`;
        anchor.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
    } catch (e) {
      setActionError(errorText(e));
    } finally {
      setExportBusy(false);
    }
  }
  function display(node: Node<T>, definition: GridColumn<T>) {
    if (!node.record) return null;
    if (edit?.row === node.id && edit.column === definition.id) {
      const editorProps = {
        autoFocus: true,
        value: edit.value,
        disabled: edit.busy,
        "aria-label": `Edit ${definition.title}`,
        onChange: (
          e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
        ) => setEdit({ ...edit, value: e.target.value, error: undefined }),
        onKeyDown: (e: KeyboardEvent<HTMLInputElement | HTMLSelectElement>) => {
          e.stopPropagation();
          if (e.key === "Enter") {
            e.preventDefault();
            void commitEdit(node, definition);
          }
          if (e.key === "Escape") {
            e.preventDefault();
            cancelEdit();
          }
        },
      };
      return (
        <div className="udg-cell-editor">
          {definition.editor === "select" ? (
            <NativeSelect {...editorProps}>
              {definition.options?.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </NativeSelect>
          ) : (
            <input {...editorProps} type={definition.editor || "text"} />
          )}
          <button
            disabled={edit.busy}
            aria-label="Save cell"
            onClick={() => void commitEdit(node, definition)}
          >
            ✓
          </button>
          <button aria-label="Cancel cell edit" onClick={cancelEdit}>
            <X size={12} />
          </button>
          {edit.error && (
            <span role="alert" className="udg-cell-error">
              {edit.error}
            </span>
          )}
        </div>
      );
    }
    return displayFor(node.record, definition);
  }
  function cells(
    node: Node<T>,
    index: number,
    subset: Column<Node<T>, unknown>[],
  ) {
    return subset.map((column) => {
      const def = columns.find((c) => c.id === column.id)!;
      let inRange = false;
      if (range) {
        const ri = modelRows.findIndex((r) => r.id === range.start.row),
          rj = modelRows.findIndex((r) => r.id === range.end.row),
          ci = ordered.findIndex((c) => c.id === range.start.column),
          cj = ordered.findIndex((c) => c.id === range.end.column),
          current = ordered.findIndex((c) => c.id === column.id);
        inRange =
          index >= Math.min(ri, rj) &&
          index <= Math.max(ri, rj) &&
          current >= Math.min(ci, cj) &&
          current <= Math.max(ci, cj);
      }
      return (
        <div
          role="gridcell"
          aria-colindex={ordered.findIndex((c) => c.id === column.id) + 2}
          key={column.id}
          data-row-id={node.id}
          data-cell-id={column.id}
          data-cell-editable={permissions.edit && (typeof def.editable === "function" ? def.editable(node.record!) : def.editable) ? "true" : undefined}
          style={style(column)}
          className={`udg-cell udg-align-${def.align || (["number", "currency"].includes(def.type || "") ? "right" : "left")} ${inRange ? "is-range" : ""} ${active?.row === node.id && active.column === column.id ? "is-focused" : ""}`}
          tabIndex={
            active
              ? active.row === node.id && active.column === column.id
                ? 0
                : -1
              : index === 0 && column.id === ordered[0]?.id
                ? 0
                : -1
          }
          onFocus={() => setActive({ row: node.id, column: column.id })}
          onPointerDown={(e) => {
            if (e.shiftKey && active)
              setRange({
                start: range?.start || active,
                end: { row: node.id, column: column.id },
              });
            else setRange(undefined);
          }}
          onDoubleClick={(e) => {
            if (
              (typeof def.editable === "function"
                ? def.editable(node.record!)
                : def.editable) &&
              permissions.edit
            ) {
              e.stopPropagation();
              startEdit(node, def);
            }
          }}
          onKeyDown={(e) => cellKey(e, node, column.id, index)}
        >
          {display(node, def)}
        </div>
      );
    });
  }
  const header = (subset: Column<Node<T>, unknown>[]) =>
    subset.map((column) => (
      <Header
        key={column.id}
        column={column}
        definition={columns.find((c) => c.id === column.id)!}
        style={style(column, true)}
        source={dataSource}
        query={query}
        change={changeQuery}
        autoFit={autoFit}
        move={moveColumn}
        resizeHandler={table
          .getFlatHeaders()
          .find((h) => h.column.id === column.id)!
          .getResizeHandler()}
        resizeKey={(delta) =>
          updateLayout({
            ...layout,
            sizes: {
              ...layout.sizes,
              [column.id]: Math.max(
                70,
                Math.min(800, column.getSize() + delta),
              ),
            },
          })
        }
      />
    ));
  const safeClipboard = (value: string) => {
    const text = /^[\s]*[=+@-]/.test(value) ? "'" + value : value;
    return /[\t\n\r"]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  return (
    <section
      className="udg"
      aria-label={props.title || "Data grid"}
      data-grid-id={gridId}
      onKeyDown={(e) => {
        if (
          e.target instanceof HTMLInputElement ||
          e.target instanceof HTMLTextAreaElement ||
          e.target instanceof HTMLSelectElement
        )
          return;
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "c" && !edit) {
          e.preventDefault();
          void copyCells();
        }
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !edit) {
          e.preventDefault();
          undo();
        }
      }}
    >
      {props.statistics && result
        ? props.statistics(result)
        : result && (
            <div className="udg-statistics">
              <div>
                <span>Matching records</span>
                <strong>{result.total.toLocaleString()}</strong>
              </div>
              {result.aggregates?.map((a) => (
                <div key={a.currency}>
                  <span>Total value · {a.currency}</span>
                  <strong>{formatMoney(a.sum, a.currency)}</strong>
                  <small>Average {formatMoney(a.avg, a.currency)}</small>
                </div>
              ))}
            </div>
          )}
      {columns.find(column => column.type === "status") && <SuiteDistribution records={visibleRecords} field={columns.find(column => column.type === "status")!.id} label={columns.find(column => column.type === "status")!.title} />}
      <GridToolbar
        search={search}
        setSearch={setSearch}
        filterCount={filterRules(query.filters).length}
        openFilters={() => setFilterOpen(true)}
        layout={layout}
        updateLayout={updateLayout}
        views={props.views || ["grid"]}
        extra={props.toolbarExtra}
        undo={historySize ? undo : undefined}
        reset={() =>
          updateLayout({ ...defaultLayout(columns), ...props.initialLayout })
        }
      >
        <ColumnManager
          columns={columns}
          layout={layout}
          update={updateLayout}
          autoFit={autoFit}
        />
        <SavedViewsManager
          views={views}
          save={(name) =>
            setViews((v) =>
              [
                ...v.filter((view) => view.name !== name),
                {
                  id: crypto.randomUUID(),
                  name,
                  layout: structuredClone(layout),
                  query: structuredClone(query),
                  context: props.viewContext
                    ? structuredClone(props.viewContext)
                    : undefined,
                },
              ].slice(-50),
            )
          }
          load={(view) => {
            updateLayout(view.layout);
            const restoredQuery = { ...view.query, path: [], page: 1 };
            if (props.onRestoreView) restoredViewQuery.current = JSON.stringify(restoredQuery);
            changeQuery(restoredQuery);
            // Restoring context can remount the adapter before the persistence effect runs.
            try {
              localStorage.setItem(preferenceKey, JSON.stringify({ layout: sanitizeLayout(view.layout, columns), query: restoredQuery, views }));
            } catch {
              setNotice("Layout could not be saved in this browser.");
            }
            if (props.onRestoreView) props.onRestoreView({ ...view, query: restoredQuery });
            else props.onViewContextChange?.(view.context || {});
          }}
          remove={(id) => setViews((v) => v.filter((view) => view.id !== id))}
        />
        <GridExportMenu
          formats={props.exportFormats}
          selectedCount={selection.length}
          visibleCount={visibleRecords.length}
          allowed={!!dataSource.export && !!permissions.export}
          columns={columns.filter((c) => layout.visibility[c.id] !== false)}
          selectedColumns={exportColumns}
          setColumns={setExportColumns}
          run={(...args) => void exportData(...args)}
          busy={exportBusy}
        />
        <button
          className="udg-control"
          aria-label="Refresh grid"
          onClick={() => void request.refetch()}
        >
          <RefreshCw
            size={15}
            className={request.isFetching ? "udg-spinning" : ""}
          />
        </button>
      </GridToolbar>
      {(filterRules(query.filters).length > 0 ||
        !!props.externalFilters?.length) && (
        <div className="udg-filter-chips">
          {props.externalFilters?.map((filter) => (
            <span key={filter.id}>
              {filter.label}
              <button
                aria-label={`Remove ${filter.label}`}
                onClick={filter.clear}
              >
                <X size={12} />
              </button>
            </span>
          ))}
          {filterRules(query.filters).map((rule, index) => (
            <span key={index}>
              {columns.find((c) => c.id === rule.field)?.title || rule.field}{" "}
              {rule.operator.replace(/_/g, " ")}{" "}
              {Array.isArray(rule.value)
                ? `${rule.value.length} values`
                : String(rule.value ?? "")}
              <button
                aria-label={`Remove filter ${index + 1}`}
                onClick={() =>
                  changeQuery({
                    ...query,
                    filters: removeRule(query.filters, rule),
                    page: 1,
                  })
                }
              >
                <X size={12} />
              </button>
            </span>
          ))}
          <button
            onClick={() => {
              changeQuery({
                ...query,
                filters: { logic: "and", rules: [] },
                search: "",
                page: 1,
              });
              props.onClearFilters?.();
            }}
          >
            Clear all
          </button>
        </div>
      )}
      {selection.length > 0 && (
        <div className="udg-selection-bar">
          <strong>{selection.length} selected</strong>
          {(props.bulkActions || []).map(action => <button type="button" key={action.id} className={`udg-control ${action.danger ? "udg-danger" : ""}`}
            disabled={!!bulkBusy || !selectedRecords.length || selectedRecords.length !== selection.length || action.disabled?.(selectedRecords)}
            onClick={() => void runBulkAction(action)}>{bulkBusy === action.id ? "Applying…" : action.label}</button>)}
          <button type="button" disabled={!!bulkBusy} onClick={() => emitSelection([])}>Clear selection</button>
          <small>
            Selection is kept across pages. Select All applies to loaded rows.
          </small>
        </div>
      )}
      {(request.error || actionError) && (
        <div role="alert" className="udg-error">
          {actionError || errorText(request.error)}
          <button
            onClick={() => {
              setActionError("");
              void request.refetch();
            }}
          >
            Retry
          </button>
        </div>
      )}
      {notice && (
        <div role="status" className="udg-notice">
          {notice}
          <button
            aria-label="Dismiss grid message"
            onClick={() => setNotice("")}
          >
            <X size={13} />
          </button>
        </div>
      )}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={dragEnd}
      >
        <GroupingPanel columns={columns} query={query} change={changeQuery} />
        {layout.view === "grid" ? (
          <div
            className="udg-scroll"
            ref={scroll}
            style={{ height: props.height || 540 }}
            role="grid"
            aria-label={props.title || "Records"}
            aria-rowcount={(result?.total || 0) + 1}
            aria-colcount={ordered.length + (selectionWidth ? 1 : 0) + (actionWidth ? 1 : 0)}
            aria-busy={request.isFetching}
          >
            <div
              className="udg-grid-content"
              style={{ width: Math.max(totalWidth, 300), minWidth: "100%" }}
            >
              <div className="udg-header" role="row" style={{ height: 40 }}>
                {selectionWidth > 0 && <div
                  className="udg-select-cell udg-select-heading"
                  role="columnheader"
                >
                  <input
                    type="checkbox"
                    aria-label="Select all loaded rows"
                    checked={allSelected}
                    onChange={(e) =>
                      emitSelection(
                        e.target.checked
                          ? [
                              ...new Set([
                                ...selection,
                                ...visibleRecords.map(getRowId),
                              ]),
                            ]
                          : selection.filter(
                              (id) =>
                                !visibleRecords.some(
                                  (row) => getRowId(row) === id,
                                ),
                            ),
                      )
                    }
                  />
                </div>}
                <SortableContext
                  items={layout.order.map((id) => `column:${id}`)}
                  strategy={horizontalListSortingStrategy}
                >
                  {header(left)}
                  {before > 0 && (
                    <div style={{ width: before, minWidth: before }} />
                  )}
                  {header(centerColumns)}
                  {after > 0 && (
                    <div style={{ width: after, minWidth: after }} />
                  )}
                  {header(right)}
                </SortableContext>
                {rowActions.length > 0 && (
                  <div
                    className="udg-action-cell"
                    role="columnheader"
                    aria-label="Row actions"
                    style={{ width: actionWidth, minWidth: actionWidth }}
                  >
                    <MoreHorizontal size={15} />
                  </div>
                )}
              </div>
              <div
                className="udg-body"
                role="rowgroup"
                style={{
                  height: request.isPending
                    ? effectiveRowHeight * 8
                    : rowVirtual.getTotalSize(),
                  position: "relative",
                }}
              >
                {request.isPending
                  ? Array.from({ length: 8 }, (_, i) => (
                      <div
                        className="udg-skeleton"
                        key={i}
                        style={{ height: effectiveRowHeight }}
                      />
                    ))
                  : virtualRows.map((virtual) => {
                      const row = modelRows[virtual.index],
                        node = row.original,
                        position: CSSProperties = {
                          position: "absolute",
                          top: 0,
                          left: 0,
                          width: "100%",
                          height: effectiveRowHeight,
                          transform: `translateY(${virtual.start - 40}px)`,
                        };
                      if (node.more)
                        return (
                          <div
                            role="row"
                            key={node.id}
                            className="udg-more-row"
                            style={position}
                          >
                            <button
                              disabled={loadingGroups.has(node.more.parent)}
                              onClick={() =>
                                void loadBranch(
                                  node.more!.path,
                                  node.more!.parent,
                                  node.more!.page,
                                )
                              }
                            >
                              Load more rows in this group
                            </button>
                          </div>
                        );
                      if (node.group)
                        return (
                          <div
                            role="row"
                            key={node.id}
                            className="udg-group-row"
                            data-row-id={node.id}
                            data-cell-id={ordered[0]?.id}
                            tabIndex={0}
                            onKeyDown={(event) => {
                              if (event.key === "ArrowDown") {
                                event.preventDefault();
                                focusCell(virtual.index + 1, 0);
                              }
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                void expand(node.id, node.group!);
                              }
                            }}
                            style={position}
                          >
                            <button
                              style={{ paddingLeft: 12 + row.depth * 18 }}
                              aria-expanded={row.getIsExpanded()}
                              onClick={() => void expand(node.id, node.group!)}
                            >
                              {loadingGroups.has(node.id) ? (
                                <RefreshCw size={14} className="udg-spinning" />
                              ) : row.getIsExpanded() ? (
                                <ChevronDown size={15} />
                              ) : (
                                <ChevronRight size={15} />
                              )}
                              <span>
                                {
                                  columns.find(
                                    (c) => c.id === node.group!.field,
                                  )?.title
                                }
                                : <strong>{node.group.label}</strong>
                              </span>
                              <b>{node.group.count.toLocaleString()}</b>
                            </button>
                            <NativeSelect
                              aria-label={`Aggregation for ${node.group.label}`}
                              value={layout.summary}
                              onChange={(e) =>
                                setLayout({
                                  ...layout,
                                  summary: e.target
                                    .value as GridLayout["summary"],
                                })
                              }
                            >
                              {["sum", "avg", "min", "max", "count"].map(
                                (key) => (
                                  <option key={key}>{key}</option>
                                ),
                              )}
                            </NativeSelect>
                            {node.group.aggregates.map((a) => (
                              <span
                                className="udg-group-total"
                                key={a.currency}
                              >
                                {layout.summary === "count"
                                  ? `${a.count} ${a.currency}`
                                  : formatMoney(a[layout.summary], a.currency)}
                              </span>
                            ))}
                          </div>
                        );
                      const record = node.record!;
                      return (
                        <GridContextMenu<T>
                          key={node.id}
                          row={record}
                          actions={rowActions}
                          open={onOpen ? () => onOpen(record) : undefined}
                          canCopy={!!permissions.export}
                          copy={() => {
                            void navigator.clipboard
                              .writeText(
                                ordered
                                  .map((c) =>
                                    safeClipboard(
                                      textFor(
                                        record,
                                        columns.find((d) => d.id === c.id)!,
                                      ),
                                    ),
                                  )
                                  .join("\t"),
                              )
                              .catch(() =>
                                setActionError(
                                  "Clipboard access is unavailable.",
                                ),
                              );
                          }}
                          run={(action, row) => void runAction(action, row)}
                        >
                          <div
                            {...props.rowProps?.(record)}
                            role="row"
                            aria-selected={selection.includes(node.id)}
                            aria-rowindex={
                              (query.page - 1) * query.pageSize +
                              virtual.index +
                              2
                            }
                            className={`udg-row ${edit?.row === node.id ? "is-editing" : ""} ${virtual.index % 2 ? "udg-row-alt" : ""} ${selection.includes(node.id) ? "is-selected" : ""}`}
                            style={position}
                            {...recordPreviewProps(record)}
                            onClick={event => {
                              props.rowProps?.(record).onClick?.(event);
                              if (event.defaultPrevented) return;
                              if (!(event.target as HTMLElement).closest('button,a,input,select,textarea,[role="checkbox"],[contenteditable="true"]') || (event.target as HTMLElement).closest("[data-record-open]")) selectRecord(record);
                            }}
                            onDoubleClickCapture={event => {
                              clearTimeout(selectRecordTimer.current);
                              const action = (event.target as HTMLElement).closest('button,a,input,select,textarea,[role="checkbox"],[contenteditable="true"]');
                              if (action && !action.hasAttribute('data-record-open')) return;
                              if (props.onOpenPopup) { event.preventDefault(); event.stopPropagation(); props.onOpenPopup(record); }
                              else if (props.rowProps?.(record).onDoubleClickCapture) props.rowProps(record).onDoubleClickCapture?.(event);
                              else recordPreviewProps(record).onDoubleClickCapture(event);
                            }}
                            draggable={!!props.manualOrder}
                            onDragStart={(e) => {
                              if (props.manualOrder)
                                e.dataTransfer.setData(
                                  "application/x-grid-row",
                                  node.id,
                                );
                            }}
                            onDragOver={(e) => {
                              if (props.manualOrder) e.preventDefault();
                            }}
                            onDrop={(e) => {
                              if (!props.manualOrder) return;
                              e.preventDefault();
                              const id = e.dataTransfer.getData(
                                  "application/x-grid-row",
                                ),
                                from = visibleRecords.find(
                                  (r) => getRowId(r) === id,
                                );
                              if (from && id !== node.id)
                                void props.manualOrder
                                  .move(from, record)
                                  .then(() => request.refetch())
                                  .catch((e) => setActionError(errorText(e)));
                            }}
                          >
                            {selectionWidth > 0 && <div className="udg-select-cell" role="gridcell">
                              <input
                                aria-label={`Select row ${textFor(record, columns[0])}`}
                                type="checkbox"
                                checked={selection.includes(node.id)}
                                onClick={(e) =>
                                  selectRow(
                                    node,
                                    !selection.includes(node.id),
                                    e.shiftKey,
                                  )
                                }
                                onChange={() => {}}
                                onDoubleClick={(e) => e.stopPropagation()}
                              />
                            </div>}
                            {cells(node, virtual.index, left)}
                            {before > 0 && (
                              <div
                                style={{ width: before, minWidth: before }}
                              />
                            )}
                            {cells(node, virtual.index, centerColumns)}
                            {after > 0 && (
                              <div style={{ width: after, minWidth: after }} />
                            )}
                            {cells(node, virtual.index, right)}
                            {rowActions.length > 0 && (
                              <div
                                className="udg-action-cell"
                                role="gridcell"
                                style={{
                                  width: actionWidth,
                                  minWidth: actionWidth,
                                }}
                              >
                                {rowActions
                                  .filter(
                                    (a) =>
                                      a.quick &&
                                      (!a.visible || a.visible(record)),
                                  )
                                  .slice(0, 4)
                                  .map((action) => (
                                    <button
                                      key={action.id}
                                      className="udg-hover-action"
                                      data-action={action.id}
                                      aria-label={`${action.label} ${textFor(record, columns[0])}`}
                                      disabled={action.disabled?.(record)}
                                      title={action.disabled?.(record) ? action.disabledReason || action.label : action.label}
                                      onClick={() =>
                                        void runAction(action, record)
                                      }
                                    >
                                      {action.icon ? (
                                        <action.icon size={14} />
                                      ) : (
                                        action.label
                                      )}
                                    </button>
                                  ))}
                                <Dropdown.Root>
                                  <Dropdown.Trigger
                                    aria-label={`Actions for ${textFor(record, columns[0])}`}
                                  >
                                    <MoreHorizontal size={16} />
                                  </Dropdown.Trigger>
                                  <Dropdown.Portal>
                                    <Dropdown.Content
                                      className="udg-menu"
                                      align="end"
                                    >
                                      {rowActions
                                        .filter(
                                          (a) =>
                                            !a.visible || a.visible(record),
                                        )
                                        .map((action) => (
                                          <Dropdown.Item
                                            disabled={action.disabled?.(record)}
                                            key={action.id}
                                            className={
                                              action.danger ? "danger" : ""
                                            }
                                            onSelect={() =>
                                              void runAction(action, record)
                                            }
                                          >
                                            {action.icon && (
                                              <action.icon size={14} />
                                            )}{" "}
                                            {action.label}
                                          </Dropdown.Item>
                                        ))}
                                    </Dropdown.Content>
                                  </Dropdown.Portal>
                                </Dropdown.Root>
                              </div>
                            )}
                          </div>
                        </GridContextMenu>
                      );
                    })}
              </div>
            </div>
            {!request.isPending && !modelRows.length && !request.error && (
              <div className="udg-empty">
                <SuiteIllustration />
                <h3>No records match</h3>
                <p>Try a different search or clear your filters.</p>
              </div>
            )}
          </div>
        ) : (
          <div className={`udg-alternate udg-view-${layout.view}`}>
            {layout.view === "kanban"
              ? [
                  ...new Set(
                    visibleRecords.map((r) =>
                      String(
                        (r as Record<string, unknown>)[
                          props.kanbanField || "status"
                        ] || "Not set",
                      ),
                    ),
                  ),
                ].map((key) => (
                  <section key={key}>
                    <h3>{key}</h3>
                    {visibleRecords
                      .filter(
                        (r) =>
                          String(
                            (r as Record<string, unknown>)[
                              props.kanbanField || "status"
                            ] || "Not set",
                          ) === key,
                      )
                      .map((r) => (
                        <article
                          key={getRowId(r)}
                          {...recordPreviewProps(r)} onClick={event=>{if(!(event.target as HTMLElement).closest("button,a,input,select,textarea")||(event.target as HTMLElement).closest("[data-record-open]"))selectRecord(r);}} onDoubleClickCapture={event=>{clearTimeout(selectRecordTimer.current);if(!(event.target as HTMLElement).closest("button,a,input,select,textarea")||(event.target as HTMLElement).closest("[data-record-open]")){event.stopPropagation();props.onOpenPopup ? props.onOpenPopup(r):recordPreviewProps(r).onDoubleClickCapture(event);}}}
                        >
                          {props.renderCard?.(r) ||
                            columns
                              .filter((c) => layout.visibility[c.id] !== false)
                              .slice(0, 5)
                              .map((c) => (
                                <p key={c.id}>
                                  <small>{c.title}</small>
                                  {displayFor(r, c)}
                                </p>
                              ))}
                        </article>
                      ))}
                  </section>
                ))
              : visibleRecords.map((r) => (
                  <article key={getRowId(r)} {...recordPreviewProps(r)} onClick={event=>{if(!(event.target as HTMLElement).closest("button,a,input,select,textarea")||(event.target as HTMLElement).closest("[data-record-open]"))selectRecord(r);}} onDoubleClickCapture={event=>{clearTimeout(selectRecordTimer.current);if(!(event.target as HTMLElement).closest("button,a,input,select,textarea")||(event.target as HTMLElement).closest("[data-record-open]")){event.stopPropagation();props.onOpenPopup ? props.onOpenPopup(r):recordPreviewProps(r).onDoubleClickCapture(event);}}}>
                    {props.renderCard?.(r) ||
                      columns
                        .filter((c) => layout.visibility[c.id] !== false)
                        .slice(0, 6)
                        .map((c) => (
                          <p key={c.id}>
                            <small>{c.title}</small>
                            {displayFor(r, c)}
                          </p>
                        ))}
                    <div className="udg-card-actions">{rowActions.filter(action=>action.quick&&(!action.visible||action.visible(r))).map(action=><button key={action.id} title={action.disabled?.(r)?action.disabledReason:action.label} aria-label={`${action.label} ${textFor(r,columns[0])}`} disabled={action.disabled?.(r)} onClick={event=>{event.stopPropagation();void runAction(action,r);}}>{action.icon&&<action.icon size={16}/>}</button>)}</div>
                  </article>
                ))}
            {query.grouping.length > 0 && !visibleRecords.length && (
              <p>Switch to Data Grid to expand the grouped records.</p>
            )}
            <small>
              These views use the same filtered data source. Cards show loaded
              rows.
            </small>
          </div>
        )}
      </DndContext>
      <div className="udg-summary-footer">
        <strong>{result?.total.toLocaleString() || 0} matching records</strong>
        <span>Full filtered dataset</span>
        {result?.aggregates?.map((a) => (
          <span key={a.currency}>
            <b>{a.currency}</b> Sum {formatMoney(a.sum, a.currency)} · Average{" "}
            {formatMoney(a.avg, a.currency)}
          </span>
        ))}
      </div>
      <footer className="udg-pagination">
        <label>
          Rows per page
          <NativeSelect
            aria-label="Rows per page"
            value={query.pageSize}
            onChange={(e) =>
              changeQuery({
                ...query,
                pageSize: Number(e.target.value),
                page: 1,
              })
            }
          >
            {[10, 25, 50, 100, 200].map((size) => (
              <option key={size}>{size}</option>
            ))}
          </NativeSelect>
        </label>
        <span>
          {query.grouping.length ? "Group page" : "Page"} {query.page} of{" "}
          {Math.max(1, Math.ceil((result?.pageTotal || 0) / query.pageSize))}
        </span>
        <button
          disabled={query.page <= 1 || request.isFetching}
          onClick={() => changeQuery({ ...query, page: query.page - 1 })}
        >
          Previous
        </button>
        <button
          disabled={
            query.page * query.pageSize >= (result?.pageTotal || 0) ||
            request.isFetching
          }
          onClick={() => changeQuery({ ...query, page: query.page + 1 })}
        >
          Next
        </button>
      </footer>
      {filterOpen && (
        <FilterBuilder
          columns={columns}
          value={query.filters}
          close={() => setFilterOpen(false)}
          apply={(filters) => {
            changeQuery({ ...query, filters, page: 1 });
            setFilterOpen(false);
          }}
        />
      )}
    </section>
  );
}


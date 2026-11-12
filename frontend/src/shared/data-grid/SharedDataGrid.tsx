import { isLocationField, locationLast } from "./record-location";
import { useRecordSync, rowSync } from "@/shared/record-sync/store";
import { withEditNavigation } from "@/lib/edit-navigation";
import { SyncRing } from "@/shared/record-sync/RecordSyncItems";
import { withAllRows } from "./all-rows-source";
import RowResizeHandle, { fitRow } from "./RowResizeHandle";
import { businessGroupColumn, initialBusinessGroups } from "./business-grouping";
import { hasMobilePreset, mobilePresets, toggleMobilePreset } from "./mobile-presets";
import { useRouteViewState } from "@/hooks/use-route-view-state";
import { groupAppearance, groupCategoryColors } from "./GroupLabel";
import "./record-group.css";
import { normalizePriority, recordPriority } from "@/shared/priority/priority";
import CollectionOverview from "./CollectionOverview";
import {useRecordAutosave} from "@/hooks/use-record-autosave";
import {moduleActionAllowed} from "@/hooks/use-module-action";
import { mergePendingGridSearch } from "./pendingSearch";
import RecordViewBar from "./RecordViewBar";
import { createPortal } from "react-dom";
import { columnIcon, columnValue } from "./column-presentation";
import { useRecordPreferences } from "./record-preferences";
import { personalQuery, personalRows } from "./personal-filter";
import { localGridSource } from "./local-source";
import { Star } from "lucide-react";
import GroupLabel from "./GroupLabel";
import { defaultText } from "@/lib/form-defaults";
import { writeClipboard } from "@/lib/clipboard";
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
  pointerWithin,
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
  ChevronsUpDown,
  ChevronsDownUp,
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
import "./grid-mobile.css";
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
    : e instanceof Error && e.message ? e.message : "The grid request could not be completed. Check your connection and filter values, then retry.";
};
const formatMoney = (value: number, currency?: string) => {
  try {
    return new Intl.NumberFormat(defaultText("number_format"), {
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
  loadedOnly,
  expandAll,
  collapseAll,
  expanding,
}: {
  loadedOnly?: boolean;
  expandAll?: () => void;
  collapseAll?: () => void;
  expanding?: boolean;
  columns: { id: string; title: string; groupable?: boolean }[];
  query: GridQuery;
  change: (query: GridQuery) => void;
}) {
  const drop = useDroppable({ id: "grid-group-zone" });
  return (
    <div
      aria-label="Column grouping drop zone"
      className={`udg-grouping ${drop.isOver ? "is-over" : ""}`}
      ref={drop.setNodeRef}
    >
      <Layers size={15} />
      <span title="Drag a column header here to group records">Group · Drag columns here</span>
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
        <small>Drag a column header here to group {loadedOnly ? "loaded rows" : "records"}</small>
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
      {query.grouping.length > 0 && <>
        <button type="button" className="udg-control udg-group-toggle" aria-label="Expand loaded groups" title="Expand loaded groups" disabled={expanding} onClick={expandAll}>{expanding ? <RefreshCw size={14} className="udg-spinning"/> : <ChevronsUpDown size={14}/>}</button>
        <button type="button" className="udg-control udg-group-toggle" aria-label="Collapse all" title="Collapse all groups" onClick={collapseAll}><ChevronsDownUp size={14}/></button>
      </>}
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
  selectionOffset,
}: {
  selectionOffset: number;
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
  const Icon = definition.icon || columnIcon(definition.title);
  return (
    <div
      role="columnheader"
      aria-colindex={column.getIndex() + 1 + selectionOffset}
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
      {definition.header ? <div className="udg-legacy-heading" {...drag.listeners}><Icon size={13} aria-hidden="true"/>{definition.header}</div> : <button
        type="button"
        className="udg-sort-button"
        {...drag.listeners}
        aria-disabled={definition.sortable === false || undefined}
        onClick={definition.sortable === false ? undefined : column.getToggleSortingHandler()}
        title="Drag to group or reorder; click to sort; Shift-click for multiple columns"
      >
        <Icon size={13} aria-hidden="true" />
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
  const user=useAuthStore(state=>state.user);
  // Reset synchronously at the identity boundary. A passive reset can render the
  // previous account's saved names/preview once, and persist them under the new key.
  const scope=JSON.stringify([user?.id,user?.access?.companyId,user?.role,user?.primary_role,user?.is_superuser,user?.access?.grants,props.userId,props.organizationId,props.workspaceId,props.gridId,props.personalScope]);
  return <ScopedDataGrid key={scope} {...props}/>;
}

function ScopedDataGrid<T>(props: SharedDataGridProps<T>) {
  const [focused, setFocused] = useState<T>();
  const [previewRows,setPreviewRows] = useState<T[]>([]);
  const [previewNotice,setPreviewNotice] = useState("");
  const workspaceElement = useRef<HTMLDivElement>(null);
  const lastRecordControl = useRef<{id:string;element:HTMLElement}>();
  const previewOrigin = useRef<{id:string;element?:HTMLElement}>();
  const rememberPreviewControl = (target: EventTarget | null) => {
    if (!(target instanceof HTMLElement)) return;
    const control=target.closest<HTMLElement>('button,a,[data-record-open]'), row=control?.closest<HTMLElement>('[data-grid-record-id]');
    if (control&&row?.dataset.gridRecordId) lastRecordControl.current={id:row.dataset.gridRecordId,element:control};
  };
  const returnPreviewFocus = () => {
    const origin = previewOrigin.current;
    requestAnimationFrame(() => {
      const root = workspaceElement.current;
      if (!root || !origin) return;
      const row = Array.from(root.querySelectorAll<HTMLElement>('[data-grid-record-id]')).find(element=>element.dataset.gridRecordId===origin.id&&element.getClientRects().length);
      const target = origin.element?.isConnected && origin.element.getClientRects().length ? origin.element : row?.querySelector<HTMLElement>('button[aria-label="Record quick actions"]') ?? row?.querySelector<HTMLElement>('button[title="Preview record"]') ?? row?.querySelector<HTMLElement>('a,button') ?? root.querySelector<HTMLElement>('input');
      target?.focus({preventScroll:true});
    });
  };
  const closePreview = () => { setFocused(undefined);setPreviewNotice("");returnPreviewFocus(); };
  const location = useLocation();
  const personal = useRecordPreferences(`${location.pathname}:${props.workspaceId || "organization"}:${props.personalScope || props.gridId}`);
  const enabled = props.personalViews !== false;
  const category = props.columns.find(column => /^(category|department|type|stage|status|team|group)$/i.test(column.title));
  const tags = props.columns.find(column => /^(tags?|labels)$/i.test(column.title));
  const mode = enabled ? personal.view : "table";
  const ranked = Object.entries(personal.activity).sort((a,b)=>b[1].count-a[1].count||b[1].last-a[1].last).map(([id])=>id);
  const ids = mode === "favorites" ? personal.favorites : mode === "frequent" ? ranked : undefined;
  const personalSignature = JSON.stringify([mode,ids]);
  const personalKind=mode==="favorites"||mode==="frequent"?mode:null;
  useEffect(()=>{props.onPersonalFilterChange?.({kind:personalKind,ids,apply:kind=>personal.setView(kind||"table")});},[personal.key,personalSignature]);
  const source = useMemo(() => {
    const base = props.dataSource;
    if (!enabled || ids === undefined) return base;
    const key = `${base.key}:personal:${personalSignature}`;
    if (base.localRows) {
      const records = personalRows(base.localRows,{kind:personalKind,ids},props.getRowId);
      const filtered = localGridSource(key,records,props.columns,props.getRowId);
      return {...filtered,load:async(query:GridQuery,signal?:AbortSignal)=>{const [result,original]=await Promise.all([filtered.load(mode==="frequent"?{...query,sorting:[]}:query,signal),base.load(query,signal)]);return {...result,permissions:original.permissions};}, export:base.export?filtered.export:undefined};
    }
    const adapt = (query:GridQuery):GridQuery => base.personalIdentity ? personalQuery(query,{kind:personalKind,ids},base.personalIdentity) : {...query,grouping:[],path:[]};
    return {...base,key,load:async(query:GridQuery,signal?:AbortSignal)=>{
      const result=await base.load(adapt(query),signal);
      if(base.personalIdentity)return result;
      const rank=new Map(ids.map((id,index)=>[id,index]));
      const rows=result.rows.filter(row=>rank.has(props.getRowId(row)));
      if(mode==="frequent")rows.sort((a,b)=>rank.get(props.getRowId(a))!-rank.get(props.getRowId(b))!);
      return {...result,rows,groups:[],total:rows.length,pageTotal:rows.length};
    },facets:base.facets?((field:string,search:string,query:GridQuery,signal?:AbortSignal)=>base.facets!(field,search,adapt(query),signal)):undefined,export:base.export&&base.personalIdentity?((request:GridExportRequest)=>base.export!({...request,query:adapt(request.query)})):undefined};
  },[props.dataSource,personalSignature,enabled]);
  const identity = props.columns.find(column=>/^(name|title|full_name)$/i.test(column.id)) || props.columns.find(column=>/^(name|title|sales order|billing plan|engagement|task|project|employee|lead|deal|contact|company|customer|account|record|document|file|item|product|invoice|order|contract|campaign)( name)?$/i.test(column.title)) || props.columns.find(column=>!/select|action|favorite/i.test(column.title)) || props.columns[0];
  const titleFor = (row:T) => identity ? String(identity.exportValue?.(row) ?? identity.accessor?.(row) ?? (row as Record<string,unknown>)[identity.id] ?? "Record") : "Record";
  const track = (row:T) => {if(enabled)personal.use(props.getRowId(row));};
  const favoriteColumn:GridColumn<T>={id:"__suite_favorite",title:"Favorite",header:<span className="sr-only">Favorite</span>,width:47,minWidth:40,sortable:false,filterable:false,groupable:false,render:row=><button type="button" className="suite-record-star" data-record-personal aria-label={`${personal.favorites.includes(props.getRowId(row))?"Unfavorite":"Favorite"} ${titleFor(row)}`} title="Toggle favorite" aria-pressed={personal.favorites.includes(props.getRowId(row))} onClick={event=>{event.stopPropagation();personal.toggle(props.getRowId(row));}}><Star size={15} fill={personal.favorites.includes(props.getRowId(row))?"currentColor":"none"}/></button>};
  const enhancedColumns=enabled?[favoriteColumn,...props.columns]:props.columns;
  useEffect(() => setFocused(undefined), [props.dataSource.key, location.pathname, location.search]);
  const canPreview = props.detailsEnabled !== false && !props.onSelectRecord;
  const preview = (row: T) => {
    const id = props.getRowId(row), active = document.activeElement;
    previewOrigin.current = {id,element:lastRecordControl.current?.id===id ? lastRecordControl.current.element : active instanceof HTMLElement && active!==document.body && !active.closest('[role="menu"]') ? active : undefined};
    track(row);setPreviewNotice("");setFocused(row);
  };
  const titleColumn = props.columns.find(c => !/^(select|actions?|quick actions)$/i.test(c.title)) || props.columns[0];
  const title = focused === undefined ? "" : String(titleColumn?.accessor?.(focused) ?? (focused as Record<string, unknown>)[titleColumn?.id] ?? "Record");
  return <div ref={workspaceElement} data-grid-id={props.gridId} onPointerDownCapture={event=>rememberPreviewControl(event.target)} onKeyDownCapture={event=>{if(event.key==="Enter"||event.key===" ")rememberPreviewControl(event.target);}} className={`udg-workspace ${focused !== undefined ? "has-details" : ""}`}>
    <div className="udg-workspace-main">{enabled&&!props.hideViewControls&&!props.compactControls&&<RecordViewBar compact={props.compactControls} scope={props.gridId} view={mode} change={personal.setView} category={category?.title} tags={!!tags} server={!!props.dataSource.personalIdentity}/>}
    <GridEngine {...props}
      toolbarExtra={props.compactControls ? <>{enabled&&!props.hideViewControls&&<RecordViewBar compact scope={props.gridId} view={mode} change={personal.setView} category={category?.title} tags={!!tags} server={!!props.dataSource.personalIdentity}/>} {props.toolbarExtra}</> : props.toolbarExtra}
      dataSource={source} columns={enhancedColumns}
      viewMode={enabled?(mode==="cards"||mode==="category"||mode==="tags"?"cards":mode==="list"?"list":"grid"):props.viewMode}
      collectionGroup={mode==="category"?category?.id:mode==="tags"?tags?.id:undefined}
      rowProps={row=>{const original=props.rowProps?.(row)||{};return {...original,"data-grid-record-id":props.getRowId(row),onClickCapture:event=>{original.onClickCapture?.(event);const target=event.target as HTMLElement,control=target.closest<HTMLElement>('button,a,[data-record-open]');if(control&&!target.closest("[data-record-personal]")){lastRecordControl.current={id:props.getRowId(row),element:control};track(row);}}};}}
      onVisibleRecordsChange={records => {setPreviewRows(records);props.onVisibleRecordsChange?.(records);}}
      onSelectRecord={props.onSelectRecord || (canPreview ? preview : undefined)}
      onOpen={props.onOpen ? row=>{track(row);props.onOpen!(row);} : (canPreview ? preview : undefined)}
      rowActions={[...(canPreview ? [{ id: "suite-preview", label: "Preview record", icon: Eye, quick: true, run: preview }] : []),...(enabled?[{id:"suite-favorite",label:"Toggle favorite",icon:Star,run:(row:T)=>personal.toggle(props.getRowId(row))},{id:"suite-copy-name",label:"Copy record name",icon:Copy,run:(row:T)=>writeClipboard(titleFor(row))}]:[]),...(props.rowActions || []).map(action=>({...action,run:(row:T)=>{track(row);return action.run(row);}}))]}
    /></div>
    {focused !== undefined && <GridRecordPane title={title} close={closePreview} managedFocusReturn expand={props.onOpen ? () => props.onOpen?.(focused) : undefined}>
      <div className="flex flex-wrap gap-2 pb-3" role="group" aria-label="Record preview navigation">
        <button type="button" disabled={previewRows.findIndex(row=>props.getRowId(row)===props.getRowId(focused))<=0} onClick={()=>setFocused(previewRows[previewRows.findIndex(row=>props.getRowId(row)===props.getRowId(focused))-1])}>Previous record</button>
        <button type="button" disabled={previewRows.findIndex(row=>props.getRowId(row)===props.getRowId(focused))<0 || previewRows.findIndex(row=>props.getRowId(row)===props.getRowId(focused))>=previewRows.length-1} onClick={()=>setFocused(previewRows[previewRows.findIndex(row=>props.getRowId(row)===props.getRowId(focused))+1])}>Next record</button>
        <button type="button" onClick={()=>{const text=props.columns.filter(c=>c.id!=="actions").map(c=>`${c.title}: ${c.previewValue ? c.previewValue(focused) : String(c.accessor?c.accessor(focused):(focused as Record<string,unknown>)[c.id]??"")}`).join("\n");void writeClipboard(text).then(()=>setPreviewNotice("Record details copied"),()=>setPreviewNotice("Could not copy record details"));}}>Copy details</button>
      </div>{previewNotice && <p role="status" className="text-xs">{previewNotice}</p>}
      {props.renderDetails ? props.renderDetails(focused) : <dl className="udg-details-fields">{props.columns.filter(c => c.id !== "actions").map(column => {
        const value = column.previewValue ? column.previewValue(focused) : column.accessor ? column.accessor(focused) : (focused as Record<string, unknown>)[column.id];
        return <div key={column.id}><dt>{column.title}</dt><dd>{value == null || value === "" ? "—" : String(value)}</dd></div>;
      })}</dl>}
    </GridRecordPane>}
  </div>;
}

function GridEngine<T>(props: SharedDataGridProps<T>) {
  const collectionLocation = useLocation();
  const {
    columns,
    dataSource: originalDataSource,
    getRowId,
    onOpen,
    onEdit,
    rowActions = [],
    gridId,
  } = props;
  const dataSource = useMemo(() => withAllRows(originalDataSource), [originalDataSource]);
  const user = useAuthStore((s) => s.user),
    client = useQueryClient();
  const preferenceKey = `suite-grid:v1:${props.organizationId ?? user?.access?.companyId ?? 0}:${props.userId ?? user?.id ?? 0}:${props.workspaceId ?? "organization"}:${gridId}`;
  const initial = useMemo(() => {
    let saved: {
      layout?: GridLayout;
      query?: GridQuery;
      views?: GridSavedView[];
      businessGrouping?: boolean;
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
          grouping: initialBusinessGroups(columns, `${collectionLocation.pathname}:${gridId}`, saved.query?.grouping ?? props.initialQuery?.grouping, saved.businessGrouping === true),
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
  const [storedLayout, setLayout] = useState(initial.layout),
    [query, setQuery] = useState<GridQuery>(initial.query),
    [views, setViews] = useState<GridSavedView[]>(initial.views);
  const mobile = useMobile();
  const [mobileTable, setMobileTable] = useRouteViewState(`grid:${gridId}:mobile-table`, false);
  const [selecting, setSelecting] = useState(false);
  const quickColumns = columns.filter(column => /^quick actions$/i.test(column.title));
  const quickIds = quickColumns.map(column => column.id);
  const locationIds = columns.filter(column => isLocationField(column.title)).map(column => column.id);
  const completeOrder = [...storedLayout.order, ...columns.map(column => column.id).filter(id => !storedLayout.order.includes(id))];
  const baseLayout = {
    ...storedLayout,
    ...(props.viewMode ? {view:props.viewMode} : {}),
    order: locationLast(completeOrder.filter(id => !quickIds.includes(id)), id => columns.find(column => column.id === id)?.title || "").concat(quickIds),
    visibility: {...storedLayout.visibility, ...Object.fromEntries(quickIds.map(id => [id, true]))},
    sizes: {...storedLayout.sizes, ...Object.fromEntries(quickColumns.map(column => [column.id, Math.max(250, column.width || 250, storedLayout.sizes[column.id] || 0)]))},
    pinning: {
      left: (storedLayout.pinning.left || []).filter(id => !quickIds.includes(id) && !locationIds.includes(id)),
      right: [...(storedLayout.pinning.right || []).filter(id => !quickIds.includes(id) && !locationIds.includes(id)), ...quickIds],
    },
  };
  const layout = mobile && !mobileTable && baseLayout.view === "grid" ? { ...baseLayout, view: "cards" as const } : baseLayout;
  const presets = mobilePresets(columns, user?.id);
  const [expandedCards, setExpandedCards] = useState<string[]>([]);
  const previousCollectionView = useRef<GridLayout["view"]>();
  const preservedGrouping = useRef<string[]>([]);
  useEffect(()=>{
    if(layout.view===previousCollectionView.current)return;
    if(layout.view!=="grid"){
      preservedGrouping.current=query.grouping;
      const mounting=previousCollectionView.current===undefined;
      setQuery(current=>({...current,grouping:[],path:[],page:mounting?current.page:1}));
    }else if(previousCollectionView.current&&previousCollectionView.current!=="grid"&&preservedGrouping.current.length){
      setQuery(current=>({...current,grouping:preservedGrouping.current,path:[],page:1}));
    }
    previousCollectionView.current=layout.view;
  },[layout.view]);

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
    [expanded, setExpanded] = useState<ExpandedState>(true),
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
    original: string;
    error?: string;
    busy?: boolean;
    automatic?: boolean;
  }>();
  const editWriting=useRef(false);
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
    // Mobile cards must use a flat query even when this workspace starts grouped.
    // This reset runs after the collection-view effect on mount.
    if (layout.view !== "grid") preservedGrouping.current = initial.query.grouping;
    setQuery(layout.view === "grid" ? initial.query : {...initial.query, grouping: [], path: []});
    setViews(initial.views);
    setSearch(initial.query.search);
    setChildren({});
    setExpanded(true);
    history.current = [];
    selectedCache.current.clear();
  }, [preferenceKey]);
  useEffect(() => {
    if (!props.queryState) return;
    const next = layout.view === "grid" ? props.queryState : {...props.queryState, grouping: [], path: []};
    if (JSON.stringify(next) !== JSON.stringify(query)) {
      setQuery(next);
      setSearch(next.search);
    }
  }, [JSON.stringify(props.queryState), layout.view]);
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
          businessGrouping: true,
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
  const automaticGroupLoads = useRef(new Set<string>());
  useEffect(() => {
    currentQuery.current = JSON.stringify([signature, query.page, props.refreshKey, dataSource.key]);
  }, [signature, query.page, props.refreshKey, dataSource.key]);
  useEffect(() => {
    setChildren({});
    setExpanded(true);
    automaticGroupLoads.current.clear();
  }, [signature, query.page, dataSource.key]);
  const recordSyncItems = useRecordSync();
  const request = useQuery({
    queryKey: [
      "shared-grid",
      preferenceKey,
      dataSource.key,
      query,
      props.refreshKey,
    ],
    queryFn: async ({ signal }) => validateGridResult(await dataSource.load(query, signal)),
    // A refresh version changes data freshness, not the selected list. Keep its
    // rows mounted; different filters, sources and identities get a fresh view.
    placeholderData: (previous, previousQuery) =>
      previousQuery && JSON.stringify(previousQuery.queryKey.slice(0, 4)) === JSON.stringify(["shared-grid", preferenceKey, dataSource.key, query])
        ? previous : undefined,
    staleTime: 15000,
    gcTime: 60000,
    refetchOnWindowFocus: true,
    retry: 1,
  });
  useEffect(() => {
    if (request.data) props.onResult?.(request.data);
  }, [request.data]);
  const result = request.data,
    permissions = {...result?.permissions,edit:!!result?.permissions?.edit&&moduleActionAllowed(user,location.pathname,"edit"),archive:!!result?.permissions?.archive&&moduleActionAllowed(user,location.pathname,"delete"),assign:!!result?.permissions?.assign&&moduleActionAllowed(user,location.pathname,"assign"),manualProbability:!!result?.permissions?.manualProbability&&moduleActionAllowed(user,location.pathname,"edit"),export:!!result?.permissions?.export&&moduleActionAllowed(user,location.pathname,"export")};
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
  const changeQuery = (next: GridQuery, replaceSearch = false) => {
    const composed = mergePendingGridSearch(query, next, search, replaceSearch);
    setQuery(composed);
    // Publish shared workspace filters before another view can unmount this table.
    if (props.compactControls && props.queryState) props.onQueryChange?.(composed);
    setSearch(composed.search);
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
        size: c.width || 220,
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
    recordNodes = modelRows.filter((row) => row.original.record);
  const visibleRecords = useMemo(() => modelRows.flatMap(row => row.original.record ? [row.original.record] : []), [modelRows]);
  useEffect(() => { props.onVisibleRecordsChange?.(visibleRecords); }, [visibleRecords]);
  const summaryRecords = dataSource.summaryRows?.(query) ?? [...new Map([
    ...(result?.rows || []),
    ...Object.values(children).flatMap(branch => branch.flatMap(node => node.record ? [node.record] : [])),
  ].map(row => [getRowId(row),row])).values()];
  const left = table.getLeftVisibleLeafColumns(),
    center = table.getCenterVisibleLeafColumns(),
    right = table.getRightVisibleLeafColumns(),
    ordered = [...left, ...center, ...right];
  const rowVirtual = useVirtualizer({
    count: modelRows.length,
    getScrollElement: () => scroll.current,
    estimateSize: (index) => modelRows[index]?.original.group ? (mobile ? 44 : 34) : Math.max(mobile ? 48 : 32, layout.rowHeights?.[modelRows[index]?.original.id] ?? effectiveRowHeight),
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
  }, [effectiveRowHeight, layout.rowHeights, mobile, modelRows.length, query.grouping.join("|")]);
  // Derived layout arrays can have new identities without changing any geometry.
  // Measuring those again updates the virtualizer and can sustain a render loop.
  const columnGeometry = JSON.stringify([effectiveSizes, layout.order, layout.visibility, effectivePinning]);
  useEffect(() => {
    columnVirtual.measure();
  }, [columnGeometry]);
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
  const actionWidth = rowActions.length ? props.renderRowActions ? 96 : Math.min(props.quickActionLimit ?? 4, rowActions.filter(action => action.quick).length) * 34 + 40 : 0;
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
        800,
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
      if (to === "grid-group-zone" || to.startsWith("group-column:")) {
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
  async function loadBranch(path: GridGroup["path"], parent: string, page = 1, fresh = false) {
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
        staleTime: fresh ? 0 : 15000,
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
  // Grouping keeps records visible by default, including each nested level.
  // Bound concurrent branch requests and remember failures until the query changes
  // so an unavailable branch cannot cause an automatic retry loop.
  useEffect(() => {
    if (!request.data || request.isPlaceholderData) return;
    const version = currentQuery.current;
    const pending = table.getRowModel().rows.filter(row =>
      row.original.group && row.getIsExpanded() && !children[row.id] &&
      !automaticGroupLoads.current.has(row.id),
    );
    void (async () => {
      for (let index = 0; index < pending.length; index += 3) {
        if (version !== currentQuery.current) return;
        const batch = pending.slice(index, index + 3).filter(row => !automaticGroupLoads.current.has(row.id));
        batch.forEach(row => automaticGroupLoads.current.add(row.id));
        await Promise.all(batch.map(row => loadBranch(row.original.group!.path, row.id)));
      }
    })();
  }, [nodes, expanded, request.data, request.isPlaceholderData]);
  // A successful edit refreshes the data, while the user's expanded groups stay open.
  useEffect(() => {
    if (!request.data || request.isPlaceholderData) return;
    const opened = table.getRowModel().flatRows.filter(row => row.original.group && row.getIsExpanded());
    const version = currentQuery.current;
    void Promise.all(opened.map(async row => {
      const loaded = children[row.id] || [];
      const more = loaded.find(node => node.more)?.more;
      const pages = more ? more.page - 1 : Math.max(1, Math.ceil(loaded.length / query.pageSize));
      for (let page = 1; page <= pages && version === currentQuery.current; page++) {
        await loadBranch(row.original.group!.path, row.id, page, true);
      }
    }));
  }, [request.dataUpdatedAt, props.refreshKey]);
  const [expandingAll, setExpandingAll] = useState(false);
  async function expandLoadedGroups() {
    if (expandingAll) return;
    setExpandingAll(true);
    const originalSignature = currentQuery.current;
    try {
      const groups = table.getRowModel().rows.filter(row => row.original.group);
      for (let index = 0; index < groups.length; index += 3) {
        if (originalSignature !== currentQuery.current) return;
        await Promise.all(groups.slice(index,index + 3).filter(row=>!children[row.id]).map(row=>loadBranch(row.original.group!.path,row.id)));
      }
      if (originalSignature === currentQuery.current) setExpanded(previous => ({ ...(typeof previous === "object" ? previous : {}), ...Object.fromEntries(groups.map(row => [row.id, true])) }));
    } finally { setExpandingAll(false); }
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
  const [undoEdit, setUndoEdit] = useState<{ row: string; column: string; before: string; after: string }>();
  const [undoBusy, setUndoBusy] = useState(false);
  const [busyAction, setBusyAction] = useState<string>();
  const actionInFlight = useRef(false);
  // Restored controlled selections contain IDs only. Resolve permitted rows from
  // the current load before falling back to this grid's in-session page cache.
  const visibleById = new Map(visibleRecords.map(row => [getRowId(row), row]));
  const selectedRecords = selection.map(id => visibleById.get(id) ?? selectedCache.current.get(id)).filter((row): row is T => row !== undefined);
  async function runBulkAction(action: NonNullable<SharedDataGridProps<T>["bulkActions"]>[number]) {
    if (bulkBusy || selectedRecords.length !== selection.length || action.disabled?.(selectedRecords)) return;
    if (action.confirm && !window.confirm(action.confirm(selectedRecords))) return;
    setBulkBusy(action.id); setActionError("");
    try { await action.run(selectedRecords); emitSelection([]); await request.refetch(); }
    catch (error) { setActionError(errorText(error)); }
    finally { setBulkBusy(undefined); }
  }
  async function runAction(action: GridAction<T>, row: T) {
    if (actionInFlight.current) return;
    if (action.disabled?.(row)) { setActionError(action.disabledReason || "This action is unavailable for this record."); return; }
    actionInFlight.current = true; setBusyAction(getRowId(row));
    try {
      setActionError("");
      await withEditNavigation(action,()=>action.run(row));
    } catch (e) {
      setActionError(errorText(e));
    } finally { actionInFlight.current = false; setBusyAction(undefined); }
  }
  function domainRowActions(record:T) {
    return props.renderRowActions?.(record,rowActions.filter(action=>!action.visible||action.visible(record)).map(action=>({...action,run:(row:T)=>runAction(action,row)})));
  }
  const rowGroupColumn = columns.find(column => query.grouping.includes(column.id) && !/priority/i.test(column.title)) || businessGroupColumn(columns, `${collectionLocation.pathname}:${gridId}`);
  const categoryColors = new Map<string,Map<string,string>>();
  function collectGroupLabels(items:Node<T>[], labels:Map<string,Set<string>>) {
    for(const node of items) {
      if(node.group) {
        const title=columns.find(column=>column.id===node.group!.field)?.title || "";
        const values=labels.get(title)||new Set<string>(); values.add(node.group.label); labels.set(title,values);
      }
      if(node.record && rowGroupColumn) {
        const values=labels.get(rowGroupColumn.title)||new Set<string>();values.add(textFor(node.record,rowGroupColumn).trim()||"Not set");labels.set(rowGroupColumn.title,values);
      }
      if(node.children)collectGroupLabels(node.children,labels);
    }
  }
  const categoryLabels=new Map<string,Set<string>>();collectGroupLabels(nodes,categoryLabels);
  for(const [title,labels] of categoryLabels)categoryColors.set(title,groupCategoryColors(labels));
  const categoryColor=(label:string,field="")=>categoryColors.get(field)?.get(label)||groupAppearance(label,field).color;
  function rowGroupStyle(record:T): CSSProperties {
    if (!rowGroupColumn) return {};
    const color = categoryColor(textFor(record,rowGroupColumn).trim() || "Not set",rowGroupColumn.title);
    return color ? {"--record-group-accent":color,"--record-group-bg":`color-mix(in srgb, ${color} 7%, hsl(var(--card)))`,"--record-group-hover":`color-mix(in srgb, ${color} 13%, hsl(var(--card)))`} as CSSProperties : {};
  }
  function rowGroup(record:T) {
    if (!rowGroupColumn) return {};
    const value = textFor(record, rowGroupColumn).trim() || "Not set";
    return {"data-record-group-tone":groupAppearance(value, rowGroupColumn.title).tone,"data-record-group-field":rowGroupColumn.title,"data-record-group-value":value};
  }
  function priorityFor(record:T) {
    const column=columns.find(column=>/\bpriority\b/i.test(column.title.trim()));
    return recordPriority(record) || (column ? normalizePriority(textFor(record,column)) : undefined);
  }
  function renderCollectionRecord(record:T) {
    const actions=rowActions.filter(action=>!action.visible||action.visible(record));
    const quick = actions.filter(action => action.quick && (!mobile || !action.danger));
    if (mobile) quick.sort((a, b) => Number(/preview|open|view/i.test(a.id)) - Number(/preview|open|view/i.test(b.id)));
    const fields = columns.filter(column => column.id !== "__suite_favorite" && layout.visibility[column.id] !== false && !/^(select|actions?|quick actions)$/i.test(column.title));
    if (mobile) fields.sort((a, b) => {
      const rank = (column: GridColumn<T>) => /^(name|title|full_name|fullName|subject)$/i.test(column.id) || /^(name|title|full name|subject|customer|employee|project|deal|lead|contact|company|sales order|invoice|contract|record|item|product)$/i.test(column.title) ? 0 : column.type === "status" ? 1 : /due|next.*(date|action|follow)/i.test(column.title) ? 2 : column.type === "owner" ? 3 : 4;
      return rank(a) - rank(b);
    });
    const more = expandedCards.includes(getRowId(record));
    const actionFields = columns.filter(column => layout.visibility[column.id] !== false && /^(actions?|quick actions)$/i.test(column.title));
    return <article data-grid-record-id={getRowId(record)} data-priority-row={!!priorityFor(record)} data-priority={priorityFor(record)} key={getRowId(record)} {...recordPreviewProps(record)} onClickCapture={event=>props.rowProps?.(record)?.onClickCapture?.(event as any)} onClick={event=>{props.rowProps?.(record)?.onClick?.(event as any);if(!event.defaultPrevented && !(event.target as HTMLElement).closest("button,a,input,select,textarea,summary"))selectRecord(record);}} onDoubleClick={event=>{if(!(event.target as HTMLElement).closest("button,a,input,select,textarea,summary"))onOpen?.(record);}}>
      {columns.find(column=>column.id==="__suite_favorite")?.render?.(record)}
      {mobile && (selecting || selection.length > 0) && props.selectionEnabled !== false && <label className="udg-card-select"><input type="checkbox" aria-label={`Select record ${getRowId(record)}`} checked={selection.includes(getRowId(record))} onChange={event => emitSelection(event.target.checked ? [...new Set([...selection, getRowId(record)])] : selection.filter(id => id !== getRowId(record)))} />Select</label>}
      {mobile && columns.filter(column => /^(select|selection)$/i.test(column.title)).map(column => <div className="udg-card-select" key={column.id}>{displayFor(record, column)}</div>)}
      {props.renderCard?.(record)||<div className="udg-record-fields">{fields.slice(0, mobile && !more ? 4 : 7).map(column=><div className="udg-record-field" key={column.id}><small>{column.title}</small>{displayFor(record,column)}</div>)}{mobile && more && fields.slice(7).map(column => <div className="udg-record-field" key={column.id}><small>{column.title}</small>{displayFor(record,column)}</div>)}</div>}
      {mobile && !props.renderCard && fields.length > 4 && <button type="button" className="udg-card-details" aria-expanded={more} onClick={() => setExpandedCards(ids => more ? ids.filter(id => id !== getRowId(record)) : [...ids, getRowId(record)])}>{more ? "Show less" : "More details"}</button>}
      {!!actionFields.length && (mobile ? <details className="udg-card-native-actions"><summary>More actions</summary><div>{actionFields.map(column => <div key={column.id}>{displayFor(record, column)}</div>)}</div></details> : actionFields.map(column => <div className="udg-record-field" key={column.id}><small>{column.title}</small>{displayFor(record, column)}</div>))}
      <div className="udg-card-actions">{props.renderRowActions ? domainRowActions(record) : <>{quick.slice(0,mobile ? 1 : 4).map(action=><button type="button" key={action.id} title={action.label} aria-label={action.label} aria-busy={busyAction === getRowId(record) || undefined} disabled={!!busyAction || action.disabled?.(record)} onClick={()=>void runAction(action,record)}>{action.icon&&<action.icon size={15}/>} {mobile && action.label}</button>)}{mobile && !quick.length && onOpen && <button type="button" onClick={() => onOpen(record)}><Eye size={16} />Open record</button>}{actions.length>0&&<Dropdown.Root modal={false}><Dropdown.Trigger aria-label="Record quick actions" title="Record quick actions"><MoreHorizontal size={16}/></Dropdown.Trigger><Dropdown.Portal><Dropdown.Content className="udg-menu" align="end" collisionPadding={10}>{actions.map(action=><Dropdown.Item key={action.id} disabled={!!busyAction || action.disabled?.(record)} onSelect={()=>void runAction(action,record)}>{action.icon&&<action.icon size={14}/>} {action.label}</Dropdown.Item>)}</Dropdown.Content></Dropdown.Portal></Dropdown.Root>}</>}</div>
    </article>;
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
    setEdit({ row: node.id, column: def.id, value: editorValue, original:editorValue });
  }
  async function commitEdit(node: Node<T>, def: GridColumn<T>, automatic=false) {
    if (!edit || !node.record || edit.busy || editWriting.current) return false;
    const validation = def.validate?.(edit.value, node.record);
    if (validation) {setEdit({ ...edit, error: validation });return false;}
    const captured=edit;editWriting.current=true;
    setEdit({ ...edit, busy: true, automatic, error: undefined });
    try {
      await onEdit?.(node.record, def.id, captured.value);
      setUndoEdit({ row: captured.row, column: def.id, before: captured.original, after: captured.value });
      if(automatic)setEdit(current=>current?.row===captured.row&&current.column===captured.column?{...current,original:captured.value,busy:false,automatic:false}:current);
      else setEdit(undefined);
      void request.refetch();setNotice(`${def.title} saved.`);return true;
    } catch (e) {
      setEdit(current=>current?.row===captured.row&&current.column===captured.column?{...current,error:errorText(e),busy:false,automatic:false}:current);return false;
    } finally {editWriting.current=false;}
  }
  const cellAuto=useRecordAutosave({value:edit?{row:edit.row,column:edit.column,value:edit.value}:null,enabled:!!edit&&!edit.busy&&permissions.edit&&!!onEdit,dirty:!!edit&&edit.value!==edit.original,save:async()=>{
    if(!edit)return false;
    const node=table.getRow(edit.row).original,def=columns.find(column=>column.id===edit.column);
    return def?commitEdit(node,def,true):false;
  }});
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
  function textFor(row: T, def: GridColumn<T>): string {
    const value = def.accessor ? def.accessor(row) : (row as Record<string, unknown>)[def.id];
    return String(def.exportValue?.(row) ?? value ?? "");
  }
  function rowLabel(row:T):string {
    const identity=columns.find(column=>/^(name|title|full_name|fullName|display_name|subject|item_name|project_name|employee_name|legal_name)$/i.test(column.id))
      ||columns.find(column=>/name|title|subject/i.test(column.title)&&!/company|owner|manager|assignee/i.test(column.title))
      ||columns.find(column=>column.id!=="__suite_favorite");
    const label=identity?textFor(row,identity).trim():"";
    return label&&label!=="—"?label:String((row as Record<string,unknown>).name||(row as Record<string,unknown>).title||getRowId(row));
  }
  function displayFor(row: T, def: GridColumn<T>) {
    if (isPhoneField(def.id)) {
      return <PhoneActions value={def.accessor ? def.accessor(row) : (row as Record<string, unknown>)[def.id]} record={row} field={def.id} />;
    }
    if(def.render) return def.render(row);
    const value=def.accessor?def.accessor(row):(row as Record<string,unknown>)[def.id];
    if(typeof value==="number"&&Number.isFinite(value)&&value>=0&&value<=100&&/^(progress|completion)(?:\s*(?:percent|percentage|\(%\)|%))?$/i.test(def.title.trim()))return columnValue(def.title,`${value}%`);
    return columnValue(def.title,textFor(row,def) || "—");
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
      await writeClipboard(copied);
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
        await writeClipboard(
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
        disabled: edit.busy&&!edit.automatic,
        "aria-label": `Edit ${definition.title}`,
        onChange: (
          e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
        ) => setEdit({ ...edit, value: e.target.value, error: undefined }),
        onKeyDown: (e: KeyboardEvent<HTMLInputElement | HTMLSelectElement>) => {
          e.stopPropagation();
          if (e.key === "Enter" || (e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="s") {
            e.preventDefault();
            if(!e.repeat)void commitEdit(node, definition);
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
            data-save-action
            aria-label="Save cell"
            onClick={() => void commitEdit(node, definition)}
          >
            ✓
          </button>
          <button aria-label="Cancel cell edit" onClick={cancelEdit}>
            <X size={12} />
          </button>
          {cellAuto.message&&<span role="status">{cellAuto.message}</span>}
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
          aria-colindex={ordered.findIndex((c) => c.id === column.id) + 1 + (selectionWidth ? 1 : 0)}
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
          {column.id===ordered.find(item=>!/^(?:actions|select|__suite_)/.test(item.id))?.id && node.record && rowSync(recordSyncItems,[getRowId(node.record)],new URLSearchParams(location.search).get("operation")||location.pathname).filter(item=>item.phase==="pending").slice(-1).map(item=><span className="record-sync-row-marker" key={item.id}><SyncRing item={item}/></span>)}
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
        selectionOffset={selectionWidth ? 1 : 0}
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
  const chartColumn = columns.find(column => column.type === "status");
  const statistics = props.statistics && result
        ? props.statistics(result)
        : result && !!result.aggregates?.length && (
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
          );
  const savedViewControls = <SavedViewsManager
          title={props.savedViewsTitle}
          label={props.savedViewsLabel || (props.compactControls ? "Table layouts" : undefined)}
          extra={props.savedViewsExtra}
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
            changeQuery(restoredQuery, true);
            // Restoring context can remount the adapter before the persistence effect runs.
            try {
              localStorage.setItem(preferenceKey, JSON.stringify({ layout: sanitizeLayout(view.layout, columns), query: restoredQuery, views, businessGrouping: true }));
            } catch {
              setNotice("Layout could not be saved in this browser.");
            }
            if (props.onRestoreView) props.onRestoreView({ ...view, query: restoredQuery });
            else props.onViewContextChange?.(view.context || {});
          }}
          remove={(id) => setViews((v) => v.filter((view) => view.id !== id))}
        />;
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
      {!props.compactControls && props.overview !== false && collectionLocation.pathname !== "/pms/projects" && result && <CollectionOverview compact={props.compactControls} rows={summaryRecords} fields={columns.filter(c=>!/^(__suite_|actions|select)/.test(c.id)).map(c=>({id:c.id,title:c.title,value:(row:T)=>c.accessor?c.accessor(row):(row as Record<string,unknown>)[c.id]}))} total={props.dataScope === "loaded" ? undefined : result.total} onOpen={onOpen}/>}
      {!props.compactControls && statistics}
      {!props.compactControls && visibleRecords.length > 0 && columns.find(column => column.type === "status") && <SuiteDistribution records={visibleRecords} field={columns.find(column => column.type === "status")!.id} label={columns.find(column => column.type === "status")!.title} />}
      <GridToolbar
        search={search}
        hideSearch={props.hideSearch}
        searchPlaceholder={props.dataScope === "loaded" ? "Search loaded records…" : undefined}
        setSearch={setSearch}
        filterCount={filterRules(query.filters).length}
        openFilters={() => setFilterOpen(true)}
        layout={layout}
        updateLayout={updateLayout}
        views={props.viewMode ? [props.viewMode] : props.views || ["grid"]}
        extra={props.compactControls ? <>{props.overview !== false && result && <CollectionOverview compact rows={summaryRecords} fields={columns.filter(c=>!/^(__suite_|actions|select)/.test(c.id)).map(c=>({id:c.id,title:c.title,value:(row:T)=>c.accessor?c.accessor(row):(row as Record<string,unknown>)[c.id]}))} total={props.dataScope === "loaded" ? undefined : result.total} onOpen={onOpen}>{statistics}{visibleRecords.length > 0 && columns.find(column => column.type === "status") && <SuiteDistribution records={visibleRecords} field={columns.find(column => column.type === "status")!.id} label={columns.find(column => column.type === "status")!.title}/>}</CollectionOverview>} {props.toolbarExtra}</> : props.toolbarExtra}
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
        {props.savedViewsHost ? createPortal(savedViewControls, props.savedViewsHost) : savedViewControls}
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
      {mobile && <div className="udg-mobile-presets" aria-label="Quick filters">
        {props.selectionEnabled !== false && <button type="button" aria-pressed={selecting} onClick={() => { setSelecting(value => !value); if (selecting) emitSelection([]); }}>{selecting ? "Done selecting" : "Select records"}</button>}
        {presets.map(preset => <button type="button" key={preset.label} aria-pressed={hasMobilePreset(query.filters, preset)} onClick={() => changeQuery({ ...query, filters: toggleMobilePreset(query.filters, preset, presets), page: 1 })}>{preset.label}</button>)}
        {baseLayout.view === "grid" && <button type="button" onClick={() => setMobileTable(value => !value)}>{mobileTable ? "Cards view" : "Table view"}</button>}
      </div>}
      {undoEdit && <div className="udg-edit-undo" role="status"><span>Change saved</span><button type="button" disabled={undoBusy || request.isFetching || !!edit || !permissions.edit || !onEdit} onClick={async () => {
        const row = visibleRecords.find(record => getRowId(record) === undoEdit.row), column = columns.find(column => column.id === undoEdit.column);
        if (!row || !column || String(column.accessor ? column.accessor(row) ?? "" : (row as Record<string, unknown>)[column.id] ?? "") !== undoEdit.after) { setActionError("This record changed. Open it to review the latest value before editing."); setUndoEdit(undefined); return; }
        setUndoBusy(true);
        try { await onEdit?.(row, column.id, undoEdit.before); setUndoEdit(undefined); await request.refetch(); setNotice("Change undone."); } catch (error) { setActionError(errorText(error)); } finally { setUndoBusy(false); }
      }}>{undoBusy ? "Undoing…" : "Undo"}</button><button type="button" aria-label="Dismiss undo" onClick={() => setUndoEdit(undefined)}>Dismiss</button></div>}
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
              }, true);
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
          {props.bulkToolbar}
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
        collisionDetection={args => {
          const hits = pointerWithin(args);
          const groupZone = hits.find(hit => hit.id === "grid-group-zone");
          return groupZone ? [groupZone] : hits.length ? hits : closestCenter(args);
        }}
        onDragEnd={dragEnd}
      >
        <GroupingPanel columns={columns} query={query} change={changeQuery} loadedOnly={props.dataScope === "loaded"}
          expandAll={() => void expandLoadedGroups()} collapseAll={() => setExpanded({})} expanding={expandingAll}/>
        {layout.view === "grid" ? (
          <div
            className="udg-scroll"
            data-navigation-region={`grid:${gridId}`}
            ref={scroll}
            style={{ height: props.height || Math.min(540, Math.max(120, (request.isPending ? 8 * effectiveRowHeight : rowVirtual.getTotalSize()) + 40)) }}
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
                          height: virtual.size,
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
                              <GroupLabel color={categoryColor(node.group.label,columns.find(c => c.id === node.group!.field)?.title)} label={node.group.label} field={columns.find(c => c.id === node.group!.field)?.title} count={node.group.count}/>
                            </button>
                            {node.group.aggregates.length > 0 && <NativeSelect
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
                            </NativeSelect>}
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
                            {...rowGroup(record)}
                            data-priority-row={!!priorityFor(record)}
                            data-priority={priorityFor(record)}
                            role="row"
                            data-resize-row={virtual.index}
                            aria-selected={selection.includes(node.id)}
                            aria-rowindex={
                              (query.page - 1) * query.pageSize +
                              virtual.index +
                              2
                            }
                            className={`udg-row ${edit?.row === node.id ? "is-editing" : ""} ${virtual.index % 2 ? "udg-row-alt" : ""} ${selection.includes(node.id) ? "is-selected" : ""}`}
                            style={{...position,...rowGroupStyle(record)}}
                            {...recordPreviewProps(record)}
                            onClick={event => {
                              props.rowProps?.(record).onClick?.(event);
                              if (event.defaultPrevented) return;
                              if (!(event.target as HTMLElement).closest('button,a,input,select,textarea,[role="checkbox"],[role="separator"],[contenteditable="true"]') || (event.target as HTMLElement).closest("[data-record-open]")) selectRecord(record);
                            }}
                            onDoubleClickCapture={event => {
                              clearTimeout(selectRecordTimer.current);
                              const action = (event.target as HTMLElement).closest('button,a,input,select,textarea,[role="checkbox"],[role="separator"],[contenteditable="true"]');
                              if (action && !action.hasAttribute('data-record-open')) return;
                              if (onOpen) { event.preventDefault(); event.stopPropagation(); onOpen(record); }
                              else if (props.onOpenPopup) { event.preventDefault(); event.stopPropagation(); props.onOpenPopup(record); }
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
                            <RowResizeHandle height={virtual.size} change={height => updateLayout({ ...layout, rowHeights: { ...layout.rowHeights, [node.id]: height } })} fit={() => fitRow(scroll.current?.querySelector<HTMLElement>(`[data-resize-row="${virtual.index}"]`) ?? null)}/>
                            {selectionWidth > 0 && <div className="udg-select-cell" role="gridcell">
                              <input
                                aria-label={`Select row ${rowLabel(record)}`}
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
                                {props.renderRowActions ? domainRowActions(record) : <>{rowActions
                                  .filter(
                                    (a) =>
                                      a.quick &&
                                      (!a.visible || a.visible(record)),
                                  )
                                  .slice(0, props.quickActionLimit ?? 4)
                                  .map((action) => (
                                    <button
                                      key={action.id}
                                      className="udg-hover-action"
                                      data-action={action.id}
                                      aria-label={`${action.label} ${rowLabel(record)}`}
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
                                {rowActions.filter(a => !a.visible || a.visible(record)).some((a, _, actions) => !a.quick || actions.filter(item => item.quick).indexOf(a) >= (props.quickActionLimit ?? 4)) && <Dropdown.Root>
                                  <Dropdown.Trigger
                                    aria-label={`Actions for ${rowLabel(record)}`}
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
                                        .filter((a, _, actions) => !a.quick || actions.filter(item => item.quick).indexOf(a) >= (props.quickActionLimit ?? 4))
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
                                </Dropdown.Root>}</>}
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
                {props.emptyContent ? <div>{props.emptyContent}</div> : <p>Try a different search or clear your filters.</p>}
              </div>
            )}
          </div>
        ) : (
          <div className={`udg-alternate udg-view-${layout.view}`} data-navigation-region={`grid:${gridId}:alternate:${layout.view}`}>
            {props.collectionGroup || layout.view === "kanban" ? (()=>{
              const field=columns.find(column=>column.id===(props.collectionGroup||props.kanbanField||"status"));
              const groups=new Map<string,T[]>();
              for(const record of visibleRecords){const raw=field?.accessor?.(record) ?? (record as Record<string,unknown>)[field?.id||"status"];const labels=field&&/tags?|labels/i.test(field.title)?Array.isArray(raw)?raw.map(String):String(raw||"").split(",").map(value=>value.trim()).filter(Boolean):[String(raw||"Not set")];for(const label of labels.length?labels:["Untagged"])groups.set(label,[...(groups.get(label)||[]),record]);}
              return [...groups].map(([label,records])=><section className="suite-record-group" key={label}><h3><GroupLabel color={categoryColor(label,field?.title)} label={label} field={field?.title} count={records.length}/></h3><div className="udg-alternate udg-view-cards">{records.map(renderCollectionRecord)}</div></section>);
            })() : visibleRecords.map(renderCollectionRecord)}
            {!visibleRecords.length&&<p className="suite-record-empty">No records in this view. Your current filters and access still apply.</p>}
            <small>Alternate views show loaded records from the same filtered data source.</small>
          </div>
        )}
      </DndContext>
      <div className="udg-summary-footer">
        <strong>{result?.total.toLocaleString() || 0} matching records</strong>
        <span>{props.dataScope === "loaded" ? "Loaded records only" : "Full filtered dataset"}</span>
        {result?.aggregates?.map((a) => (
          <span key={a.currency}>
            <b>{a.currency}</b> Sum {formatMoney(a.sum, a.currency)} · Average{" "}
            {formatMoney(a.avg, a.currency)}
          </span>
        ))}
      </div>
      {(!props.externalPagination || query.pageSize === 0 || (result?.pageTotal || 0) > query.pageSize) && <footer className="udg-pagination">
        <label>
          {props.dataScope === "loaded" ? "Loaded rows per page" : "Rows per page"}
          <NativeSelect
            aria-label={props.dataScope === "loaded" ? "Loaded rows per page" : "Rows per page"}
            value={query.pageSize}
            onChange={(e) =>
              changeQuery({
                ...query,
                pageSize: Number(e.target.value),
                page: 1,
              })
            }
          >
            {[10, 25, 50, 100, 200, 0].map((size) => (
              <option key={size} value={size}>{size === 0 ? "All" : size}</option>
            ))}
          </NativeSelect>
        </label>
        <span>
          {query.grouping.length ? "Group page" : "Page"} {query.page} of{" "}
          {query.pageSize === 0 ? 1 : Math.max(1, Math.ceil((result?.pageTotal || 0) / query.pageSize))}
        </span>
        <button
          disabled={query.page <= 1 || request.isFetching}
          onClick={() => changeQuery({ ...query, page: query.page - 1 })}
        >
          Previous
        </button>
        <button
          disabled={
            query.pageSize === 0 || query.page * query.pageSize >= (result?.pageTotal || 0) ||
            request.isFetching
          }
          onClick={() => changeQuery({ ...query, page: query.page + 1 })}
        >
          Next
        </button>
      </footer>}
      {filterOpen && (
        <FilterBuilder
          dataScope={props.dataScope}
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

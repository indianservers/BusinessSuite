import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import type {
  SortingState,
  ColumnPinningState,
  VisibilityState,
  ColumnSizingState,
} from "@tanstack/react-table";

export type GridValue = string | number | boolean | null;
export type GridOperator =
  | "equals"
  | "not_equals"
  | "contains"
  | "starts_with"
  | "ends_with"
  | "between"
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "empty"
  | "not_empty"
  | "in";
export type GridRule = {
  field: string;
  operator: GridOperator;
  value?: GridValue | GridValue[];
  value2?: GridValue;
};
export type GridFilter = {
  logic: "and" | "or";
  rules: (GridRule | GridFilter)[];
};
export type GridPath = { field: string; value: string | number | null }[];
export type GridQuery = {
  search: string;
  filters: GridFilter;
  sorting: SortingState;
  grouping: string[];
  path: GridPath;
  page: number;
  pageSize: number;
};
export type GridAggregate = {
  currency?: string;
  count: number;
  sum: number;
  avg: number;
  min: number;
  max: number;
  weighted?: number;
};
export type GridGroup = {
  field: string;
  value: GridValue;
  label: string;
  count: number;
  aggregates: GridAggregate[];
  path: GridPath;
};
export type GridResult<T> = {
  rows: T[];
  groups?: GridGroup[];
  total: number;
  pageTotal: number;
  page: number;
  pageSize: number;
  aggregates?: GridAggregate[];
  permissions?: {
    edit?: boolean;
    export?: boolean;
    archive?: boolean;
    assign?: boolean;
    manualProbability?: boolean;
  };
  context?: Record<string, unknown>;
};
export type GridExportRequest = {
  format: "csv" | "xlsx" | "pdf" | "clipboard";
  scope: "visible" | "selected" | "filtered";
  ids: string[];
  columns: string[];
  includeGroups: boolean;
  includeSummaries: boolean;
  query: GridQuery;
};
export type GridDataSource<T> = {
  key: string;
  load: (query: GridQuery, signal?: AbortSignal) => Promise<GridResult<T>>;
  facets?: (
    field: string,
    search: string,
    query: GridQuery,
    signal?: AbortSignal,
  ) => Promise<{
    values: { value: GridValue; label: string; count?: number }[];
    hasMore?: boolean;
  }>;
  export?: (request: GridExportRequest) => Promise<Blob | string>;
};
export type GridColumn<T> = {
  id: string;
  title: string;
  type?:
    | "text"
    | "number"
    | "currency"
    | "date"
    | "datetime"
    | "status"
    | "owner"
    | "category";
  icon?: LucideIcon;
  width?: number;
  minWidth?: number;
  align?: "left" | "right" | "center";
  accessor?: (row: T) => unknown;
  render?: (row: T) => ReactNode;
  exportValue?: (row: T) => string;
  sortable?: boolean;
  filterable?: boolean;
  groupable?: boolean;
  editable?: boolean | ((row: T) => boolean);
  editor?: "text" | "number" | "date" | "datetime-local" | "select";
  options?: { value: string; label: string }[];
  validate?: (value: string, row: T) => string | undefined;
};
export type GridLayout = {
  order: string[];
  visibility: VisibilityState;
  pinning: ColumnPinningState;
  sizes: ColumnSizingState;
  density: "compact" | "comfortable";
  rowHeight: number;
  view: "grid" | "cards" | "list" | "kanban";
  summary: "sum" | "avg" | "min" | "max" | "count";
};
export type GridSavedView = {
  id: string;
  name: string;
  layout: GridLayout;
  query: GridQuery;
  context?: Record<string, unknown>;
};
export type GridAction<T> = {
  id: string;
  label: string;
  icon?: LucideIcon;
  danger?: boolean;
  quick?: boolean;
  visible?: (row: T) => boolean;
  run: (row: T) => void | Promise<void>;
};
export type SharedDataGridProps<T> = {
  gridId: string;
  title?: string;
  columns: GridColumn<T>[];
  dataSource: GridDataSource<T>;
  getRowId: (row: T) => string;
  userId?: number;
  organizationId?: number;
  workspaceId?: number | string;
  initialQuery?: Partial<GridQuery>;
  queryState?: GridQuery;
  initialLayout?: Partial<GridLayout>;
  refreshKey?: number;
  selectedIds?: string[];
  onSelectionChange?: (records: T[], ids: string[]) => void;
  onQueryChange?: (query: GridQuery) => void;
  externalFilters?: { id: string; label: string; clear: () => void }[];
  onClearFilters?: () => void;
  viewContext?: Record<string, unknown>;
  onViewContextChange?: (context: Record<string, unknown>) => void;
  onRestoreView?: (view: GridSavedView) => void;
  onResult?: (result: GridResult<T>) => void;
  onOpen?: (row: T) => void;
  onEdit?: (row: T, column: string, value: string) => Promise<void>;
  rowActions?: GridAction<T>[];
  toolbarExtra?: ReactNode;
  renderCard?: (row: T) => ReactNode;
  views?: GridLayout["view"][];
  kanbanField?: string;
  manualOrder?: { move: (row: T, before: T) => Promise<void> };
  height?: number;
  statistics?: (result: GridResult<T>) => ReactNode;
  defaultExportColumns?: string[];
  exportFormats?: GridExportRequest["format"][];
};
export const emptyQuery = (): GridQuery => ({
  search: "",
  filters: { logic: "and", rules: [] },
  sorting: [],
  grouping: [],
  path: [],
  page: 1,
  pageSize: 50,
});

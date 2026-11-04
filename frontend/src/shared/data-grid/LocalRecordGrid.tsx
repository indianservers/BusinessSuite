import { useMemo } from "react";
import SharedDataGrid from "./SharedDataGrid";
import { localGridSource } from "./local-source";
import type { SharedDataGridProps } from "./types";

/** For pages whose existing API already owns filtering and pagination. */
export default function LocalRecordGrid<T>({ rows, allowExport = false, ...props }: Omit<SharedDataGridProps<T>, "dataSource"> & { rows: T[]; allowExport?: boolean }) {
  const signature = JSON.stringify(rows);
  const source = useMemo(() => {
    let hash = 2166136261;
    for (let i = 0; i < signature.length; i++) hash = Math.imul(hash ^ signature.charCodeAt(i), 16777619);
    const source = localGridSource(`${props.gridId}:${hash >>> 0}`, rows, props.columns, props.getRowId);
    return allowExport ? source : { ...source, export: undefined };
  }, [signature, props.gridId, props.columns, props.getRowId, allowExport]);
  return <SharedDataGrid {...props} dataSource={source} exportFormats={["csv", "clipboard"]}
    statistics={props.statistics || (result => <div className="udg-statistics"><div><span>Matching loaded records</span><strong>{result.total.toLocaleString()}</strong></div><p className="udg-scope-note">Grid controls apply to loaded records. Use page filters and pagination to load other records.</p></div>)}/>;
}

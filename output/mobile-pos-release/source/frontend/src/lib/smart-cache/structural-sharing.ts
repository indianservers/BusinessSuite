import { rowId, type Row } from './model';
/** Retain row identities even when sorting or insertion moves their array positions. */
export function shareRecordReferences(previous: unknown, incoming: unknown): unknown {
  if (previous === incoming) return previous;
  if (!previous || !incoming || typeof previous !== 'object' || typeof incoming !== 'object') return incoming;
  if (Array.isArray(incoming)) {
    if (!Array.isArray(previous)) return incoming;
    const recordList = incoming.every(row => rowId(row as Row) !== undefined) && previous.every(row => rowId(row as Row) !== undefined);
    const unique = recordList && new Set(incoming.map(row => rowId(row as Row))).size === incoming.length && new Set(previous.map(row => rowId(row as Row))).size === previous.length;
    const byId = unique ? new Map(previous.map(row => [rowId(row as Row), row])) : undefined;
    const rows = incoming.map((row, index) => shareRecordReferences(byId ? byId.get(rowId(row as Row)) : previous[index], row));
    return rows.length === previous.length && rows.every((row, i) => row === previous[i]) ? previous : rows;
  }
  if (Array.isArray(previous) || Object.getPrototypeOf(incoming) !== Object.prototype || Object.getPrototypeOf(previous) !== Object.prototype) return incoming;
  const old = previous as Record<string, unknown>, next = incoming as Record<string, unknown>;
  // Transport metadata can contain cycles; only the business body is shared.
  if ('config' in next && 'status' in next && 'data' in next) return { ...next, data: shareRecordReferences(old.data, next.data) };
  const keys = Object.keys(next);
  const output = Object.fromEntries(keys.map(key => [key, shareRecordReferences(old[key], next[key])]));
  return keys.length === Object.keys(old).length && keys.every(key => old[key] === output[key]) ? previous : output;
}

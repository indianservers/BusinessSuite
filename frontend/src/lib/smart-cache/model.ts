/** Versioned wire/storage model. Collections are bounded views, never full-table replicas. */
export type Row = { id?: string | number; [key: string]: unknown };
export type View = { key: string | null; rows: Row[]; meta: Record<string, unknown> };
export type Delta = { schema: number; key: string | null; order: string[]; upserts: Row[]; removed: string[]; meta: Record<string, unknown> };
export type Entry = {
  key: string; scope: string; module: string; entity: string; projection: string;
  url: string; data: unknown; etag: string; cursor: string; serverScope: string;
  checked: number; accessed: number; bytes: number; persistent: boolean;
};
export const MAX_ROWS = 500;
export const MAX_VIEWS = 100;
export const MAX_BYTES = 20 * 1024 * 1024;
export const MAX_AGE = 24 * 60 * 60 * 1000;
export const CHECK_INTERVAL = 45000;
const collection = /^(?:\/master-data\/(companies|contacts|company-directory\/query)|\/project-management\/(projects|tasks|teams|people-workspace\/people|people-workspace\/groups)|\/crm\/(leads|lead-management\/leads|contact-directory|contacts|accounts|companies|deals|deal-workspace\/(?:query|grid\/query)|customers|products|services|quotes|quotations|sales-orders)|\/srm\/(customers|products|services|sales-orders|sales|quotations|customer-360)|\/catalog\/(products|services|items)|\/profiles\/(directory)|\/(employees(?:\/directory)?|departments|teams)|\/company\/(departments|teams)|\/interns-hub\/(management\/batches|learning\/assignments)|\/attendance\/(my|team|register)|\/leave\/(requests|my|my-requests))\/?$/;
export function policy(url: string) {
  const path = url.split('?')[0];
  const match = path.match(collection);
  if (!match) return undefined;
  const resource = match.slice(1).find(Boolean)!;
  const module = path.startsWith('/project-management/') ? 'pms' : path.startsWith('/crm/') ? 'crm' : path.startsWith('/srm/') ? 'sales' : (path.startsWith('/catalog/') || path.startsWith('/profiles/') || path.startsWith('/master-data/')) ? 'shared' : 'hrms';
  if (path.startsWith("/leave/")) return { module, entity: "leave", path };
  // Aliases share invalidation; projections remain separate to preserve endpoint field permissions.
  const entity = ({ 'company-directory/query':'customer', 'contact-directory': 'contact', directory: 'person', 'people-workspace/people': 'person', 'people-workspace/groups': 'team', 'lead-management/leads': 'lead', 'deal-workspace/query': 'deal', 'deal-workspace/grid/query': 'deal', items: 'catalog', 'customer-360': 'customer', 'my-requests': 'leave', 'management/batches': 'batch', 'learning/assignments': 'assignment', companies: 'customer', accounts: 'customer', customers: 'customer', employees: 'employee', 'employees/directory': 'employee' } as Record<string, string>)[resource] || resource.replace(/s$/, '');
  return { module, entity, path };
}
export function rowId(row: Row): string | undefined {
  if (!row || typeof row !== 'object') return;
  if (!('id' in row) && 'task_id' in row && 'user_id' in row) return ['task_id', 'user_id'].every(k => ['number', 'string'].includes(typeof row[k])) ? `task:${row.task_id}:user:${row.user_id}` : undefined;
  if ('attendance_id' in row && ['number', 'string'].includes(typeof row.employee_id) && typeof row.date === 'string') return `employee:${row.employee_id}:date:${row.date}`;
  if (['product', 'service'].includes(String(row.kind)) && ['number', 'string'].includes(typeof row.id)) return `${row.kind}:${row.id}`;
  const value = row.id ?? row.userId;
  return ['number', 'string'].includes(typeof value) ? String(value) : undefined;
}
export function splitView(data: unknown): View | undefined {
  if (!data || typeof data !== 'object') return;
  const obj = data as Record<string, unknown>;
  const key = Array.isArray(data) ? null : ['items', 'results', 'records', 'rows'].find(k => Array.isArray(obj[k]));
  if (key === undefined) return;
  const rows = (key === null ? data : obj[key]) as Row[];
  if (rows.length > MAX_ROWS || rows.some(r => !r || typeof r !== 'object' || rowId(r) === undefined) || new Set(rows.map(r => rowId(r))).size !== rows.length) return;
  return { key, rows, meta: key === null ? {} : Object.fromEntries(Object.entries(obj).filter(([k]) => k !== key)) };
}
export function joinView(view: View): unknown { return view.key === null ? view.rows : { ...view.meta, [view.key]: view.rows }; }
export function applyChangedRecords(data: unknown, delta: Delta): unknown {
  const view = splitView(data);
  if (!view || delta.schema !== 1 || delta.key !== view.key || !Array.isArray(delta.order) || new Set(delta.order).size !== delta.order.length || delta.order.length > MAX_ROWS) throw new Error('Invalid sync baseline');
  const rows = new Map(view.rows.map(r => [rowId(r)!, r]));
  delta.removed.forEach(id => rows.delete(String(id)));
  delta.upserts.forEach(row => rows.set(rowId(row)!, row));
  if (delta.order.some(id => !rows.has(String(id)))) throw new Error('Incomplete sync delta');
  return joinView({ key: delta.key, rows: delta.order.map(id => rows.get(String(id))!), meta: delta.meta });
}
/** Browsers can merge a 304 into a 200 response with the cached wire body. */
export function resolveSyncPayload(mode: unknown, data: unknown, baseline?: unknown): unknown {
  if (mode === 'unchanged') {
    if (!splitView(baseline)) throw new Error('Missing sync baseline');
    return baseline;
  }
  if (mode === 'delta') return applyChangedRecords(baseline, data as Delta);
  return data;
}
export function stable(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stable).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => `${JSON.stringify(k)}:${stable(v)}`).join(',')}}`;
  return JSON.stringify(value) ?? 'null';
}
export async function hash(value: string): Promise<string> {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
  return Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, '0')).join('');
}
// Defense in depth: only server-approved, non-sensitive payloads reach IndexedDB.
const sensitiveKey = /password|token|secret|bank|iban|aadhaar|aadhar|pan_?number|passport|national_?id|ssn|tax_?id|home_?address|emergency_?contact|salary(?!_currency)|compensation|payroll|document|personal_?email|date_?of_?birth|dob(?:$|_)|medical|biometric|latitude|longitude/i;
export function containsSensitive(value: unknown): boolean {
  if (typeof value === 'string') return /(?:[?&](?:token|access_token|api_key|signature)=|X-Amz-Signature=)/i.test(value);
  if (!value || typeof value !== 'object') return false;
  return Object.entries(value).some(([key, item]) => (sensitiveKey.test(key) && item != null && item !== '' && (!Array.isArray(item) || item.length > 0)) || containsSensitive(item));
}

export function canonicalView(url: string): string {
  const [path, query] = url.split('?');
  const params = new URLSearchParams(query); params.sort();
  return `${path.replace(/\/$/, '')}?${params}`;
}

/** Maximum revalidation interval by resource; writes still require server confirmation. */
export function refreshInterval(url:string):number {
 if(url.startsWith("/attendance/"))return 15000;
 const entity=policy(url)?.entity;
 if(entity&&["quote","quotation","sales-order","sale","leave","attendance"].includes(entity))return 15000;
 if(entity&&["task","project","deal","lead"].includes(entity))return 30000;
 return CHECK_INTERVAL;
}

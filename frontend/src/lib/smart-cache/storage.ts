import { type Entry, type Row, splitView, joinView, MAX_AGE, MAX_BYTES, MAX_VIEWS, CHECK_INTERVAL, stable, hash, rowId } from './model';
const DATABASE = 'suite-record-cache-v1';
type StoredView = Omit<Entry, 'data'> & { listKey: string | null; ids: string[]; meta: Record<string, unknown>; fingerprint: string };
type StoredRow = { key: string; scope: string; data: Row };
let opening: Promise<IDBDatabase> | undefined;
function open(): Promise<IDBDatabase> {
  return opening ||= new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => {
      for (const name of ['views', 'records']) { const store = request.result.createObjectStore(name, { keyPath: 'key' }); store.createIndex('scope', 'scope'); }
    };
    request.onsuccess = () => { request.result.onversionchange = () => { request.result.close(); opening = undefined; }; resolve(request.result); };
    request.onerror = () => { opening = undefined; reject(request.error); };
    request.onblocked = () => { opening = undefined; reject(new Error('Cache database upgrade blocked')); };
  });
}
function result<T>(request: IDBRequest<T>): Promise<T> { return new Promise((resolve, reject) => { request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error); }); }
function complete(tx: IDBTransaction): Promise<void> { return new Promise((resolve, reject) => { tx.oncomplete = () => resolve(); tx.onabort = tx.onerror = () => reject(tx.error || new Error('Cache transaction failed')); }); }
const recordKey = (view: Pick<Entry, 'scope' | 'projection'>, id: string) => `${view.scope}:${view.projection}:${id}`;
export async function getCachedRecords(key: string): Promise<Entry | undefined> {
  const db = await open();
  const tx = db.transaction(['views', 'records'], 'readonly');
  const view = await result(tx.objectStore('views').get(key)) as StoredView | undefined;
  if (!view || Date.now() - view.checked > MAX_AGE) return;
  const rows = await Promise.all(view.ids.map(id => result(tx.objectStore('records').get(recordKey(view, id))) as Promise<StoredRow | undefined>));
  if (rows.some(row => !row)) return;
  const { listKey, ids: _ids, meta, fingerprint, ...entry } = view;
  const data = joinView({ key: listKey, rows: rows.map(row => row!.data), meta });
  return { ...entry, data, ...(await hash(stable(data)) !== fingerprint ? { cursor: "", etag: "", checked: Date.now() - CHECK_INTERVAL } : {}) };
}
export async function saveCachedRecords(entry: Entry): Promise<void> {
  if (!entry.persistent) return;
  const view = splitView(entry.data);
  if (!view) return;
  const fingerprint = await hash(stable(entry.data));
  const db = await open();
  const tx = db.transaction(['views', 'records'], 'readwrite');
  const done = complete(tx);
  const { data: _data, ...metadata } = entry;
  tx.objectStore('views').put({ ...metadata, listKey: view.key, ids: view.rows.map(row => rowId(row)!), meta: view.meta, fingerprint } satisfies StoredView);
  view.rows.forEach(row => tx.objectStore('records').put({ key: recordKey(entry, rowId(row)!), scope: entry.scope, data: row } satisfies StoredRow));
  // Limit persisted views and remove orphan records in the same transaction.
  const views = await result(tx.objectStore('views').getAll()) as StoredView[];
  views.sort((a, b) => b.accessed - a.accessed);
  let bytes = 0;
  const keep = new Set<string>();
  for (let i = 0; i < views.length; i++) {
    const v = views[i]; bytes += v.bytes;
    if (i >= MAX_VIEWS || bytes > MAX_BYTES || Date.now() - v.checked > MAX_AGE) tx.objectStore('views').delete(v.key);
    else v.ids.forEach(id => keep.add(recordKey(v, id)));
  }
  const cursor = tx.objectStore('records').openKeyCursor();
  cursor.onsuccess = () => { const c = cursor.result; if (c) { if (!keep.has(String(c.primaryKey))) tx.objectStore('records').delete(c.primaryKey); c.continue(); } };
  await done;
}
export async function invalidateCache(scope: string, module?: string): Promise<void> {
  const db = await open();
  const tx = db.transaction(['views', 'records'], 'readwrite');
  const done = complete(tx);
  const views = await result(tx.objectStore('views').index('scope').getAll(scope)) as StoredView[];
  for (const view of views) if (!module || view.module === module) tx.objectStore('views').delete(view.key);
  // Projection keys include module, so module clearing cannot remove another module's rows.
  const rows = tx.objectStore('records').index('scope').openCursor(scope);
  rows.onsuccess = () => { const c = rows.result; if (c) { if (!module || String(c.primaryKey).startsWith(`${scope}:${module}:`)) c.delete(); c.continue(); } };
  await done;
}
export const clearUserCache = (scope: string) => invalidateCache(scope);

export async function storageUsage(scope: string): Promise<{ bytes: number; views: number }> {
  const db = await open();
  const tx = db.transaction('views', 'readonly');
  const views = await result(tx.objectStore('views').index('scope').getAll(scope)) as StoredView[];
  return { bytes: views.reduce((sum, view) => sum + view.bytes, 0), views: views.length };
}

/** An unchanged 304 updates the view lease/cursor without rewriting every row. */
export async function refreshSnapshot(entry: Entry): Promise<void> {
  if (!entry.persistent) return;
  const db = await open();
  const tx = db.transaction('views', 'readwrite');
  const done = complete(tx);
  const store = tx.objectStore('views');
  const view = await result(store.get(entry.key)) as StoredView | undefined;
  if (view) store.put({ ...view, checked: entry.checked, accessed: entry.accessed, cursor: entry.cursor, etag: entry.etag });
  await done;
  if (!view) await saveCachedRecords(entry);
}

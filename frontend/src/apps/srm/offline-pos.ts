import { isAxiosError } from "axios";

type Snapshot<T> = { value: T; savedAt: number };
export const POS_SNAPSHOT_MAX_AGE = 24 * 60 * 60 * 1000;
export type LocalSale<Attempt, Result> = {
  key: string;
  scope: string;
  sessionId: number;
  attempt: Attempt;
  result?: Result;
  confirmedAt?: number;
  error?: string;
};

let opening: Promise<IDBDatabase> | undefined;
function database() {
  if (!opening) {
    opening = new Promise<IDBDatabase>((resolve, reject) => {
      const request = indexedDB.open("suite-pos-offline", 1);
      request.onupgradeneeded = () => {
        request.result.createObjectStore("snapshots");
        const sales = request.result.createObjectStore("sales", { keyPath: "key" });
        sales.createIndex("shift", ["scope", "sessionId"]);
        sales.createIndex("stock", ["scope", "stockAt"]);
      };
      request.onsuccess = () => {
        const db = request.result;
        db.onversionchange = () => { db.close(); opening = undefined; };
        resolve(db);
      };
      request.onerror = () => reject(request.error);
    }).catch(error => { opening = undefined; throw error; });
  }
  return opening;
}

function finished(transaction: IDBTransaction) {
  return new Promise<void>((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onabort = () => reject(transaction.error || new Error("Local storage transaction was interrupted."));
  });
}

function result<T>(request: IDBRequest<T>) {
  return new Promise<T>((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function cachedSnapshot<T>(key: string): Promise<Snapshot<T> | undefined> {
  const stored = await result((await database()).transaction("snapshots").objectStore("snapshots").get(key)) as Snapshot<T> | undefined;
  return stored && Date.now() - stored.savedAt < POS_SNAPSHOT_MAX_AGE ? stored : undefined;
}

export async function posSnapshot<T>(key: string, fetchValue: () => Promise<T>, mayFallback = () => true): Promise<Snapshot<T>> {
  if (!navigator.onLine && mayFallback()) {
    const cached = await cachedSnapshot<T>(key).catch(() => undefined);
    if (cached && mayFallback()) return cached;
  }
  const started = Date.now();
  try {
    const value = await fetchValue();
    const snapshot = { value, savedAt: started };
    try {
      const tx = (await database()).transaction("snapshots", "readwrite");
      const committed = finished(tx);
      tx.objectStore("snapshots").put(snapshot, key);
      await committed;
    } catch { /* Online reads work when local storage is unavailable. */ }
    return snapshot;
  } catch (error) {
    if (!mayFallback() || !isAxiosError(error) || error.code === "ERR_CANCELED" || error.response && error.response.status < 500) throw error;
    try {
      const stored = await cachedSnapshot<T>(key);
      if (stored && mayFallback()) return stored;
    } catch { /* Preserve the original connection error. */ }
    throw error;
  }
}

const UNSYNCED_STOCK = Number.MAX_SAFE_INTEGER;

function stockRange(scope: string, since: number) {
  return IDBKeyRange.bound([scope, since], [scope, UNSYNCED_STOCK]);
}

export async function readLocalSales<A, R>(scope: string, sessionId: number | undefined, catalogAt: number): Promise<LocalSale<A, R>[]> {
  const store = (await database()).transaction("sales").objectStore("sales");
  const shifts = store.index("shift");
  const lastShift = () => new Promise<LocalSale<A, R>[]>((resolve, reject) => {
    const request = shifts.openKeyCursor(IDBKeyRange.bound([scope, 0], [scope, Number.MAX_SAFE_INTEGER]), "prev");
    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      if (!request.result) { resolve([]); return; }
      resolve(result(shifts.getAll(request.result.key)));
    };
  });
  const [stock, shift] = await Promise.all([
    result(store.index("stock").getAll(stockRange(scope, catalogAt))),
    sessionId === undefined ? lastShift() : result(shifts.getAll([scope, sessionId])),
  ]);
  return [...new Map([...stock, ...shift].map(row => [row.key, row])).values()];
}

export async function enqueueLocalSale<A, R>(sale: LocalSale<A, R>, catalogAt: number, validate: (rows: LocalSale<A, R>[]) => void) {
  const tx = (await database()).transaction("sales", "readwrite", { durability: "strict" });
  const committed = finished(tx);
  const store = tx.objectStore("sales");
  let validationError: unknown;
  const request = store.index("stock").getAll(stockRange(sale.scope, catalogAt));
  request.onsuccess = () => {
    try {
      validate(request.result);
      store.add({ ...sale, stockAt: UNSYNCED_STOCK });
    } catch (error) {
      validationError = error;
      tx.abort();
    }
  };
  await committed.catch(error => { throw validationError || error; });
}

export async function updateLocalSale<A, R>(sale: LocalSale<A, R>) {
  const tx = (await database()).transaction("sales", "readwrite");
  const committed = finished(tx);
  const store = tx.objectStore("sales");
  const request = store.get(sale.key);
  request.onsuccess = () => {
    if (request.result && !request.result.result) store.put({ ...sale, stockAt: sale.confirmedAt ?? UNSYNCED_STOCK });
  };
  await committed;
}

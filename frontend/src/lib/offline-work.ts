import { isAxiosError } from "axios";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { syncScope } from "@/shared/record-sync/store";
import { randomUUID } from "@/lib/random-uuid";

type Row = Record<string, unknown>;
type Request = { family: string; target: string; url: string; method: "post" | "put" | "patch"; body: unknown; params?: Record<string, string>; row: Row };
type Change = Request & { id: string; scope: string; created: number; error?: string; confirmed?: boolean };
type Snapshot = {scope: string; data: unknown; savedAt: number; family?: string};
const reads = new Map<string, Promise<unknown>>();
export const offlineChangeEvent = "suite:offline-work-changed";
const snapshots = new Map<string, Snapshot>();

function remember(key: string, snapshot: Snapshot) {
  if (!snapshots.has(key) && snapshots.size >= 100) snapshots.delete(snapshots.keys().next().value!);
  snapshots.set(key, snapshot);
}
let database: Promise<IDBDatabase> | undefined;

function db() {
  database ??= new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open("suite-offline-work", 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore("reads");
      request.result.createObjectStore("changes", {keyPath: "id"}).createIndex("scope", "scope");
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  }).catch(error => { database = undefined; throw error; });
  return database;
}

function read<T>(request: IDBRequest<T>) {
  return new Promise<T>((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function write(store: "reads" | "changes", value: Snapshot | Change, key?: string) {
  const tx = (await db()).transaction(store, "readwrite", {durability: "strict"});
  await new Promise<void>((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onabort = () => reject(tx.error);
    if (key === undefined) tx.objectStore(store).put(value);
    else tx.objectStore(store).put(value, key);
  });
}

const changed = (family: string) => window.dispatchEvent(new CustomEvent(offlineChangeEvent, {detail: family}));
const owns = (scope: string) => useAuthStore.getState().isAuthenticated && syncScope() === scope;

export async function offlineRead<T>(key: string, fetchValue: () => Promise<T>, family?: string): Promise<T> {
  const scope = syncScope();
  if (!owns(scope)) return fetchValue();
  const cacheKey = JSON.stringify([scope, key]);
  const cached = snapshots.get(cacheKey) || await db().then(database => read(database.transaction("reads").objectStore("reads").get(cacheKey))).catch(() => undefined) as Snapshot | undefined;
  if (!owns(scope)) throw new Error("Workspace changed.");
  if (cached && !snapshots.has(cacheKey)) remember(cacheKey, cached);
  const refresh = () => {
    const existing = reads.get(cacheKey);
    if (existing) return existing as Promise<T>;
    const request = (async () => {
      try {
        const data = await fetchValue();
        if (!owns(scope)) throw new Error("Workspace changed.");
        const snapshot = {scope, data, savedAt: Date.now(), family};
        remember(cacheKey, snapshot);
        await write("reads", snapshot, cacheKey).catch(() => undefined);
        if (!owns(scope)) throw new Error("Workspace changed.");
        if (family && cached && JSON.stringify(cached.data) !== JSON.stringify(data) && owns(scope)) changed(family);
        return data;
      } catch (error) {
        const status = isAxiosError(error) ? error.response?.status : undefined;
        if (status === 401 || status === 403 || status === 404) {
          snapshots.delete(cacheKey);
          const tx = (await db()).transaction("reads", "readwrite");
          await read(tx.objectStore("reads").delete(cacheKey)).catch(() => undefined);
          if (family && cached && owns(scope)) changed(family);
        }
        throw error;
      }
    })().finally(() => reads.delete(cacheKey));
    reads.set(cacheKey, request);
    return request;
  };
  if (cached && (!navigator.onLine || family)) {
    if (navigator.onLine && Date.now() - (cached.savedAt || 0) > 15000) {
      void refresh().catch(() => undefined);
    }
    return cached.data as T;
  }
  if (navigator.onLine) {
    try { return await refresh(); }
    catch (error) {
      if (!cached || !owns(scope) || !isAxiosError(error) || error.code === "ERR_CANCELED" || error.response && error.response.status < 500) throw error;
    }
  }
  if (!cached) throw new Error("Open this view while connected to make it available offline.");
  return cached.data as T;
}

export async function offlineChanges(family?: string): Promise<Change[]> {
  const scope = syncScope();
  if (!owns(scope)) return [];
  const rows = await read((await db()).transaction("changes").objectStore("changes").index("scope").getAll(scope)) as Change[];
  return owns(scope) ? rows.filter(row => (!family || row.family === family)).sort((a,b) => a.created - b.created) : [];
}

export async function discardOfflineChange(id: string) {
  const scope = syncScope();
  const changes = await offlineChanges();
  const entry = changes.find(change => change.id === id && change.error);
  if (!entry || !owns(scope)) return;
  const tx = (await db()).transaction("changes", "readwrite", {durability: "strict"});
  await new Promise<void>((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onabort = () => reject(tx.error);
    tx.objectStore("changes").delete(id);
  });
  if (owns(scope)) changed(entry.family);
}

export async function saveOffline<T>(request: Request): Promise<T> {
  const scope = syncScope();
  if (!owns(scope)) throw new Error("Sign in to save changes.");
  const id = randomUUID();
  const row = {id: -(Date.now() * 1000 + Math.floor(Math.random() * 1000)), ...request.row, offline_pending: true};
  const tx = (await db()).transaction("changes", "readwrite", {durability: "strict"});
  await new Promise<void>((resolve, reject) => {
    const store = tx.objectStore("changes");
    let problem: Error | undefined;
    tx.oncomplete = () => resolve();
    tx.onabort = () => reject(problem || tx.error);
    const existing = store.index("scope").getAll(scope);
    existing.onsuccess = () => {
      if (!owns(scope) || (existing.result as Change[]).some(change => !change.confirmed && change.family === request.family && change.target === request.target)) {
        problem = new Error("A saved change for this record is already awaiting sync or review.");
        tx.abort();
      } else store.add({...request, row, id, scope, created: Date.now()});
    };
  });
  if (!owns(scope)) throw new Error("The change was saved in the original workspace.");
  changed(request.family);
  void flushOfflineWork();
  return row as T;
}

let running = false;
export async function flushOfflineWork() {
  if (running || !navigator.onLine) return;
  const scope = syncScope();
  running = true;
  try {
    const replay = async () => {
      const blocked = new Set<string>();
      for (const entry of await offlineChanges()) {
        if (!owns(scope) || !navigator.onLine) break;
        const target = JSON.stringify([entry.family, entry.target]);
        if (entry.confirmed || blocked.has(target)) continue;
        if (entry.error) { blocked.add(target); continue; }
        try {
          const {data} = await api.request({
            url: entry.url, method: entry.method, data: entry.body, params: entry.params,
            offlineScope: scope, _recordSyncBackground: true,
            headers: {"X-Offline-Operation": entry.id, "X-Suite-Tenant": sessionStorage.getItem("suite-tenant") || ""}, timeout: 12000, progress: false, recordSync: false,
          });
          const record = (data.task || data) as Row;
          await write("changes", {...entry, row: {...entry.row, ...record, offline_pending: false}, confirmed: true});
        } catch (error) {
          const status = isAxiosError(error) ? error.response?.status : undefined;
          if (!status || status >= 500 || [401, 408, 429].includes(status)) break;
          const detail = isAxiosError(error) ? error.response?.data?.detail : undefined;
          await write("changes", {...entry, error: typeof detail === "string" ? detail : "The server could not apply this change."});
          blocked.add(target);
        }
        if (owns(scope)) {
          for (const snapshot of snapshots.values()) if (snapshot.family === entry.family && snapshot.scope === scope) snapshot.savedAt = 0;
          changed(entry.family);
        }
      }
    };
    if (navigator.locks) await navigator.locks.request("suite-offline-work:" + scope, {ifAvailable: true}, lock => lock ? replay() : undefined);
    else await replay();
  } catch { /* Retain the durable queue and try again when the browser can read it. */ }
  finally { running = false; }
}

export function installOfflineWork() {
  window.addEventListener("online", () => void flushOfflineWork());
  window.addEventListener("focus", () => void flushOfflineWork());
  window.setInterval(() => void flushOfflineWork(), 5000);
}

import axios, { AxiosError, AxiosHeaders, type AxiosInstance, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { resolveSyncPayload, canonicalView, containsSensitive, hash, policy, splitView, stable, CHECK_INTERVAL, MAX_AGE, MAX_BYTES, MAX_VIEWS, type Delta, type Entry } from './model';
import * as disk from './storage';

declare module 'axios' {
  interface AxiosRequestConfig {
    /** Bypass local data for explicit refresh or endpoint-specific freshness requirements. */
    recordCache?: false;
    _recordSyncBypass?: boolean;
    _recordSyncBackground?: boolean;
  }
}
export type SyncStatus = { hits: number; misses: number; avoided: number; requests: number; updated: number; pending: number; bytes: number; lastSync: number; failures: number; error: string; health: 'idle' | 'syncing' | 'offline' | 'error'; views: number; diskBytes: number; networkRequests: number };
export type Change = { key: string; url: string; old: unknown; data: unknown; module: string; entity: string };
type Environment = { identity: () => string | null; changed: (change: Change) => void; revoked: (revalidate?: boolean) => void; used: (key: string, data: unknown) => void; active: (key: string) => boolean };
export class RecordCacheManager {
  private memory = new Map<string, Entry>();
  private flights = new Map<string, Promise<AxiosResponse>>();
  private configs = new Map<string, InternalAxiosRequestConfig>();
  private observedViews = new Map<string, number>();
  private listeners = new Set<() => void>();
  private generation = 0;
  private activeScope = '';
  private channel?: BroadcastChannel;
  private timer?: ReturnType<typeof setTimeout>;
  private failures = 0;
  private retryAt = 0;
  private stopped = false;
  private optimistic = new Set<string>();
  private lastIdentity: string | null;
  private status: SyncStatus = { hits: 0, misses: 0, avoided: 0, requests: 0, updated: 0, pending: 0, bytes: 0, lastSync: 0, failures: 0, error: '', health: 'idle', views: 0, diskBytes: 0, networkRequests: 0 };
  constructor(private api: AxiosInstance, private env: Environment) {
    this.lastIdentity = env.identity();
    const adapter = axios.getAdapter(api.defaults.adapter);
    const transport: typeof adapter = config => { this.report({ networkRequests: this.status.networkRequests + 1 }); return adapter(config); };
    api.defaults.adapter = config => config._recordSyncBypass ? transport(config) : this.read(config, transport);
    try {
      this.channel = new BroadcastChannel('suite-record-cache-v1');
      this.channel.onmessage = event => {
        const msg = event.data;
        const identity = this.env.identity(), generation = this.generation;
        if (!msg || !identity || identity !== this.lastIdentity || msg.scope !== this.activeScope) return;
        if (msg.type === 'clear') { void this.clear(false); this.env.revoked(); }
        if (msg.type === 'updated' && typeof msg.key === 'string') {
          const old = this.memory.get(msg.key);
          if (old?.persistent) void disk.getCachedRecords(msg.key).then(entry => {
            if (entry && generation === this.generation && identity === this.env.identity() && entry.scope === this.activeScope) { this.memory.set(entry.key, entry); if (stable(old.data) !== stable(entry.data)) this.env.changed({ key: old.key, url: old.url, old: old.data, data: entry.data, module: entry.module, entity: entry.entity }); }
          }).catch(() => undefined);
        }
      };
    } catch { /* Storage and broadcast APIs are optional. */ }
    window.addEventListener('online', this.wake);
    document.addEventListener('visibilitychange', this.wake);
    window.addEventListener('focus', this.wake);
    this.schedule();
  }
  observeView(view: string) {
    const key = canonicalView(view);
    this.observedViews.set(key, (this.observedViews.get(key) || 0) + 1);
    return () => { const count = (this.observedViews.get(key) || 1) - 1; if (count) this.observedViews.set(key, count); else this.observedViews.delete(key); };
  }
  private isActive(entry: Entry) { return this.env.active(entry.key) || this.observedViews.has(canonicalView(entry.url)); }
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  getSyncStatus = () => this.status;
  private report(patch: Partial<SyncStatus> = {}) {
    this.status = { ...this.status, ...patch, views: this.memory.size, bytes: [...this.memory.values()].reduce((sum, e) => sum + e.bytes, 0) };
    this.listeners.forEach(fn => fn());
  }
  private wake = () => { if (document.visibilityState === 'visible' && navigator.onLine) { this.retryAt = 0; void this.syncModuleChanges(); } };
  private schedule() {
    if (this.stopped) return;
    this.timer = setTimeout(async () => {
      if (document.visibilityState === 'visible' && navigator.onLine) await this.syncModuleChanges();
      this.schedule();
    }, Math.min(300000, CHECK_INTERVAL * 2 ** Math.min(this.failures, 3)) + Math.random() * 3000);
  }
  dispose() { this.stopped = true; clearTimeout(this.timer); this.channel?.close(); window.removeEventListener('online', this.wake); window.removeEventListener('focus', this.wake); document.removeEventListener('visibilitychange', this.wake); }
  contextChanged() {
    const next = this.env.identity();
    if (next !== this.lastIdentity) { this.lastIdentity = next; const hadScope = Boolean(this.activeScope); void this.clear(); if (hadScope) this.env.revoked(); }
  }
  async clear(broadcast = true, module?: string) {
    const scope = this.activeScope;
    if (!module) this.activeScope = '';
    ++this.generation;
    for (const [key, entry] of this.memory) if (!module || entry.module === module) { this.memory.delete(key); this.configs.delete(key); }
    this.flights.clear();
    if (broadcast && scope) this.channel?.postMessage({ type: 'clear', scope });
    this.report();
    if (scope) await disk.invalidateCache(scope, module).catch(() => undefined);
    this.report({ diskBytes: (await disk.storageUsage(scope).catch(() => ({ bytes: 0 }))).bytes });
  }
  async clearUserCache() { await this.clear(); }
  async invalidateCache(module?: string) { await this.clear(true, module); }
  async getCachedRecord(entity: string, id: string | number) {
    const entries = [...this.memory.values()].filter(e => e.scope === this.activeScope && e.entity === entity);
    return entries.flatMap(e => splitView(e.data)?.rows || []).find(row => String(row.id) === String(id));
  }
  private rememberConfig(key: string, config: InternalAxiosRequestConfig) {
    // Never keep bearer tokens, cookies, request IDs, abort signals or progress closures in the cache.
    const headers = new AxiosHeaders();
    for (const name of ['X-Suite-Organization', 'X-Suite-Branch']) if (config.headers.has(name)) headers.set(name, config.headers.get(name));
    this.configs.set(key, { url: config.url, params: config.params, baseURL: config.baseURL, method: 'get', headers, timeout: config.timeout, responseType: 'json' } as InternalAxiosRequestConfig);
  }
  private async read(config: InternalAxiosRequestConfig, fallback: ReturnType<typeof axios.getAdapter>): Promise<AxiosResponse> {
    this.contextChanged();
    const info = policy(config.url || '');
    const identity = this.env.identity();
    if (config.recordCache === false || (config.method || 'get') !== 'get' || !info || !identity || !crypto.subtle || config.responseType && config.responseType !== 'json' || /^https?:/.test(config.url || '')) return fallback(config);
    const generation = this.generation;
    const scope = await hash(stable([this.api.defaults.baseURL, identity]));
    if (generation !== this.generation || identity !== this.env.identity()) throw new axios.CanceledError('Cache context changed');
    this.activeScope = scope;
    const url = this.api.getUri(config).replace(config.baseURL || '', '');
    if ([...new URL(url, location.origin).searchParams.keys()].some(name => /token|password|secret|signature|api_key/i.test(name))) return fallback(config);
    const key = `${scope}:${await hash(url)}`;
    const customOrg = String(config.headers.get('X-Suite-Organization') || '');
    const customBranch = String(config.headers.get('X-Suite-Branch') || '');
    if (customOrg !== (sessionStorage.getItem('suite-organization') || '') || customBranch !== (sessionStorage.getItem('suite-branch') || '')) return fallback(config);
    let entry = this.memory.get(key);
    if (!entry) entry = await disk.getCachedRecords(key).catch(() => undefined);
    if (generation !== this.generation || identity !== this.env.identity()) throw new axios.CanceledError('Cache context changed');
    if (entry && entry.scope === scope && Date.now() - entry.checked <= MAX_AGE) {
      if (!this.status.diskBytes) void disk.storageUsage(scope).then(usage => { if (scope === this.activeScope) this.report({ diskBytes: usage.bytes }); }).catch(() => undefined);
      this.memory.set(key, entry); this.rememberConfig(key, config); this.env.used(key, entry.data); entry.accessed = Date.now();
      const force = config.recordCache === false || Boolean(config._finishPageRefresh);
      const check = navigator.onLine && Date.now() >= this.retryAt && Date.now() - entry.checked >= CHECK_INTERVAL;
      this.report({ hits: this.status.hits + 1, avoided: this.status.avoided + ((!force && !check || !navigator.onLine) ? 1 : 0) });
      if (force && navigator.onLine) return this.fetch(key, scope, config, entry, generation);
      if (check) void this.fetch(key, scope, config, entry, generation).catch(() => undefined);
      return { data: entry.data, status: 200, statusText: 'OK', headers: new AxiosHeaders({ 'X-Suite-Local-Cache': 'hit' }), config };
    }
    this.report({ misses: this.status.misses + 1 });
    return this.fetch(key, scope, config, undefined, generation);
  }
  private fetch(key: string, scope: string, config: InternalAxiosRequestConfig, old: Entry | undefined, generation: number): Promise<AxiosResponse> {
    const existing = this.flights.get(key);
    if (existing) { this.report({ avoided: this.status.avoided + 1 }); return existing.then(response => ({ ...response, config })); }
    const run = async (): Promise<AxiosResponse> => {
      if (generation !== this.generation || scope !== this.activeScope || !this.env.identity()) throw new axios.CanceledError('Cache context changed');
      // Re-read inside a cross-tab lock: the preceding tab may have just synchronized.
      const shared = await disk.getCachedRecords(key).catch(() => undefined);
      if (generation !== this.generation || scope !== this.activeScope || !this.env.identity()) throw new axios.CanceledError('Cache context changed');
      if (shared && shared.checked > (old?.checked || 0) && Date.now() - shared.checked < CHECK_INTERVAL && config.recordCache !== false && !config._finishPageRefresh) {
        this.memory.set(key, shared); this.env.used(key, shared.data);
        if (old && stable(old.data) !== stable(shared.data)) this.env.changed({ key: old.key, url: old.url, old: old.data, data: shared.data, module: shared.module, entity: shared.entity });
        this.report({ avoided: this.status.avoided + 1 });
        return { data: shared.data, status: 200, statusText: 'OK', headers: new AxiosHeaders(), config };
      }
      const headers = new AxiosHeaders(config.headers);
      headers.set('X-Suite-Sync', '1');
      if (old?.cursor) { headers.set('X-Suite-Sync-Cursor', old.cursor); headers.set('If-None-Match', old.etag); }
      else { headers.delete('X-Suite-Sync-Cursor'); headers.delete('If-None-Match'); }
      this.report({ requests: this.status.requests + 1, pending: this.status.pending + 1, health: 'syncing' });
      try {
        let response = await this.api.request({ ...config, headers, signal: undefined, _recordSyncBypass: true, _recordSyncBackground: Boolean(old), progress: old ? false : config.progress, _finishProgress: undefined, _finishPageRefresh: undefined, validateStatus: status => status === 304 || status >= 200 && status < 300 });
        if (generation !== this.generation || scope !== this.activeScope || !this.env.identity()) throw new axios.CanceledError('Cache context changed');
        let mode = response.headers['x-suite-sync-mode'];
        let data = response.data;
        try { data = resolveSyncPayload(mode, data, old?.data); }
        catch {
          headers.delete('If-None-Match'); headers.delete('X-Suite-Sync-Cursor');
          this.report({ requests: this.status.requests + 1 });
          response = await this.api.request({ ...config, headers, signal: undefined, _recordSyncBypass: true, _recordSyncBackground: true, progress: false, _finishProgress: undefined, _finishPageRefresh: undefined });
          if (generation !== this.generation || scope !== this.activeScope || !this.env.identity()) throw new axios.CanceledError('Cache context changed');
          mode = response.headers['x-suite-sync-mode'];
          if (mode !== 'full') throw new Error('Server could not reset the sync baseline');
          data = response.data;
        }
        const info = policy(config.url || '')!;
        const approved = ['persist', 'memory'].includes(response.headers['x-suite-cache']) && !String(response.headers['cache-control'] || '').includes('no-store') && splitView(data) && !containsSensitive(data);
        if (!approved) {
          if (old) { await this.clear(); this.env.revoked(); }
          return { ...response, config, data, status: 200 };
        }
        const serverScope = String(response.headers['x-suite-sync-scope'] || '');
        if ((old?.serverScope || [...this.memory.values()].find(e => e.scope === scope)?.serverScope) && (old?.serverScope || [...this.memory.values()].find(e => e.scope === scope)?.serverScope) !== serverScope) {
          await this.clear(); this.env.revoked();
          throw new axios.CanceledError('Authorization scope changed; reload authorized views');
        }
        const entry: Entry = { key, scope, ...info, projection: `${info.module}:${await hash(info.path + serverScope + (new URL(this.api.getUri(config), location.origin).searchParams.get('source') || '') + stable(Object.keys(splitView(data)!.rows[0] || {}).sort()))}`, url: this.api.getUri(config).replace(config.baseURL || '', ''), data, etag: String(response.headers.etag || ''), cursor: String(response.headers['x-suite-sync-cursor'] || ''), serverScope, checked: Date.now(), accessed: Date.now(), bytes: new TextEncoder().encode(JSON.stringify(data)).length, persistent: response.headers['x-suite-cache'] === 'persist' };
        // Do not persist oversized or expired entries, and keep memory bounded too.
        this.memory.delete(key); this.memory.set(key, entry); this.rememberConfig(key, config); this.env.used(key, data);
        while (this.memory.size > MAX_VIEWS || [...this.memory.values()].reduce((n, e) => n + e.bytes, 0) > MAX_BYTES) { const oldest = this.memory.keys().next().value!; this.memory.delete(oldest); this.configs.delete(oldest); }
        await (mode === 'unchanged' ? disk.refreshSnapshot(entry) : disk.saveCachedRecords(entry)).catch(() => undefined);
        const usage = await disk.storageUsage(scope).catch(() => ({ bytes: 0 })); this.report({ diskBytes: usage.bytes });
        if (generation !== this.generation) { await disk.clearUserCache(scope).catch(() => undefined); throw new axios.CanceledError('Cache context changed'); }
        this.channel?.postMessage({ type: 'updated', key, scope });
        if (old && stable(old.data) !== stable(data)) {
          this.env.changed({ key: old.key, url: old.url, old: old.data, data, module: info.module, entity: info.entity });
          this.report({ updated: this.status.updated + (mode === 'delta' ? (response.data as Delta).upserts.length + (response.data as Delta).removed.length : splitView(data)!.rows.length) });
        }
        this.failures = 0; this.retryAt = 0;
        this.report({ lastSync: Date.now(), error: '', health: 'idle' });
        return { ...response, status: 200, statusText: 'OK', config, data };
      } catch (error) {
        const status = (error as AxiosError).response?.status;
        if (status === 401 || status === 403) { await this.clear(); this.env.revoked(false); }
        if (!axios.isCancel(error)) { this.failures++; this.retryAt = Date.now() + Math.min(300000, CHECK_INTERVAL * 2 ** Math.min(this.failures, 3)); this.report({ failures: this.status.failures + 1, health: navigator.onLine ? 'error' : 'offline', error: status ? `Synchronization failed (HTTP ${status})` : 'Synchronization unavailable; retrying when connected' }); }
        throw error;
      } finally { this.report({ pending: Math.max(0, this.status.pending - 1) }); }
    };
    const promise: Promise<AxiosResponse> = Promise.resolve(navigator.locks ? navigator.locks.request(`suite-cache:${key}`, run) : run()).then(async response => await response).finally(() => { if (this.flights.get(key) === promise) this.flights.delete(key); });
    this.flights.set(key, promise);
    return promise;
  }
  async syncModuleChanges(module?: string, force = false) {
    this.contextChanged();
    if (!navigator.onLine) { this.report({ health: 'offline' }); return; }
    if (!force && Date.now() < this.retryAt) return;
    // Only views used in the last two minutes; never enumerate or preload a table.
    const entries = [...this.memory.values()].filter(e => !this.optimistic.has(e.entity) && (!module || e.module === module) && (this.isActive(e) || Date.now() - e.accessed < 120000) && (force || Date.now() - e.checked >= CHECK_INTERVAL));
    // Bound concurrency and let the per-view Web Lock deduplicate other tabs.
    for (let i = 0; i < entries.length; i += 4) await Promise.allSettled(entries.slice(i, i + 4).map(e => {
      const config = this.configs.get(e.key);
      return config ? this.fetch(e.key, e.scope, force ? { ...config, recordCache: false } : config, e, this.generation) : Promise.resolve();
    }));
  }
  /** Only low-risk lead contact edits with the existing server-enforced version check. */
  async optimisticEdit<T extends AxiosResponse>(entity: string, id: number, patch: Record<string, unknown>, version: number | undefined, request: () => Promise<T>, details: Record<string, unknown> = {}): Promise<T> {
    const safe = new Set(['full_name', 'email', 'phone', 'phone_country_code', 'job_title', 'company_name']);
    const generation = this.generation;
    const row = await this.getCachedRecord(entity, id);
    if (generation !== this.generation || !this.env.identity()) throw new axios.CanceledError('Cache context changed');
    if (!navigator.onLine || entity !== 'lead' || !row || row.version !== version || !Object.keys(patch).length || Object.keys(patch).some(k => !safe.has(k)) || Object.entries(details).some(([key, value]) => stable((row.details as Record<string, unknown> | undefined)?.[key]) !== stable(value))) return request();
    if (this.optimistic.has(entity)) throw new Error('Another contact edit is still saving. Wait for it to finish.');
    const previous = new Map<string, unknown>();
    this.optimistic.add(entity);
    const apply = (entry: Entry, values: Record<string, unknown>) => {
      const view = splitView(entry.data);
      if (!view || entry.entity !== entity || !view.rows.some(r => String(r.id) === String(id))) return;
      const old = entry.data;
      const rows = view.rows.map(r => String(r.id) === String(id) ? { ...r, ...Object.fromEntries(Object.entries(values).filter(([key]) => key in r)) } : r);
      entry.data = view.key === null ? rows : { ...view.meta, [view.key]: rows };
      this.env.used(entry.key, entry.data);
      this.env.changed({ key: entry.key, url: entry.url, old, data: entry.data, module: entry.module, entity });
    };
    for (const entry of this.memory.values()) if (entry.entity === entity) { previous.set(entry.key, entry.data); apply(entry, patch); }
    try {
      const response = await request();
      if (generation === this.generation) for (const entry of this.memory.values()) if (entry.entity === entity) {
        apply(entry, response.data); entry.checked = 0; entry.cursor = ''; entry.etag = '';
      }
      return response;
    } catch (error) {
      if (generation === this.generation) for (const [key, data] of previous) {
        const entry = this.memory.get(key);
        if (entry) { const old = entry.data; entry.data = data; this.env.used(key, data); this.env.changed({ key, url: entry.url, old, data, module: entry.module, entity }); }
      }
      throw error;
    } finally { this.optimistic.delete(entity); void this.syncModuleChanges(); }
  }
  async afterMutation(url: string) {
    const generation = this.generation;
    const path = (url || "").replace(/\/[^/]+$/, '');
    const masterPath = (url || "").split("?")[0];
    const masterEntity = /^\/master-data\/(?:companies|company|company-directory)(?:\/|$)/.test(masterPath) ? "customer" : /^\/master-data\/contact(?:\/|$)/.test(masterPath) ? "contact" : undefined;
    const affected = masterEntity ? {entity:masterEntity,module:"shared"} : policy(path) || policy(url || "");
    const related = new Set(affected?.entity === 'employee' ? ['employee', 'person', 'assignment', 'team'] : affected?.entity === 'customer' ? ['customer', 'contact', 'lead', 'deal'] : affected?.entity === 'product' || affected?.entity === 'service' || affected?.entity === 'catalog' ? ['product', 'service', 'catalog', 'deal'] : affected?.entity === 'contact' ? ['contact','customer','lead'] : affected ? [affected.entity] : []);
    const entries = [...this.memory.values()].filter(entry => !affected || related.has(entry.entity) || entry.module === affected.module);
    // Persist the stale marker so another tab cannot mistake a pre-edit snapshot for a fresh result.
    for (const entry of entries) {
      if (generation !== this.generation) return;
      entry.checked = Date.now() - CHECK_INTERVAL; await disk.saveCachedRecords(entry).catch(() => undefined);
      if (generation !== this.generation) { await disk.clearUserCache(entry.scope).catch(() => undefined); return; }
    }
    for (let i = 0; i < entries.length; i += 4) await Promise.allSettled(entries.slice(i, i + 4).filter(entry => !this.optimistic.has(entry.entity) && (this.isActive(entry) || Date.now() - entry.accessed < 120000)).map(entry => {
      const config = this.configs.get(entry.key);
      return config ? this.fetch(entry.key, entry.scope, { ...config, recordCache: false }, entry, generation) : Promise.resolve();
    }));
  }
}

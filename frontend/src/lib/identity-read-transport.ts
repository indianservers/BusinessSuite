import {AxiosError, CanceledError, isAxiosError, type AxiosAdapter, type AxiosResponse, type InternalAxiosRequestConfig} from 'axios';

const identityReads = new Set(['/auth/me', '/access/me', '/branches/context', '/access/setup']);

type SharedRead = {promise: Promise<AxiosResponse>; controller: AbortController; readers: number; settled: boolean};

/** Share in-flight identity reads, never settled permissions. Subscribers cancel independently. */
export function identityReadTransport(transport: AxiosAdapter, uri: (config: InternalAxiosRequestConfig) => string): AxiosAdapter {
  const active = new Map<string, SharedRead>();
  return async config => {
    if ((config.method || 'get').toLowerCase() !== 'get' || !identityReads.has((config.url || '').split('?')[0])
        || config.cancelToken || config.onDownloadProgress || config.onUploadProgress) return transport(config);
    if (config.signal?.aborted) throw new CanceledError('canceled', config);
    const headers = Object.entries(config.headers.toJSON())
      .filter(([name]) => name.toLowerCase() !== 'x-request-id')
      .map(([name, value]) => [name.toLowerCase(), value])
      .sort(([a], [b]) => String(a).localeCompare(String(b)));
    // Includes authorization, company, branch, tenant, pack and expected realm.
    // The key exists in memory only until this one request settles.
    const key = JSON.stringify([uri(config), headers, config.timeout, config.responseType, config.withCredentials]);
    let pending = active.get(key);
    if (!pending) {
      if (active.size >= 32) return transport(config);
      const controller = new AbortController();
      pending = {controller, readers: 0, settled: false, promise: undefined!};
      const created = pending;
      created.promise = Promise.resolve().then(() => transport({...config, signal: controller.signal})).finally(() => {
        created.settled = true;
        if (active.get(key) === created) active.delete(key);
      });
      active.set(key, pending);
    }
    const read = pending;
    read.readers++;
    return new Promise<AxiosResponse>((resolve, reject) => {
      let finished = false;
      const release = () => {
        if (finished) return false;
        finished = true;
        config.signal?.removeEventListener?.('abort', cancel);
        read.readers--;
        if (!read.readers && !read.settled) {
          if (active.get(key) === read) active.delete(key);
          read.controller.abort();
        }
        return true;
      };
      const cancel = () => { if (release()) reject(new CanceledError('canceled', config)); };
      config.signal?.addEventListener?.('abort', cancel);
      if (config.signal?.aborted) cancel();
      read.promise.then(response => {
        if (release()) resolve({...response, config});
      }, error => {
        if (!release()) return;
        reject(isAxiosError(error) ? AxiosError.from(error, error.code, config, error.request,
          error.response ? {...error.response, config} : undefined) : error);
      });
    });
  };
}

import {AxiosError, isAxiosError, type AxiosAdapter, type AxiosResponse, type InternalAxiosRequestConfig} from 'axios';

const identityReads = new Set(['/auth/me', '/access/me', '/branches/context', '/access/setup']);

/** Share only identical requests that are still on the wire; never cache identity. */
export function identityReadTransport(transport: AxiosAdapter, uri: (config: InternalAxiosRequestConfig) => string): AxiosAdapter {
  const active = new Map<string, Promise<AxiosResponse>>();
  return async config => {
    if ((config.method || 'get').toLowerCase() !== 'get' || !identityReads.has((config.url || '').split('?')[0])
        || config.signal || config.cancelToken) return transport(config);
    const headers = Object.entries(config.headers.toJSON())
      .filter(([name]) => name.toLowerCase() !== 'x-request-id')
      .map(([name, value]) => [name.toLowerCase(), value])
      .sort(([a], [b]) => String(a).localeCompare(String(b)));
    // Includes authorization, company, branch, tenant, pack and expected realm.
    // The key exists in memory only until this one request settles.
    const key = JSON.stringify([uri(config), headers]);
    let pending = active.get(key);
    if (!pending) {
      if (active.size >= 32) return transport(config);
      pending = Promise.resolve().then(() => transport(config)).finally(() => active.delete(key));
      active.set(key, pending);
    }
    try {
      const response = await pending;
      // Each consumer retains its own progress, scope and interceptor state.
      return {...response, config};
    } catch (error) {
      if (isAxiosError(error)) throw AxiosError.from(error, error.code, config, error.request,
        error.response ? {...error.response, config} : undefined);
      throw error;
    }
  };
}

import { beginProgress } from "../../src/lib/async-progress";
import { apiBaseUrl } from "./config";
import { applicationToken } from "./applicationSession";
export const API = apiBaseUrl;
const KEY = "internhub.session";
const REFRESH_KEY = "internhub.refresh";
let refreshing: Promise<boolean> | null = null;
export class FieldValidationError extends Error { constructor(message:string,public fields:Record<string,string>){super(message);} }
export function token() {
  return sessionStorage.getItem(KEY);
}
export function setToken(value: string | null, refresh?: string) {
  if (value) {
    sessionStorage.setItem(KEY, value);
    if (refresh) sessionStorage.setItem(REFRESH_KEY, refresh);
  } else {
    sessionStorage.removeItem(KEY);
    sessionStorage.removeItem(REFRESH_KEY);
  }
}
async function refreshSession() {
  const value = sessionStorage.getItem(REFRESH_KEY);
  if (!value) return false;
  try {
    const response = await fetch(`${API}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: value }),
    });
    if (!response.ok) return false;
    const result = await response.json();
    setToken(result.access_token, result.refresh_token);
    return true;
  } catch {
    return false;
  }
}
async function performRequest<T = any>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const sessionRequest =
    !path.startsWith("/auth/") &&
    !path.startsWith("/interns-hub/applications") &&
    path !== "/interns-hub/application-options";
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...(token() ? { Authorization: `Bearer ${token()}` } : {}),
      ...(applicationToken() ? { "X-Intern-Application-Token": applicationToken()! } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    if(response.status === 401 && ["/interns-hub/application-options","/interns-hub/application-uploads","/interns-hub/applications","/interns-hub/applications/corrections"].includes(path)) {
      window.dispatchEvent(new Event("internhub:applicant-expired"));
    }
    if (response.status === 401 && sessionRequest && retry && token()) {
      if (!refreshing)
        refreshing = refreshSession().finally(() => {
          refreshing = null;
        });
      if (await refreshing) return request<T>(path, options, false);
    }
    const body = await response.json().catch(() => ({}));
    if (response.status === 401 && sessionRequest && token()) {
      setToken(null);
      window.dispatchEvent(new Event("internhub:expired"));
    }
    if(Array.isArray(body.detail))throw new FieldValidationError('Please correct the highlighted fields.',Object.fromEntries(body.detail.map((item:any)=>[String(item.loc?.at(-1)||''),String(item.msg).replace(/^Value error, /,'')])));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : Array.isArray(body.detail)
          ? body.detail.map((d: any) => d.msg).join("; ")
          : response.status >= 500
            ? "The HRMS service is unavailable. Please try again."
            : "Please check the fields and try again.",
    );
  }
  return response.json();
}
export async function request<T = any>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  const finish = beginProgress(options.method && options.method !== "GET" ? "Processing your request" : "Loading page data");
  try {
    const result = await performRequest<T>(path, options, retry);
    finish();
    return result;
  } catch (error) {
    finish(false, error instanceof Error ? error.message : "Request failed");
    throw error;
  }
}
export const hub = <T = any>(path: string, options: RequestInit = {}) =>
  request<T>(`/interns-hub${path}`, options);
export const send = (method: string, body?: unknown): RequestInit => ({
  method,
  ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
});
async function performDownload(path: string, filename: string) {
  const response = await fetch(`${API}/interns-hub${path}`, {
    headers: { Authorization: `Bearer ${token()}` },
  });
  if (!response.ok) throw new Error("Download unavailable");
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function download(path: string, filename: string) {
  const finish = beginProgress("Downloading file");
  try { await performDownload(path, filename); finish(); }
  catch (error) { finish(false, "Download unavailable. Please try again."); throw error; }
}

export async function downloadApplicationReceipt(accessToken: string, reference: string) {
  const response = await fetch(`${API}/interns-hub/applications/receipt`, {
    headers: { Authorization: `Bearer ${accessToken}` }, cache: "no-store",
  });
  if (!response.ok) throw new Error("Receipt unavailable. Check your application status again and retry.");
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${reference}-receipt.pdf`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

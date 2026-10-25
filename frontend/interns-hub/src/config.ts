declare global {
  interface Window {
    __INTERNHUB_CONFIG__?: { apiBaseUrl?: string; hrmsLoginUrl?: string };
  }
}
const runtime = window.__INTERNHUB_CONFIG__ || {};
export const apiBaseUrl = (
  runtime.apiBaseUrl ||
  import.meta.env.VITE_API_BASE_URL ||
  "/api/v1"
).replace(/\/$/, "");
export const hrmsLoginUrl =
  runtime.hrmsLoginUrl ||
  import.meta.env.VITE_HRMS_URL ||
  (import.meta.env.DEV ? "http://localhost:5173/hrms/login" : "");

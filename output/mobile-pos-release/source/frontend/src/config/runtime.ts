type RuntimeConfig = {
  apiBaseUrl?: string;
  uploadsBaseUrl?: string;
};

declare global {
  interface Window {
    __AI_HRMS_CONFIG__?: RuntimeConfig;
  }
}

function cleanUrl(value?: string | null): string | undefined {
  const trimmed = value?.trim();
  if (!trimmed) return undefined;
  return trimmed.replace(/\/+$/, "");
}

export function getApiBaseUrl(): string {
  return (
    cleanUrl(window.__AI_HRMS_CONFIG__?.apiBaseUrl) ||
    cleanUrl(import.meta.env.VITE_API_BASE_URL) ||
    cleanUrl(import.meta.env.VITE_API_URL) ||
    "/api/v1"
  );
}

export function getUploadsBaseUrl(): string {
  const configuredUploads = cleanUrl(window.__AI_HRMS_CONFIG__?.uploadsBaseUrl);
  if (configuredUploads) return configuredUploads;

  const apiBaseUrl = getApiBaseUrl();
  if (apiBaseUrl.startsWith("http")) {
    return apiBaseUrl.replace(/\/api\/v\d+$/, "");
  }
  return "";
}

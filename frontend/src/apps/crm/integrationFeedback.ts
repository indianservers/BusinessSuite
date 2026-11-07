export function integrationError(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.flatMap(item => typeof item?.msg === "string" ? [item.msg] : []);
    if (messages.length) return messages.join(". ");
  }
  return fallback;
}

export function webhookValidation(draft: { name: string; url: string; events: string[] }): string | undefined {
  if (!draft.name.trim()) return "Enter a webhook name.";
  try {
    const url = new URL(draft.url.trim());
    if (!["http:", "https:"].includes(url.protocol) || !url.hostname || url.username || url.password) return "Enter an HTTP or HTTPS endpoint URL without embedded credentials.";
  } catch { return "Enter a valid HTTP or HTTPS endpoint URL."; }
  if (!draft.events.length) return "Select at least one webhook event.";
}

/** Remove one-use provider credentials while retaining the selected workspace tab. */
export function calendarReturnSearch(search: string): string {
  const params = new URLSearchParams(search);
  for (const key of ["code", "state", "error", "error_description", "error_uri", "session_state"]) params.delete(key);
  const remaining = params.toString();
  return remaining ? `?${remaining}` : "";
}

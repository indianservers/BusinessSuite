export function taskDraftId() {
  // Web Crypto exposes getRandomValues on HTTP LAN origins.
  const bytes = crypto.getRandomValues(new Uint8Array(6));
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 11)}`;
}

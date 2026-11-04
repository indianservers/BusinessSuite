import type { CSSProperties } from "react";

export const isPhoneField = (key: string) => /^(?:(?:primary|secondary|alternate|emergency|emergency_contact|contact|business|work|personal)[_-]?)?(?:phone|mobile|telephone|whatsapp)(?:[_-]?(?:number|no))?$/i.test(key) || /^(?:emergency_contact_number|contact_number|emergency_contact)$/i.test(key);

export function phoneCountryCode(record: unknown, field = "phone"): string {
  if (!record || typeof record !== "object") return "";
  const row = record as Record<string, unknown>;
  return String(row[`${field}_country_code`] || row[`${field}CountryCode`] || row.phone_country_code || row.phoneCountryCode || row.countryCode || "");
}

export function phoneLinks(value: unknown, countryCode = "") {
  const display = typeof value === "string" || typeof value === "number" ? String(value).trim() : "";
  // Masked, missing and descriptive values must never become contact links.
  if (!/^(?:\+|00)?[\d\s().-]+$/.test(display)) return null;
  const compact = display.replace(/[\s().-]/g, "").replace(/^00/, "+");
  const code = /^\+?\d{1,4}$/.test(countryCode.trim()) ? `+${countryCode.replace(/\D/g, "")}` : "";
  const full = compact.startsWith("+") ? compact : code ? `${code}${compact.replace(/^0+/, "")}` : compact;
  const digits = full.replace(/\D/g, "");
  if (digits.length < 7 || digits.length > 15 || (full.startsWith("+") && digits.startsWith("0"))) return null;
  return { display: code && !compact.startsWith("+") ? `${code} ${display}` : display, call: `tel:${full}`, whatsapp: full.startsWith("+") ? `https://wa.me/${digits}` : undefined };
}

const linkStyle: CSSProperties = { display: "inline-flex", alignItems: "center", minHeight: 32, borderRadius: 4 };

/** Native links work on mobile and desktop without sending a message automatically. */
export default function PhoneActions({ value, countryCode, record, field = "phone", fallback = "—", blocked = false }: { value: unknown; countryCode?: string; record?: unknown; field?: string; fallback?: string; blocked?: boolean }) {
  const row = (record || {}) as Record<string, unknown>;
  const unavailable = blocked || row.contact_masked === true || /^(do not contact|blocked|inactive)$/i.test(String(row.status || ""));
  const links = unavailable ? null : phoneLinks(value, countryCode ?? phoneCountryCode(record, field));
  if (!links) return <>{typeof value === "string" || typeof value === "number" ? value || fallback : fallback}</>;
  return <span data-phone-actions="true" style={{ display: "inline-flex", alignItems: "center", gap: 6, whiteSpace: "nowrap", maxWidth: "100%" }} onClick={event => event.stopPropagation()} onDoubleClick={event => event.stopPropagation()} onPointerDown={event => event.stopPropagation()} onKeyDown={event => event.stopPropagation()}>
    <a href={links.call} style={{ ...linkStyle, textDecoration: "underline", textUnderlineOffset: 3 }} aria-label={`Call ${links.display}`} title={`Call ${links.display}`}>{links.display}</a>
    {links.whatsapp && <a href={links.whatsapp} target="_blank" rel="noopener noreferrer" style={{ ...linkStyle, justifyContent: "center", minWidth: 32, color: "#15803d" }} aria-label={`WhatsApp ${links.display}`} title={`Message ${links.display} on WhatsApp`}><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M21 11.5a9 9 0 0 1-13.4 7.9L3 21l1.6-4.6A9 9 0 1 1 21 11.5Z"/><path d="M8 7.5c-.8 3.8 2.7 7.3 6.5 8l1.5-2-2.5-1.3-1 1c-1.5-.6-2.6-1.7-3.2-3.2l1-1L9 6.5Z"/></svg></a>}
  </span>;
}

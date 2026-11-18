/** Location aliases used by CRM and employee address records. */
export const locationFields = [
  {id:"state",label:"State",keys:["state","state_name","present_state","permanent_state"]},
  {id:"city",label:"City",keys:["city","city_name","present_city","permanent_city"]},
  {id:"pincode",label:"PIN code",keys:["pincode","pin_code","postal_code","postalCode","zip_code","zip","present_pincode","permanent_pincode"]},
  {id:"country",label:"Country",keys:["country","country_name","present_country","permanent_country"]},
] as const;
export function locationValue(item: unknown, field: typeof locationFields[number]): string {
  if (!item || typeof item !== "object") return "";
  const row = item as Record<string, unknown>;
  const sources = [row, row.details, row.address, row.billing_address, row.billingAddress, row.shipping_address, row.shippingAddress, ...(Array.isArray(row.addresses) ? row.addresses.slice(0,1) : [])];
  for (const source of sources) {
    if (!source || typeof source !== "object") continue;
    for (const key of field.keys) {
      const value = (source as Record<string, unknown>)[key];
      if ((typeof value === "string" || typeof value === "number") && String(value).trim()) return String(value).trim();
    }
  }
  return "";
}

/** Match address fields exactly so workflow state and country calling codes stay put. */
export function isLocationField(label: string): boolean {
  return /^(?:(?:billing|shipping|present|permanent)\s+)?(?:city|country|state(?:\s*\/\s*region)?|region|pin\s*code|postal\s*code|zip(?:\s*code)?)(?:\s*\*)?$/i.test(label.trim().replace(/_/g, " "));
}
export function locationLast<T>(items: T[], label: (item: T) => string): T[] {
  return [...items.filter(item => !isLocationField(label(item))), ...items.filter(item => isLocationField(label(item)))];
}

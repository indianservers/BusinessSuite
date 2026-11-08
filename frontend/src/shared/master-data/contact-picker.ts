export type ContactPickerOption = { id: number; name: string; email?: string | null };

export function contactPickerResponse(value: unknown): { items: ContactPickerOption[] } {
  if (!value || typeof value !== "object" || !Array.isArray((value as { items?: unknown }).items)) {
    throw new Error("Contact persons could not be loaded. Try again.");
  }
  const items = (value as { items: unknown[] }).items;
  if (items.some(item => !item || typeof item !== "object" ||
    !Number.isSafeInteger((item as ContactPickerOption).id) || (item as ContactPickerOption).id <= 0 ||
    typeof (item as ContactPickerOption).name !== "string" ||
    ((item as ContactPickerOption).email != null && typeof (item as ContactPickerOption).email !== "string"))) {
    throw new Error("Contact persons could not be loaded. Try again.");
  }
  return { items: items as ContactPickerOption[] };
}

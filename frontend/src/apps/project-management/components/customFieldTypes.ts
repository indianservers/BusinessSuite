export const customFieldTypes = [
  ["text", "Text"], ["long_text", "Text area (long text)"], ["dropdown", "Dropdown"],
  ["number", "Number"], ["money", "Money (amount)"], ["date", "Date"],
  ["checkbox", "Checkbox"], ["email", "Email"], ["phone", "Phone"],
  ["website", "Website"], ["rating", "Rating (0–5)"], ["progress", "Progress (0–100%)"],
] as const;
export const numericFieldTypes = ["number", "money", "rating", "progress"];

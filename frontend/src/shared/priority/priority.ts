export type Priority = "urgent" | "high" | "medium" | "low";

/** Only business priority labels are colored; numeric ordering ranks stay neutral. */
export function normalizePriority(value: unknown): Priority | undefined {
  if (typeof value !== "string") return undefined;
  return ({urgent:"urgent",critical:"urgent",high:"high",medium:"medium",normal:"medium",low:"low"} as Record<string,Priority>)[value.trim().toLowerCase()];
}
export function recordPriority(record: unknown): Priority | undefined {
  if (!record || typeof record !== "object") return undefined;
  const value=record as Record<string,unknown>;
  return normalizePriority(value.priority ?? value.priority_name ?? value.priorityName ?? value.priority_level);
}

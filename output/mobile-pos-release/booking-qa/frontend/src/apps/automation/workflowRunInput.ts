export function workflowRunInput(recordId: string, context: string) {
  let record: unknown;
  try { record = JSON.parse(context.trim() || "{}"); }
  catch { throw new Error("Enter valid JSON field values for the execution context."); }
  if (!record || typeof record !== "object" || Array.isArray(record)) throw new Error("Execution context must be a JSON object.");
  const identity = recordId.trim() ? Number(recordId) : null;
  if (identity !== null && (!Number.isSafeInteger(identity) || identity <= 0)) throw new Error("Record ID must be a positive whole number, or left blank for an unlinked execution.");
  return { record: record as Record<string, unknown>, record_id: identity, depth: 0 };
}

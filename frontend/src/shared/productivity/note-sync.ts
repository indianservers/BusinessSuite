import type { NoteRecord } from "./notesTypes";

export type NoteSyncState = "saving" | "saved" | "error";
export type NoteUpdate = { record: NoteRecord; state: NoteSyncState };

/** A slow list response must not replace a newer local save with an old row. */
export function mergeNoteUpdates(rows: NoteRecord[], updates: Record<number, NoteUpdate>): NoteRecord[] {
  const result = rows.map(row => {
    const update = updates[row.id];
    return update && (update.state !== "saved" || row.version < update.record.version) ? update.record : row;
  });
  const ids = new Set(result.map(row => row.id));
  return [...Object.values(updates).filter(update => update.state !== "saved" && !ids.has(update.record.id)).map(update => update.record), ...result];
}

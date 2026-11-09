import type { GridColumn, GridFilter } from "./types";

type Preset = { label: string; filter: GridFilter };
const equal = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
export function hasMobilePreset(filter: GridFilter, preset: Preset) {
  return equal(filter, preset.filter) || filter.logic === "and" && filter.rules.some(rule => equal(rule, preset.filter));
}
export function toggleMobilePreset(filter: GridFilter, preset: Preset, presets: Preset[]) {
  const active = hasMobilePreset(filter, preset);
  const family = ["Due today", "Overdue"].includes(preset.label) ? ["Due today", "Overdue"] : ["Mine", "Unassigned"].includes(preset.label) ? ["Mine", "Unassigned"] : [preset.label];
  const exclusive = presets.filter(candidate => family.includes(candidate.label));
  let rules = exclusive.some(candidate => equal(filter, candidate.filter)) ? [] : filter.logic === "and" ? filter.rules : [filter];
  rules = rules.filter(rule => !exclusive.some(candidate => equal(rule, candidate.filter)));
  return { logic: "and" as const, rules: active ? rules : [...rules, preset.filter] };
}

export function mobilePresets<T>(columns: GridColumn<T>[], userId?: number, now = new Date()) {
  const presets: Preset[] = [];
  const owner = columns.find(column => /^(owner_user_id|owner_id|assigned_to|assignee_id)$/.test(column.id));
  if (owner && userId) presets.push({ label: "Mine", filter: { logic: "and", rules: [{ field: owner.id, operator: "equals", value: userId }] } });
  const due = columns.find(column => /^(due_date|due_at|next_follow_up_at|next_action_at)$/.test(column.id));
  const day = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  const status = columns.find(column => /^(status|stage)$/.test(column.id));
  if (due) {
    const closed = status?.options?.filter(option => /^(closed|completed|done|cancelled|canceled|won|lost)$/i.test(option.value)) || [];
    const active = closed.map(option => ({ field: status!.id, operator: "not_equals" as const, value: option.value }));
    presets.push({ label: "Due today", filter: { logic: "and", rules: [{ field: due.id, operator: "between", value: day, value2: `${day}T23:59:59.999` }, ...active] } });
    presets.push({ label: "Overdue", filter: { logic: "and", rules: [{ field: due.id, operator: "lt", value: day }, { field: due.id, operator: "not_empty" }, ...active] } });
  }
  if (owner) presets.push({ label: "Unassigned", filter: { logic: "and", rules: [{ field: owner.id, operator: "empty" }] } });
  const pending = status?.options?.find(option => /^(pending[ _]approval|awaiting[ _]approval)$/i.test(option.value));
  if (status && pending) presets.push({ label: "Pending approval", filter: { logic: "and", rules: [{ field: status.id, operator: "equals", value: pending.value }] } });
  return presets;
}

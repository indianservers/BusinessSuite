import { NativeSelect } from "@/components/ui/native-select";
import { dateInputInZone, dateInputToIso } from "./time";
import { Input } from "@/components/ui/input";
export type Schedule = {
  required: boolean;
  type: string;
  reference: string;
  reference_at?: string;
  interval_days: number;
  due_at?: string;
  timezone: string;
  reminder_days: number;
  assigned_user_id?: number;
  assigned_team_id?: number;
  cancellation_policy?: string;
  priority: string;
  purpose: string;
  contact_method: string;
  notes: string;
};
export const defaultSchedule: Schedule = {
  required: false,
  type: "days",
  reference: "purchase",
  interval_days: 45,
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  reminder_days: 2,
  priority: "Normal",
  purpose: "General",
  contact_method: "Call",
  notes: "",
};
export function ScheduleFields({
  value,
  onChange,
  employees = [],
  teams = [],
  template = false,
}: {
  template?: boolean;
  value: Schedule;
  onChange: (v: Schedule) => void;
  employees?: { id: number; name: string }[];
  teams?: { id: number; name: string }[];
}) {
  const patch = (key: string, v: unknown) => onChange({ ...value, [key]: v });
  const select = (label: string, key: keyof Schedule, choices: string[]) => (
    <label className="space-y-1 text-xs">
      {label}
      <NativeSelect
        className="block w-full rounded border bg-background p-2 text-sm"
        value={String(value[key] || "")}
        onChange={(e) => patch(key, e.target.value)}
      >
        {choices.map((c) => (
          <option key={c}>{c}</option>
        ))}
      </NativeSelect>
    </label>
  );
  const date = (label: string, key: "reference_at" | "due_at") => (
    <label className="text-xs">
      {label}
      <Input
        required={key === "due_at" || (!template && value.reference !== "purchase")}
        type="datetime-local"
        value={value[key] ? dateInputInZone(value[key]!, value.timezone) : ""}
        onChange={(e) => {
          try {
            e.target.setCustomValidity("");
            patch(
              key,
              e.target.value
                ? dateInputToIso(e.target.value, value.timezone)
                : undefined,
            );
          } catch (error) {
            e.target.setCustomValidity(
              error instanceof Error
                ? error.message
                : "Choose a valid time zone and date",
            );
            e.target.reportValidity();
          }
        }}
      />
    </label>
  );
  return (
    <fieldset className="space-y-3 rounded-lg border bg-muted/20 p-3">
      <label className="follow-up-toggle flex items-center gap-2 text-sm font-medium">
        <input
          type="checkbox"
          checked={value.required}
          onChange={(e) => patch("required", e.target.checked)}
        />
        Schedule customer follow-up
      </label>
      {value.required && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            {select("Schedule", "type", ["days", "date", "recurring"])}
            {select("Reference date", "reference", [
              "purchase",
              "delivery",
              "completion",
            ])}
            {value.type !== "date" && (
              <label className="text-xs">
                Interval (days)
                <Input
                  type="number"
                  min={1}
                  max={3650}
                  value={value.interval_days}
                  onChange={(e) =>
                    patch("interval_days", Number(e.target.value))
                  }
                />
              </label>
            )}
            {value.type === "date"
              ? date("Follow-up date & time", "due_at")
              : !template && date("Reference date & time", "reference_at")}
            <label className="text-xs">
              Reminder (days before)
              <Input
                type="number"
                min={0}
                max={365}
                value={value.reminder_days}
                onChange={(e) => patch("reminder_days", Number(e.target.value))}
              />
            </label>
            {select("Priority", "priority", [
              "Low",
              "Normal",
              "High",
              "Urgent",
            ])}
            {select("Purpose", "purpose", [
              "Feedback",
              "Renewal",
              "Maintenance",
              "Payment",
              "Upsell",
              "General",
            ])}
            {select("Contact method", "contact_method", [
              "Call",
              "WhatsApp",
              "Email",
              "Visit",
            ])}
            {select("Cancelled / refunded sale", "cancellation_policy", [
              "cancel",
              "retain",
            ])}
            <label className="text-xs">
              Assigned team
              <NativeSelect
                className="block w-full rounded border bg-background p-2 text-sm"
                value={value.assigned_team_id || ""}
                onChange={(e) =>
                  patch("assigned_team_id", Number(e.target.value) || undefined)
                }
              >
                <option value="">No team</option>
                {teams.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </NativeSelect>
            </label>
            <label className="text-xs">
              Assigned employee
              <NativeSelect
                aria-label="Assigned employee"
                className="block w-full rounded border bg-background p-2 text-sm"
                value={value.assigned_user_id || ""}
                onChange={(e) =>
                  patch("assigned_user_id", Number(e.target.value) || undefined)
                }
              >
                <option value="">Me</option>
                {employees.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name}
                  </option>
                ))}
              </NativeSelect>
            </label>
            <label className="text-xs">
              Time zone
              <Input
                value={value.timezone}
                onChange={(e) => patch("timezone", e.target.value)}
              />
            </label>
          </div>
          <label className="block text-xs">
            Notes / customer instructions
            <Input
              value={value.notes}
              onChange={(e) => patch("notes", e.target.value)}
            />
          </label>
          <p className="text-xs text-muted-foreground">
            {template && value.type !== "date"
              ? `A follow-up is created ${value.interval_days} days after each customer's ${value.reference === "completion" ? "service completion" : value.reference}.`
              : value.type !== "date" && value.reference_at
              ? `Next follow-up: ${new Date(new Date(value.reference_at).getTime() + value.interval_days * 86400000).toLocaleString()}`
              : "Purchase reference uses the successful purchase time unless overridden."}
          </p>
        </>
      )}
    </fieldset>
  );
}

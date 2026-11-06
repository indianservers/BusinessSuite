import { useEffect, useState } from "react";
/** A date is committed when the calendar/field is left, avoiding saves for partial date segments. */
export default function InlineProjectDate({
  label,
  value,
  disabled,
  overdue,
  onSave,
}: {
  label: string;
  value?: string;
  disabled: boolean;
  overdue: boolean;
  onSave: (value: string | null) => Promise<boolean>;
}) {
  const [draft, setDraft] = useState(value?.slice(0, 10) || "");
  useEffect(() => setDraft(value?.slice(0, 10) || ""), [value]);
  return (
    <input
      aria-label={label}
      type="date"
      className={overdue ? "is-overdue" : ""}
      disabled={disabled}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={(e) => {
        const next = e.currentTarget.value;
        if (next !== (value?.slice(0, 10) || ""))
          void onSave(next || null).then((saved) => {
            if (!saved) setDraft(value?.slice(0, 10) || "");
          });
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
        if (e.key === "Escape") {
          e.preventDefault();
          e.currentTarget.value = value?.slice(0, 10) || "";
          setDraft(value?.slice(0, 10) || "");
          e.currentTarget.blur();
        }
      }}
    />
  );
}

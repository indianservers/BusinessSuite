import { useEffect, useState, type ReactNode } from "react";
import * as Select from "@radix-ui/react-select";
import { Check, ChevronDown, Loader2 } from "lucide-react";
export const statusTone = (status: string) =>
  /done|complete|resolved|paid|approved|active/i.test(status)
    ? "done"
    : /block|reject|cancel|overdue/i.test(status)
      ? "blocked"
      : /review|pending|waiting/i.test(status)
        ? "review"
        : /progress|working|processing/i.test(status)
          ? "progress"
          : "todo";
export function StatusBadge({ value }: { value: string }) {
  return (
    <span className="kf-status" data-tone={statusTone(value)}>
      <i aria-hidden="true" />
      {value}
    </span>
  );
}
export function StatusSelect({
  value,
  options,
  onSave,
  disabled,
  label,
}: {
  value: string;
  options: string[];
  onSave: (value: string) => Promise<boolean | void>;
  disabled?: boolean;
  label: string;
}) {
  const [pending, setPending] = useState<string>();
  const [error, setError] = useState("");
  useEffect(() => setError(""), [value]);
  return (
    <>
      <Select.Root
        value={pending ?? value}
        disabled={disabled || pending !== undefined}
        onValueChange={async (next) => {
          setPending(next);
          setError("");
          try {
            const result = await onSave(next);
            if (result === false) setError("Change was not saved.");
          } catch {
            setError("Change was not saved. Try again.");
          } finally {
            setPending(undefined);
          }
        }}
      >
        <Select.Trigger
          aria-label={label}
          className="kf-status"
          data-tone={statusTone(pending ?? value)}
          aria-busy={pending !== undefined}
        >
          <i aria-hidden="true" />
          <Select.Value>{pending ?? value}</Select.Value>
          {pending !== undefined ? (
            <Loader2 className="animate-spin" size={13} />
          ) : (
            <ChevronDown size={13} />
          )}
        </Select.Trigger>
        <Select.Portal>
          <Select.Content
            position="popper"
            sideOffset={5}
            collisionPadding={12}
            className="kf-select-menu"
          >
            <Select.Viewport>
              {[...new Set([value, ...options])].map((option) => (
                <Select.Item
                  key={option}
                  value={option}
                  className="kf-select-item"
                >
                  <StatusBadge value={option} />
                  <Select.ItemText>
                    <span className="sr-only">{option}</span>
                  </Select.ItemText>
                  <Select.ItemIndicator style={{ marginLeft: "auto" }}>
                    <Check size={14} />
                  </Select.ItemIndicator>
                </Select.Item>
              ))}
            </Select.Viewport>
          </Select.Content>
        </Select.Portal>
      </Select.Root>
      {error && (
        <span role="alert" className="text-xs text-destructive">
          {error}
        </span>
      )}
    </>
  );
}
export function PageHeader({
  icon: Icon,
  title,
  description,
  actions,
}: {
  icon: typeof import("lucide-react").Home;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="kf-page-header">
      <div className="kf-page-title-group">
        <div className="kf-feature-icon">
          <Icon size={27} />
        </div>
        <div>
          <h1 className="page-title">{title}</h1>
          {description && <p className="page-description">{description}</p>}
        </div>
      </div>
      {actions}
    </div>
  );
}

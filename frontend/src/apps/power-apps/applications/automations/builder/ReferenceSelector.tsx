import { forwardRef, useEffect, useId, useState } from "react";
import { ChevronDown } from "lucide-react";
import type { ReferenceProvider } from "./types";
export const ReferenceSelector = forwardRef<
  HTMLInputElement,
  {
    id: string;
    "aria-label": string;
    disabled?: boolean;
    value: string;
    onChange: (value: string) => void;
    provider?: ReferenceProvider;
    kind: string;
  }
>(function ReferenceSelector(
  { provider, onChange, value, kind, ...input },
  ref,
) {
  const [open, setOpen] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [options, setOptions] = useState<{ value: string; label: string }[]>(
    [],
  );
  const listId = useId();
  useEffect(() => {
    if (!open || !provider) return;
    let live = true;
    setBusy(true);
    setError("");
    const timer = window.setTimeout(
      () =>
        provider(value)
          .then((rows) => {
            if (live) setOptions(rows.slice(0, 50));
          })
          .catch(() => {
            if (live)
              setError(
                "Lookup is unavailable. Check permissions or enter an authorized reference.",
              );
          })
          .finally(() => {
            if (live) setBusy(false);
          }),
      250,
    );
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [open, provider, value]);
  return (
    <div className="as-reference-selector">
      <div>
        <input
          {...input}
          ref={ref}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={listId}
          value={value}
          placeholder={`${kind[0].toUpperCase() + kind.slice(1)} reference or variable`}
          onChange={(event) => {
            onChange(event.target.value);
            setOpen(true);
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") setOpen(true);
            if (event.key === "Escape") {
              event.stopPropagation();
              setOpen(false);
            }
          }}
        />
        <button
          type="button"
          disabled={input.disabled}
          aria-label={`Choose ${kind} reference`}
          onClick={() => setOpen((v) => !v)}
        >
          <ChevronDown size={13} />
        </button>
      </div>
      {open && (
        <div id={listId} role="listbox" aria-label={`${kind} references`}>
          {busy ? (
            <p role="status">Searching authorized references...</p>
          ) : error ? (
            <p role="alert">{error}</p>
          ) : provider && options.length ? (
            options.map((option) => (
              <button
                key={option.value}
                role="option"
                aria-selected={option.value === value}
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
              >
                {option.label}
                <small>{option.value}</small>
              </button>
            ))
          ) : (
            <p>
              {provider
                ? "No matching authorized references."
                : "No lookup adapter is installed for this field. Enter a known reference or map an upstream value."}
            </p>
          )}
          <button type="button" onClick={() => setOpen(false)}>
            Close reference picker
          </button>
        </div>
      )}
    </div>
  );
});

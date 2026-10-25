import { useId } from "react";
import { X } from "lucide-react";

export const splitTags = (text: string) =>
  text
    .split(/[,\n\r]+/)
    .map((name) => name.trim().replace(/\s+/g, " "))
    .filter(Boolean);
export function uniqueTags(names: string[]) {
  const seen = new Set<string>();
  return names.filter((name) => {
    const key = name.toLocaleLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export default function SmartTagsInput({
  value,
  draft,
  onChange,
  onDraftChange,
  suggestions,
  disabled,
}: {
  value: string[];
  draft: string;
  onChange: (tags: string[]) => void;
  onDraftChange: (text: string) => void;
  suggestions: string[];
  disabled?: boolean;
}) {
  const id = useId();
  const add = (text = draft) => {
    const existing = new Map(
      suggestions.map((name) => [name.toLocaleLowerCase(), name]),
    );
    onChange(
      uniqueTags([
        ...value,
        ...splitTags(text).map(
          (name) => existing.get(name.toLocaleLowerCase()) || name,
        ),
      ]),
    );
    onDraftChange("");
  };
  return (
    <div className="smart-tags">
      <div className="compose-tags" aria-label="Selected tags">
        {value.map((name) => (
          <button
            disabled={disabled}
            type="button"
            key={name.toLocaleLowerCase()}
            aria-label={`Remove tag ${name}`}
            onClick={() => onChange(value.filter((tag) => tag !== name))}
          >
            {name}
            <X aria-hidden="true" />
          </button>
        ))}
      </div>
      <div style={{ display: "flex", gap: 8, minWidth: 0 }}>
        <input
          id="task-tags"
          aria-label="Tags"
          aria-describedby={`${id}-help`}
          list={`${id}-suggestions`}
          disabled={disabled}
          value={draft}
          placeholder="Add tags, separated by commas"
          autoComplete="off"
          onPaste={(event) => {
            const text = event.clipboardData.getData("text");
            if (/[,\n\r]/.test(text)) {
              event.preventDefault();
              const input = event.currentTarget;
              add(
                draft.slice(0, input.selectionStart ?? draft.length) +
                  text +
                  draft.slice(input.selectionEnd ?? draft.length),
              );
            }
          }}
          onChange={(event) => {
            const text = event.target.value;
            if (/[,\n\r]/.test(text)) add(text);
            else onDraftChange(text);
          }}
          onKeyDown={(event) => {
            if (event.nativeEvent.isComposing) return;
            if (event.key === "Enter") {
              event.preventDefault();
              add();
            }
            if (event.key === "Backspace" && !draft && value.length) {
              event.preventDefault();
              onChange(value.slice(0, -1));
            }
          }}
        />
        <button
          type="button"
          className="compose-tag-add"
          disabled={disabled || !draft.trim()}
          onClick={() => add()}
        >
          Add
        </button>
      </div>
      <datalist id={`${id}-suggestions`}>
        {uniqueTags(suggestions)
          .filter(
            (name) =>
              !value.some(
                (tag) => tag.toLocaleLowerCase() === name.toLocaleLowerCase(),
              ),
          )
          .map((name) => (
            <option key={name} value={name} />
          ))}
      </datalist>
      <small id={`${id}-help`}>
        Comma or Enter adds tags. Choose an existing tag or type a new one.
      </small>
    </div>
  );
}

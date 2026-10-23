import { useState, type CSSProperties } from "react";
import { displayed, type Answer, type Definition } from "./formsTypes";
export default function FormResponse({
  definition,
  disabled,
  submit,
  mobile = false,
}: {
  definition: Definition;
  disabled: boolean;
  submit: (a: Record<string, Answer>) => Promise<void>;
  mobile?: boolean;
}) {
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const fields = displayed(definition.fields, answers);
  const set = (id: string, value: Answer) =>
    setAnswers((a) => ({ ...a, [id]: value }));
  return (
    <form
      className={"form-live " + (mobile ? "form-device-mobile" : "")}
      style={{ "--form-accent": definition.accent } as CSSProperties}
      onSubmit={(e) => {
        e.preventDefault();
        const allowed = new Set(fields.map((f) => f.id));
        void submit(
          Object.fromEntries(
            Object.entries(answers).filter(([id]) => allowed.has(id)),
          ),
        );
      }}
    >
      <div className="form-live-banner" />
      <h2>{definition.name}</h2>
      <p>{definition.description}</p>
      <fieldset disabled={disabled}>
        {fields.map((f) => (
          <div className="form-live-field" key={f.id}>
            {f.type === "section" ? (
              <h3>{f.label}</h3>
            ) : (
              <>
                <label htmlFor={f.id}>
                  {f.label}
                  {f.required && <em> *</em>}
                </label>
                {f.type === "textarea" ? (
                  <textarea
                    id={f.id}
                    required={f.required}
                    maxLength={10000}
                    placeholder={f.placeholder}
                    value={String(answers[f.id] || "")}
                    onChange={(e) => set(f.id, e.target.value)}
                  />
                ) : f.type === "select" ? (
                  <select
                    id={f.id}
                    required={f.required}
                    value={String(answers[f.id] || "")}
                    onChange={(e) => set(f.id, e.target.value)}
                  >
                    <option value="">Choose an option</option>
                    {f.options.map((o) => (
                      <option key={o}>{o}</option>
                    ))}
                  </select>
                ) : ["radio", "multiselect"].includes(f.type) ? (
                  <fieldset aria-label={f.label}>
                    {f.options.map((o) => (
                      <label className="form-choice" key={o}>
                        <input
                          type={f.type === "radio" ? "radio" : "checkbox"}
                          name={f.id}
                          required={
                            f.required &&
                            (f.type === "radio" ||
                              !Array.isArray(answers[f.id]) ||
                              (answers[f.id] as string[]).length === 0)
                          }
                          checked={
                            f.type === "radio"
                              ? answers[f.id] === o
                              : Array.isArray(answers[f.id]) &&
                                (answers[f.id] as string[]).includes(o)
                          }
                          onChange={(e) =>
                            set(
                              f.id,
                              f.type === "radio"
                                ? o
                                : e.target.checked
                                  ? [
                                      ...(Array.isArray(answers[f.id])
                                        ? (answers[f.id] as string[])
                                        : []),
                                      o,
                                    ]
                                  : (answers[f.id] as string[]).filter(
                                      (v) => v !== o,
                                    ),
                            )
                          }
                        />
                        {o}
                      </label>
                    ))}
                  </fieldset>
                ) : f.type === "checkbox" ? (
                  <label className="form-choice">
                    <input
                      id={f.id}
                      type="checkbox"
                      required={f.required}
                      checked={answers[f.id] === true}
                      onChange={(e) => set(f.id, e.target.checked)}
                    />
                    I agree
                  </label>
                ) : f.type === "rating" ? (
                  <select
                    id={f.id}
                    required={f.required}
                    value={String(answers[f.id] || "")}
                    onChange={(e) => set(f.id, e.target.value)}
                  >
                    <option value="">Choose a rating</option>
                    {[1, 2, 3, 4, 5].map((n) => (
                      <option key={n} value={n}>
                        {"★".repeat(n)}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    id={f.id}
                    type={f.type === "phone" ? "tel" : f.type}
                    required={f.required}
                    min={f.min ?? undefined}
                    max={f.max ?? undefined}
                    step={f.type === "number" ? "any" : undefined}
                    maxLength={2000}
                    placeholder={f.placeholder}
                    value={String(answers[f.id] ?? "")}
                    onChange={(e) =>
                      set(
                        f.id,
                        f.type === "number" && e.target.value !== ""
                          ? Number(e.target.value)
                          : e.target.value,
                      )
                    }
                  />
                )}
              </>
            )}
            {f.help && <small>{f.help}</small>}
          </div>
        ))}
        <button className="form-primary" type="submit">
          {definition.submit_label} →
        </button>
      </fieldset>
      <small className="form-internal-note">
        Secure workspace form · Sign-in required
      </small>
    </form>
  );
}

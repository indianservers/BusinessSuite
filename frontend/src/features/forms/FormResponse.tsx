import { PhoneInput } from "@/lib/validation/PhoneInput";
import { useState, type CSSProperties, type ReactNode } from "react";
import { displayed, type Answer, type Definition } from "./formsTypes";
export default function FormResponse({
  definition,
  disabled,
  submit,
  mobile = false,
  footer,
  onFiles,
  publicForm = false,
}: {
  definition: Definition;
  disabled: boolean;
  submit: (a: Record<string, Answer>) => Promise<void>;
  mobile?: boolean;
  publicForm?: boolean;
  footer?: ReactNode;
  onFiles?: (files: Record<string, File>) => void;
}) {
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const [files, setFiles] = useState<Record<string, File>>({});
  const [page, setPage] = useState(0);
  const allFields = displayed(definition.fields, answers);
  const pages: (typeof allFields)[] = [[]];
  allFields.forEach((f) => {
    if (f.type === "page" && definition.settings?.layout === "pages")
      pages.push([]);
    else pages[pages.length - 1].push(f);
  });
  const currentPage = Math.min(page, pages.length - 1);
  const fields = pages[currentPage];
  const set = (id: string, value: Answer) =>
    setAnswers((a) => ({ ...a, [id]: value }));
  return (
    <form
      className={"form-live " + (mobile ? "form-device-mobile" : "")}
      style={
        {
          "--form-accent": definition.accent,
          fontFamily:
            definition.settings?.font === "serif"
              ? "Georgia, serif"
              : definition.settings?.font === "monospace"
                ? "monospace"
                : undefined,
          "--form-radius": `${definition.settings?.button_radius ?? 10}px`,
        } as CSSProperties
      }
      onSubmit={(e) => {
        e.preventDefault();
        if (currentPage < pages.length - 1) {
          setPage(currentPage + 1);
          return;
        }
        const allowed = new Set(allFields.flatMap(f=>f.type==='phone'?[f.id,f.id+'_country_code']:[f.id]));
        void submit(
          Object.fromEntries(
            Object.entries(answers).filter(([id]) => allowed.has(id)),
          ),
        );
      }}
    >
      <div className="form-live-banner" />
      <h2 aria-level={publicForm ? 1 : 2}>{definition.name}</h2>
      <p>{definition.description}</p>
      {pages.length > 1 && (
        <p>
          Step {currentPage + 1} of {pages.length}{" "}
          <progress value={currentPage + 1} max={pages.length} />
        </p>
      )}
      <fieldset disabled={disabled}>
        {fields.map((f) => (
          <div className="form-live-field" key={f.id}>
            {["section", "page"].includes(f.type) ? (
              <h3>{f.label}</h3>
            ) : (
              <>
                <label htmlFor={f.id}>
                  {f.label}
                  {f.required && <em> *</em>}
                </label>
                {f.type === "file" ? (
                  <>
                    <input
                      id={f.id}
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg"
                      required={f.required && !files[f.id]}
                      onChange={(e) => {
                        const next = { ...files };
                        const file = e.target.files?.[0];
                        if (file && file.size > 2 * 1024 * 1024) {
                          e.target.value = "";
                          e.target.setCustomValidity(
                            "Maximum file size is 2 MB",
                          );
                          e.target.reportValidity();
                          return;
                        }
                        e.target.setCustomValidity("");
                        if (file) next[f.id] = file;
                        else delete next[f.id];
                        setFiles(next);
                        onFiles?.(next);
                        set(f.id, file ? file.name : "");
                      }}
                    />
                    <small>
                      PDF, PNG or JPEG · 2 MB per file · 3 MB total · up to 3
                      files
                    </small>
                  </>
                ) : f.type === "textarea" ? (
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
                ) : f.type==='phone' ? <PhoneInput id={f.id} label={f.label} required={f.required} value={String(answers[f.id] ?? '')} countryCode={String(answers[f.id+'_country_code'] ?? '+91')} onChange={value=>setAnswers(current=>({...current,[f.id]:value,[f.id+'_country_code']:current[f.id+'_country_code'] ?? '+91'}))} onCountryCodeChange={value=>set(f.id+'_country_code',value)} /> : f.type === "rating" ? (
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
                    type={f.type}
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
        {currentPage === pages.length - 1 && footer}
        {currentPage > 0 && (
          <button type="button" onClick={() => setPage(currentPage - 1)}>
            Back
          </button>
        )}
        <button className="form-primary" type="submit">
          {currentPage < pages.length - 1
            ? "Continue"
            : definition.submit_label}{" "}
          →
        </button>
      </fieldset>
      <small className="form-internal-note">
        {publicForm
          ? "Protected form · Your response is shared with the form owner"
          : "Preview · No response is stored"}
      </small>
    </form>
  );
}

import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/services/api";
import FormResponse from "./FormResponse";
import type { Definition, Answer } from "./formsTypes";
import "./FormsPage.css";

declare global {
  interface Window {
    turnstile?: {
      render: (el: HTMLElement, options: Record<string, unknown>) => string;
      remove: (id: string) => void;
      reset: (id: string) => void;
    };
  }
}
export function Turnstile({
  siteKey,
  onToken,
}: {
  siteKey: string;
  onToken: (s: string) => void;
}) {
  const node = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let id: string | undefined;
    let active = true;
    const render = () => {
      if (active && window.turnstile && node.current && !id)
        id = window.turnstile.render(node.current, {
          sitekey: siteKey,
          callback: onToken,
          "expired-callback": () => onToken(""),
          "error-callback": () => onToken(""),
        });
    };
    let script = document.querySelector<HTMLScriptElement>(
      "script[data-form-turnstile]",
    );
    if (!script) {
      script = document.createElement("script");
      script.src =
        "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
      script.async = true;
      script.dataset.formTurnstile = "true";
      document.head.appendChild(script);
    }
    script.addEventListener("load", render);
    render();
    return () => {
      active = false;
      script?.removeEventListener("load", render);
      if (id) window.turnstile?.remove(id);
    };
  }, [siteKey, onToken]);
  return <div ref={node} />;
}
export default function PublicFormPage({
  internal = false,
}: {
  internal?: boolean;
}) {
  const { slug, formId } = useParams();
  const endpoint = internal
    ? `/forms/${formId}/internal`
    : `/forms/public/${slug}`;
  const [data, setData] = useState<{
    definition: Definition;
    version: number;
    open: boolean;
    site_key?: string;
  } | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const [challenge, setChallenge] = useState<{
    id: string;
    image: string;
  } | null>(null);
  const [answer, setAnswer] = useState("");
  const [website, setWebsite] = useState("");
  const [files, setFiles] = useState<Record<string, File>>({});
  const [token, setToken] = useState("");
  const [captchaEpoch, setCaptchaEpoch] = useState(0);
  const requestId = useRef(crypto.randomUUID());
  const refresh = async () => {
    try {
      const r = await api.get(`${endpoint}/challenge`);
      setChallenge(r.data);
      setAnswer("");
    } catch (e) {
      setError(message(e));
    }
  };
  useEffect(() => {
    let active = true;
    api
      .get(endpoint)
      .then((r) => {
        if (active) {
          setData(r.data);
          if (
            !internal &&
            r.data.open &&
            r.data.definition.settings.captcha === "builtin"
          )
            void refresh();
        }
      })
      .catch((e) => {
        if (active) setError(message(e));
      });
    return () => {
      active = false;
    };
  }, [slug, formId, internal]);
  const send = async (answers: Record<string, Answer>) => {
    if (!data) return;
    const visibleFiles = Object.entries(files).filter(([id]) => id in answers);
    if (
      visibleFiles.length > 3 ||
      visibleFiles.reduce((sum, [, file]) => sum + file.size, 0) >
        3 * 1024 * 1024
    ) {
      setError("Upload limit: 3 files, 2 MB per file, 3 MB total");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const uploads: Record<string, { filename: string; data: string }> = {};
      for (const [id, file] of Object.entries(files)) {
        if (!(id in answers)) continue;
        uploads[id] = {
          filename: file.name,
          data: await new Promise<string>((resolve, reject) => {
            const r = new FileReader();
            r.onload = () => resolve(String(r.result).split(",")[1]);
            r.onerror = reject;
            r.readAsDataURL(file);
          }),
        };
      }
      const r = await api.post(`${endpoint}/submit`, {
        request_id: requestId.current,
        version: data.version,
        answers,
        files: uploads,
        website,
        challenge_id: challenge?.id || "",
        captcha_answer: answer,
        turnstile_token: token,
      });
      setSuccess(r.data.message);
    } catch (e) {
      setError(message(e));
      setToken("");
      setCaptchaEpoch((n) => n + 1);
      if (!internal && data.definition.settings?.captcha === "builtin")
        void refresh();
    } finally {
      setBusy(false);
    }
  };
  return (
    <main className="forms-studio public-form-shell">
      <div aria-live="polite">
        {error && (
          <p className="forms-error" role="alert">
            {error}
          </p>
        )}
      </div>
      {success ? (
        <section className="forms-panel">
          <h1>Response received</h1>
          <p>{success}</p>
        </section>
      ) : data ? (
        data.open ? (
          <FormResponse
            definition={data.definition}
            disabled={busy}
            publicForm
            submit={send}
            onFiles={setFiles}
            footer={
              internal ? undefined : (
                <>
                  <div className="form-honey" aria-hidden="true">
                    <label>
                      Leave this empty
                      <input
                        tabIndex={-1}
                        autoComplete="off"
                        value={website}
                        onChange={(e) => setWebsite(e.target.value)}
                      />
                    </label>
                  </div>
                  {data.site_key ? (
                    <Turnstile
                      key={captchaEpoch}
                      siteKey={data.site_key}
                      onToken={setToken}
                    />
                  ) : (
                    <div className="forms-captcha">
                      <h3>Security check</h3>
                      {challenge && (
                        <img
                          src={challenge.image}
                          alt="Security code. Enter the six characters shown."
                          width={240}
                          height={80}
                        />
                      )}
                      <button type="button" onClick={() => void refresh()}>
                        Refresh security code
                      </button>
                      <label>
                        Security code
                        <input
                          autoComplete="off"
                          required
                          maxLength={6}
                          value={answer}
                          onChange={(e) => setAnswer(e.target.value)}
                        />
                      </label>
                      <small>
                        Codes expire in five minutes. If you cannot read it,
                        refresh for another code.
                      </small>
                    </div>
                  )}
                </>
              )
            }
          />
        ) : (
          <section className="forms-panel">
            <h1>This form is closed</h1>
            <p>The owner is no longer accepting responses.</p>
          </section>
        )
      ) : (
        !error && <p>Loading form…</p>
      )}
    </main>
  );
}
export function message(e: unknown) {
  const value = (e as { response?: { data?: { detail?: unknown } } }).response
    ?.data?.detail;
  return typeof value === "string"
    ? value
    : Array.isArray(value)
      ? value.map((v: { msg?: string }) => v.msg).join("; ")
      : "Could not complete this request. Please try again.";
}

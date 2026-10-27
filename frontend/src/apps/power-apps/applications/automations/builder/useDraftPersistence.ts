import { useCallback, useEffect, useRef, useState } from "react";
import type { Resource } from "../../../registry";
import type { WorkflowDocument } from "./types";
import { errorMessage } from "../../../api";
export type SaveStatus = "saved" | "dirty" | "saving" | "error" | "conflict";
type Recovery = {
  document: WorkflowDocument;
  baseVersion: number;
  timestamp: string;
};
export function useDraftPersistence(
  document: WorkflowDocument,
  options: {
    key: string;
    version: number;
    savedAt?: string;
    exists: boolean;
    readOnly: boolean;
    paused?: boolean;
    onSave: (document: WorkflowDocument, version: number) => Promise<Resource>;
    onSaved?: (resource: Resource) => void;
  },
) {
  const serialized = JSON.stringify(document);
  const documentRef = useRef(document);
  documentRef.current = document;
  const callbacks = useRef(options);
  callbacks.current = options;
  const currentVersion = useRef(options.version);
  const lastSaved = useRef(options.exists ? serialized : "");
  const unsavedBase = useRef(options.version);
  const blocked = useRef(false);
  const pending = useRef<Promise<Resource | null> | null>(null);
  const mounted = useRef(true);
  const previousKey = useRef(options.key);
  const [status, setStatus] = useState<SaveStatus>(
    options.exists ? "saved" : "dirty",
  );
  const [version, setVersion] = useState(options.version);
  const [savedAt, setSavedAt] = useState(options.savedAt);
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);
  const [recovery, setRecovery] = useState<Recovery | null>(() => {
    try {
      const value = JSON.parse(sessionStorage.getItem(options.key) || "null");
      return value?.document?.definition?.schema_version === 2 &&
        typeof value.baseVersion === "number" &&
        JSON.stringify(value.document) !== serialized
        ? value
        : null;
    } catch {
      return null;
    }
  });
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    if (previousKey.current !== options.key) {
      try {
        const old = sessionStorage.getItem(previousKey.current);
        if (old && !sessionStorage.getItem(options.key))
          sessionStorage.setItem(options.key, old);
        sessionStorage.removeItem(previousKey.current);
      } catch {
        /* Editing still works if browser storage is unavailable. */
      }
      previousKey.current = options.key;
    }
  }, [options.key]);
  const flush = useCallback((retry = false): Promise<Resource | null> => {
    if (pending.current) return pending.current;
    if (callbacks.current.readOnly || (blocked.current && !retry))
      return Promise.resolve(null);
    const snapshot = structuredClone(documentRef.current);
    const signature = JSON.stringify(snapshot);
    if (signature === lastSaved.current) return Promise.resolve(null);
    if (!snapshot.name.trim()) {
      setStatus("error");
      setError("Give this automation a name before saving");
      return Promise.resolve(null);
    }
    blocked.current = false;
    setError("");
    setStatus("saving");
    const base = currentVersion.current;
    unsavedBase.current = base;
    const promise = callbacks.current
      .onSave(snapshot, base)
      .then((row) => {
        currentVersion.current = row.version;
        unsavedBase.current = row.version;
        lastSaved.current = signature;
        if (mounted.current) {
          setVersion(row.version);
          setSavedAt(row.updated_at);
          setStatus(
            JSON.stringify(documentRef.current) === signature
              ? "saved"
              : "dirty",
          );
        }
        if (JSON.stringify(documentRef.current) === signature) {
          try {
            sessionStorage.removeItem(callbacks.current.key);
          } catch {
            /* Optional recovery cache. */
          }
        }
        callbacks.current.onSaved?.(row);
        return row;
      })
      .catch((e) => {
        blocked.current = true;
        if (mounted.current) {
          setError(errorMessage(e));
          setStatus(
            (e as { response?: { status?: number } })?.response?.status === 409
              ? "conflict"
              : "error",
          );
        }
        return null;
      })
      .finally(() => {
        pending.current = null;
        if (mounted.current) setTick((v) => v + 1);
      });
    pending.current = promise;
    return promise;
  }, []);
  useEffect(() => {
    if (options.readOnly || recovery) return;
    if (serialized === lastSaved.current) {
      if (!pending.current && !blocked.current) setStatus("saved");
      return;
    }
    try {
      sessionStorage.setItem(
        options.key,
        JSON.stringify({
          document,
          baseVersion: blocked.current
            ? unsavedBase.current
            : currentVersion.current,
          timestamp: new Date().toISOString(),
        }),
      );
    } catch {
      /* Storage quotas cannot block server saves. */
    }
    if (blocked.current || pending.current || recovery || options.paused)
      return;
    setStatus("dirty");
    const timer = window.setTimeout(() => {
      void flush();
    }, 1100);
    return () => window.clearTimeout(timer);
  }, [
    serialized,
    options.readOnly,
    options.paused,
    options.key,
    tick,
    recovery,
    flush,
  ]);
  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (
        !callbacks.current.readOnly &&
        JSON.stringify(documentRef.current) !== lastSaved.current
      ) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);
  const recover = () => {
    if (!recovery) return null;
    const value = recovery.document;
    unsavedBase.current = recovery.baseVersion;
    if (recovery.baseVersion !== currentVersion.current) {
      blocked.current = true;
      setStatus("conflict");
      setError(
        "The server has a newer version. Recover into a separate copy or reload the latest draft.",
      );
    }
    setRecovery(null);
    return value;
  };
  const discardRecovery = () => {
    setRecovery(null);
    try {
      sessionStorage.removeItem(options.key);
    } catch {
      /* Optional cache. */
    }
  };
  return {
    status,
    version,
    savedAt,
    error,
    recovery,
    recover,
    discardRecovery,
    flush,
    dirty: serialized !== lastSaved.current,
  };
}

import { useState, type Dispatch, type SetStateAction } from "react";
import { useLocation } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { stable } from "@/lib/smart-cache/model";
import { navigationViews } from "@/lib/navigation-views";
/** UI preferences only. Never pass record payloads or form drafts. Memory is scoped and bounded. */
export function useRouteViewState<T>(
  name: string,
  initial: T | (() => T),
): [T, Dispatch<SetStateAction<T>>] {
  const user = useAuthStore((s) => s.user),
    { pathname } = useLocation();
  const scope = stable([
    user?.id,
    user?.primary_role ?? user?.role,
    user?.access,
    sessionStorage.getItem("suite-tenant"),
    sessionStorage.getItem("suite-organization"),
    sessionStorage.getItem("suite-branch"),
  ]);
  navigationViews.scope(scope);
  const key = JSON.stringify([scope, pathname, name]);
  const read = () => {
    const values = navigationViews.get(pathname)?.values;
    return values && name in values
      ? (values[name] as T)
      : typeof initial === "function"
        ? (initial as () => T)()
        : initial;
  };
  const [state, setState] = useState(() => ({ key, value: read() }));
  const value = state.key === key ? state.value : read();
  const setValue: Dispatch<SetStateAction<T>> = (update) =>
    setState((previous) => {
      const current = previous.key === key ? previous.value : read();
      const next =
        typeof update === "function"
          ? (update as (v: T) => T)(current)
          : update;
      navigationViews.setValue(scope, pathname, name, next);
      return { key, value: next };
    });
  return [value, setValue];
}

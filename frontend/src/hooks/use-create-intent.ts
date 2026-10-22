import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";

/** Consume a New-menu intent once, including another selection on the same page. */
export function useCreateIntent(open: (kind: string) => void) {
  const location = useLocation();
  const navigate = useNavigate();
  const callback = useRef(open);
  callback.current = open;
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const kind = params.get("new");
    if (!kind) return;
    callback.current(kind);
    params.delete("new");
    navigate({ pathname: location.pathname, search: params.toString(), hash: location.hash }, { replace: true });
  }, [location.key, location.pathname, location.search, location.hash, navigate]);
}

import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { beginProgress } from "../../lib/async-progress";

export default function RouteProgress() {
  const location = useLocation();
  useEffect(() => {
    const finish = beginProgress("Opening page");
    const timer = setTimeout(() => finish(), 400);
    return () => { clearTimeout(timer); finish(); };
  }, [location.key]);
  return null;
}

export function PendingPageProgress() {
  useEffect(() => beginProgress("Loading page"), []);
  return null;
}

import { useEffect, useState } from "react";
export function useMobile(maxWidth = 767) {
  const [mobile, setMobile] = useState(() => window.matchMedia(`(max-width: ${maxWidth}px)`).matches);
  useEffect(() => {
    const media = window.matchMedia(`(max-width: ${maxWidth}px)`);
    const update = () => setMobile(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [maxWidth]);
  return mobile;
}

import { useEffect, useState } from "react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";

export function useCompanyBranding(path: string) {
  const user = useAuthStore((s) => s.user);
  const [name, setName] = useState("");
  useEffect(() => {
    if (!user) return;
    let live = true;
    const root = document.documentElement;
    const original = new Map<string, string>();
    const company = Number(
      sessionStorage.getItem("suite-organization") ||
        user.access?.companyId ||
        1,
    );
    api
      .get("/access/enterprise/branding", {
        params: { companyId: company },
        progress: false,
      })
      .then((response) => {
        if (!live) return;
        const theme = response.data.values || {};
        setName(theme.appName || "");
        function hsl(hex: string) {
          let [r, g, b] = [1, 3, 5].map(
            (i) => parseInt(hex.slice(i, i + 2), 16) / 255,
          );
          const high = Math.max(r, g, b),
            low = Math.min(r, g, b),
            delta = high - low,
            light = (high + low) / 2;
          let hue = 0,
            saturation = 0;
          if (delta) {
            saturation = delta / (1 - Math.abs(2 * light - 1));
            hue =
              high === r
                ? ((g - b) / delta) % 6
                : high === g
                  ? (b - r) / delta + 2
                  : (r - g) / delta + 4;
            hue = (hue * 60 + 360) % 360;
          }
          return `${hue.toFixed(1)} ${(saturation * 100).toFixed(1)}% ${(light * 100).toFixed(1)}%`;
        }
        for (const [field, variable] of [
          ["primary", "--primary"],
          ["surface", "--card"],
          ["surface", "--popover"],
          ["background", "--background"],
          ["text", "--foreground"],
          ["text", "--card-foreground"],
          ["text", "--popover-foreground"],
          ["text", "--muted-foreground"],
        ]) {
          if (/^#[0-9a-f]{6}$/i.test(theme[field] || "")) {
            original.set(variable, root.style.getPropertyValue(variable));
            root.style.setProperty(variable, hsl(theme[field]));
          }
        }
        if (Number.isInteger(theme.radius)) {
          original.set("--radius", root.style.getPropertyValue("--radius"));
          root.style.setProperty("--radius", `${theme.radius}px`);
        }
      })
      .catch(() => {
        if (live) setName("");
      });
    return () => {
      live = false;
      for (const [key, value] of original) {
        if (value) root.style.setProperty(key, value);
        else root.style.removeProperty(key);
      }
    };
  }, [user?.id, path]);
  return name;
}

import { useAuthStore } from "@/store/authStore";
import { api } from "@/services/api";

function loginProvider() {
  try {
    const token = useAuthStore.getState().accessToken;
    const provider = JSON.parse(atob((token || "").split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))).auth_provider;
    return provider === "google" || provider === "microsoft" ? provider : null;
  } catch { return null; }
}

export function usesSocialVerification(value: string) {
  return value.startsWith("provider:") || !!loginProvider();
}

export async function administratorStepUp(value: string) {
  const provider = value.startsWith("provider:") ? value.slice(9) : loginProvider();
  if (provider === "google" || provider === "microsoft") {
    const { socialStepUp } = await import("@/services/firebaseLogin");
    const identity_token = await socialStepUp(provider);
    return api.post("/access/step-up", { identity_token });
  }
  return api.post("/access/step-up", { password: value });
}

export default function AdminVerification({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const provider = loginProvider();
  const selected = provider || (value.startsWith("provider:") ? value.slice(9) : "password");
  return <div className="space-y-2">
    {provider ? <p>Continue to verify your {provider === "google" ? "Google" : "Microsoft"} account.</p> : <label className="block space-y-1 text-sm">Verify using
      <select className="block h-10 w-full rounded-md border bg-background px-3" aria-label="Administrator verification method" value={selected} onChange={event => onChange(event.target.value === "password" ? "" : `provider:${event.target.value}`)}>
        <option value="password">Password</option><option value="google">Google</option><option value="microsoft">Microsoft</option>
      </select>
    </label>}
    {selected === "password" && <label className="block space-y-1 text-sm">Current administrator password<input className="block w-full rounded border p-2" type="password" autoComplete="current-password" required value={value} onChange={event => onChange(event.target.value)} /></label>}
  </div>;
}

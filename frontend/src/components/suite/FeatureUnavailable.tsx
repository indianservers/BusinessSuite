import { Link } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";

export default function FeatureUnavailable({title}:{title:string}) {
  const admin=useAuthStore(state=>state.user?.access?.isAccessAdmin);
  return <section className="space-y-3 rounded-lg border bg-card p-6"><h1 className="text-xl font-semibold">{title} unavailable</h1><p>{title} are unavailable for this account or organization.</p>{admin ? <Link className="text-primary underline" to="/settings/users">Review module access</Link> : <p className="text-sm text-muted-foreground">Ask a company administrator to review module access.</p>}</section>;
}

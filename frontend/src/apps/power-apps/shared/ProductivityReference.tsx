import { Link } from "react-router-dom";
import { productivityReferences } from "@/shared/productivity/references";
import { canAccessRoute } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";

export function ProductivityReference({ section }: { section: string }) {
  const user = useAuthStore(s => s.user);
  const reference = productivityReferences.find(item => item.id === section);
  if (!reference) return null;
  return <section className="pa-panel">
    <span className="pa-status">Integration reference</span>
    <h2>{reference.name}</h2>
    <p>{reference.description}</p>
    <p>Business Suite uses the fully integrated PMS implementation. Integrating this capability into another application requires its own data mapping, permissions and service connections.</p>
    <h3>Integration requirements</h3>
    <ul>{reference.integration.map(item => <li key={item}>{item}</li>)}</ul>
    <h3>Existing Business Suite behavior</h3>
    <p>{reference.preserve}</p>
    {user && canAccessRoute(reference.route, user.role, user.is_superuser) && <Link to={reference.route}>Open integrated PMS {reference.name}</Link>}
  </section>;
}

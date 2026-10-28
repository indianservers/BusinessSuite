import { Link } from "react-router-dom";
import { LayoutGrid } from "lucide-react";
import "./suite.css";

export default function SuiteBrand({
  to = "/",
  subtitle = "YOUR CONNECTED WORKSPACE",
}: {
  to?: string;
  subtitle?: string;
}) {
  return (
    <Link to={to} className="suite-identity" aria-label="Business Suite home">
      <span>
        <LayoutGrid size={28} />
      </span>
      <div>
        Business Suite<small>{subtitle}</small>
      </div>
    </Link>
  );
}

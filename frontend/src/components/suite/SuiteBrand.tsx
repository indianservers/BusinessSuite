import { Link } from "react-router-dom";
import { LayoutGrid } from "lucide-react";
import "./suite.css";

export default function SuiteBrand({
  to = "/",
  subtitle = "YOUR CONNECTED WORKSPACE",
  mobileSubtitle,
}: {
  to?: string;
  subtitle?: string;
  mobileSubtitle?: string;
}) {
  return (
    <Link to={to} className="suite-identity" aria-label="Business Suite home">
      <span>
        <LayoutGrid size={28} />
      </span>
      <div>
        Business Suite<small>{subtitle}</small>{mobileSubtitle && <small className="launcher-brand-company">{mobileSubtitle}</small>}
      </div>
    </Link>
  );
}

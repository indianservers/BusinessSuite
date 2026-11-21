import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import "./hrms-service-header.css";

interface HrmsServiceHeaderProps {
  title: string;
  description: string;
  icon: LucideIcon;
  actions?: ReactNode;
}

export default function HrmsServiceHeader({ title, description, icon: Icon, actions }: HrmsServiceHeaderProps) {
  return (
    <header className="hrms-service-header">
      <div className="hrms-service-header-copy">
        <span className="hrms-service-header-icon" aria-hidden="true"><Icon size={22} /></span>
        <div>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
      </div>
      {actions && <div className="hrms-service-header-actions">{actions}</div>}
    </header>
  );
}

import type { ReactNode } from "react";
import "./crm-page.css";

export default function CRMPageHeader({ title, description, actions, subsection = false }: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  subsection?: boolean;
}) {
  const Heading = subsection ? "h2" : "h1";
  return (
    <header className={`crm-page-header${subsection ? " crm-page-header-subsection" : ""}`}>
      <div className="crm-page-identity">
        <Heading>{title}</Heading>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="crm-page-actions">{actions}</div>}
    </header>
  );
}

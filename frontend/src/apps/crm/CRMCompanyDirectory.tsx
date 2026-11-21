import CompaniesPage from "@/shared/master-data/CompaniesPage";
import "./crm-company-directory.css";

export default function CRMCompanyDirectory({ role }: { role?: string }) {
  return <div className="crm-company-directory"><CompaniesPage role={role} /></div>;
}

import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import WorkforcePersonPreview from "@/components/workforce/WorkforcePersonPreview";
import { api, employeeApi } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
type Employee = { id: number; first_name: string; last_name: string; employee_id: string; employment_type: string; status: string; personal_email: string | null; department_id: number | null };
export default function EmployeeQuickPreview({ employee, options, onClose }: { employee: Employee; options?: Record<string, { value: string; label: string }[]>; onClose: () => void }) {
  const navigate = useNavigate();
  const userId = useAuthStore(s => s.user?.id);
  const detail = useQuery({ queryKey: ["employee-preview", userId, employee.id], queryFn: () => employeeApi.get(employee.id).then(r => r.data) });
  const summary = useQuery({ queryKey: ["workforce", "/project-management/operations", "employee-summary", userId, employee.id], queryFn: () => api.get("/project-management/operations/people", { params: { search: employee.employee_id, kind: "all", per_page: 50 } }).then(r => r.data.items.find((item: { id: number }) => item.id === employee.id)) });
  const person = { ...employee, ...detail.data };
  const option = (key: string, id: unknown) => options?.[key]?.find(item => item.value === String(id))?.label;
  const profile = { ...person, ...summary.data, name: `${person.first_name} ${person.last_name}`.trim(), email: person.work_email || person.personal_email,
    department: summary.data?.department || person.department_name || option("department_id", person.department_id) || (person.department_id ? `Department #${person.department_id}` : undefined),
    manager: summary.data?.manager || person.reporting_manager_name || option("reporting_manager_id", person.reporting_manager_id) || (person.reporting_manager_id ? `Supervisor #${person.reporting_manager_id}` : undefined) };
  return <WorkforcePersonPreview profile={profile} root="/project-management/operations" taskPath="/pms/batch-tasks" onClose={onClose} onFollowUp={() => { onClose(); navigate("/pms/people-work", { state: { employee_ids: [employee.id] } }); }} />;
}

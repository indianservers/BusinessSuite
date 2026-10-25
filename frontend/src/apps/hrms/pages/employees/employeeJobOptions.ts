import { employeeApi } from "@/services/api";

export async function loadManagerOptions(): Promise<Array<{ id: number; name: string }>> {
  const options: Array<{ id: number; name: string }> = [];
  let page = 1;
  while (true) {
    const { data } = await employeeApi.list({ page, per_page: 100, status: "Active" });
    const employees = data.items || [];
    options.push(...employees.map((employee: any) => ({
      id: employee.id,
      name: `${employee.first_name} ${employee.last_name} (${employee.employee_id})`,
    })));
    if (!employees.length || options.length >= data.total || employees.length < 100) break;
    page += 1;
  }
  return options;
}

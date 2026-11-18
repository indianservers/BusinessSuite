import { api } from "@/services/api";

export async function loadManagerOptions(): Promise<Array<{ id: number; name: string }>> {
  const { data } = await api.get("/employees/reporting-managers");
  return data;
}

import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { peopleBase, type Destinations } from "./peopleTypes";

export const membershipOptionsKey = ["pms-membership-options"];
export function useMembershipOptions(enabled = true) {
  const user = useAuthStore(state => state.user);
  return useQuery({
    queryKey: [...membershipOptionsKey, user?.id, user?.access?.companyId],
    queryFn: async () => (await api.get<Destinations>(`${peopleBase}/options`)).data,
    enabled,
  });
}

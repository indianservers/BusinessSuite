import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { authApi } from "@/services/api";

export function useSignOut(_loginPath: string) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  return async () => {
    try {
      await authApi.logout();
    } catch {
      /* Local sign-out also works offline. */
    } finally {
      await queryClient.cancelQueries();
      useAuthStore.getState().logout();
      queryClient.clear();
      navigate("/login", { replace: true });
    }
  };
}

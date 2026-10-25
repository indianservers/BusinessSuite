import { Link } from "react-router-dom";
import { getInstalledAppKeys } from "../../appRegistry";
import { api } from "../../services/api";
import { useAuthStore } from "../../store/authStore";
import {
  UnifiedProfile,
  ProfileManagement,
  type ProfileRequest,
} from "./UnifiedProfile";

export const profileRequest: ProfileRequest = async (path, options) =>
  (
    await api.request({
      url: path,
      method: options?.method || "GET",
      data: options?.body,
    })
  ).data;

export default function SharedProfilePage({
  employeeId,
}: {
  employeeId?: number;
}) {
  const user = useAuthStore((state) => state.user);
  return (
    <div>
      <UnifiedProfile
        request={profileRequest}
        employeeId={employeeId}
        onSaved={() => {
          if (!employeeId || employeeId === user?.employee_id)
            api
              .get("/auth/me")
              .then(({ data }) => {
                const current = useAuthStore.getState().user;
                if (current)
                  useAuthStore.getState().setUser({
                    ...current,
                    name:
                      data.name ||
                      data.full_name ||
                      data.display_name ||
                      current.name,
                  });
              })
              .catch(() => {});
        }}
      />
      {!employeeId && getInstalledAppKeys().includes("hrms") && (
        <div className="up-root up-actions">
          <Link className="up-button" to="/hrms/profile/security">
            Account security, photo & HR documents
          </Link>
          {user?.is_superuser ||
          ["admin", "hr", "manager"].includes(user?.role || "") ? (
            <Link className="up-button" to="/hrms/profile-management">
              Manage people profiles
            </Link>
          ) : null}
        </div>
      )}
    </div>
  );
}

export function SharedProfileManagementPage() {
  return <ProfileManagement request={profileRequest} />;
}

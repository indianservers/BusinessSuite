import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  ChevronDown,
  CircleHelp,
  LogOut,
  Settings,
  UserRound,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useState } from "react";
import { useAuthStore } from "@/store/authStore";
import { useSignOut } from "@/hooks/use-sign-out";

export default function SuiteProfileMenu() {
  const user = useAuthStore((s) => s.user);
  const signOut = useSignOut("/login");
  const [busy, setBusy] = useState(false);
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger
        className="suite-profile-trigger"
        aria-label="Open account menu"
      >
        <span className="md-avatar">
          {(user?.name || user?.email || "S").charAt(0).toUpperCase()}
        </span>
        <span className="md-account-details">
          <strong>{user?.email}</strong>
          <small>{user?.access?.companyName || "Business workspace"}</small>
        </span>
        <ChevronDown size={16} />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content className="suite-menu" align="end" sideOffset={8}>
          <DropdownMenu.Label className="suite-menu-label">
            {user?.email}
          </DropdownMenu.Label>
          <DropdownMenu.Item asChild>
            <Link to="/account">
              <UserRound size={17} />
              My profile
            </Link>
          </DropdownMenu.Item>
          <DropdownMenu.Item asChild>
            <Link to="/settings">
              <Settings size={17} />
              Settings
            </Link>
          </DropdownMenu.Item>
          <DropdownMenu.Item asChild>
            <Link to="/help">
              <CircleHelp size={17} />
              Help & support
            </Link>
          </DropdownMenu.Item>
          <DropdownMenu.Separator className="suite-menu-divider" />
          <DropdownMenu.Item
            disabled={busy}
            onSelect={() => {
              setBusy(true);
              void signOut();
            }}
          >
            <LogOut size={17} />
            {busy ? "Signing out…" : "Sign out"}
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

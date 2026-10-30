import SuiteNotificationBell from "@/components/suite/SuiteNotificationBell";
import PageRefreshButton from "@/components/app/PageRefreshButton";
import RefreshPagesCatalog from "@/components/app/RefreshPagesCatalog";
import DensityControl from "./DensityControl";
import PMSProfileMenu from "./PMSProfileMenu";
import { useSignOut } from "@/hooks/use-sign-out";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Briefcase, Eye, EyeOff, KeyRound, LayoutDashboard, LogOut, Menu, Moon, Sun, UserCircle } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import ModuleNewMenu from "@/components/app/ModuleNewMenu";
import GlobalSearch from "@/components/app/GlobalSearch";
import KeyboardShortcuts from "@/components/app/KeyboardShortcuts";
import { useThemeStore } from "@/store/themeStore";
import { useAuthStore } from "@/store/authStore";
import { getRoleLabel } from "@/lib/roles";
import { BUSINESS_SUITE_DISPLAY_NAME, getProductDisplayName, getProductForContext } from "@/lib/products";
import { authApi } from "@/services/api";
import { toast } from "@/hooks/use-toast";

interface TopbarProps {
  onMenuClick: () => void;
}

// Keep legacy approval/helpdesk invalidations connected to the shared inbox.
export const NOTIF_UNREAD_KEY = ["suite-notifications"];

export default function Topbar({ onMenuClick }: TopbarProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const { theme, setTheme } = useThemeStore();
  const { user } = useAuthStore();
  const product = getProductForContext(location.pathname, user?.role, user?.is_superuser);
  function openOperator(){
    const params=new URLSearchParams(location.search);
    const prefix=location.pathname.split('/')[1];
    const focus:Record<string,string>={hrms:'HRMS',crm:'CRM',srm:'SRM',fam:'FAM',pms:'PMS'};
    if(focus[prefix])params.set('module',focus[prefix]);
    navigate(`/ai-agents/operator?${params.toString()}`);
  }
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const roleLabel = getRoleLabel(user?.role, user?.is_superuser);
  const initials = user?.name ? getNameInitials(user.name) : user?.email?.slice(0, 2).toUpperCase() || "?";
  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");
  const handleLogout = useSignOut(product.loginPath);
  const isHrms = location.pathname.startsWith("/hrms");
  const isCrm = location.pathname.startsWith("/crm");
  const profilePath = isHrms ? "/hrms/profile" : isCrm ? "/crm/profile" : location.pathname.startsWith("/srm") ? "/srm/profile" : location.pathname.startsWith("/fam") ? "/fam/profile" : "/pms/profile";
  const selfServicePath = isHrms ? "/hrms/ess" : profilePath;
  const changePassword = useMutation({
    mutationFn: () => authApi.changePassword(currentPassword, newPassword),
    onSuccess: () => {
      toast({ title: "Password changed" });
      setPasswordDialogOpen(false);
      setCurrentPassword("");
      setNewPassword("");
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast({
        title: "Unable to change password",
        description: detail || "Please check the current password and password policy.",
        variant: "destructive",
      });
    },
  });
  const submitPasswordChange = (event: FormEvent) => {
    event.preventDefault();
    changePassword.mutate();
  };
  const passwordStrength = getPasswordStrength(newPassword);

  return (
    <header className="kf-topbar z-40 flex h-16 shrink-0 items-center gap-4 border-b bg-background/95 backdrop-blur px-4 md:px-6 lg:px-8">
      {/* Mobile menu button */}
      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 lg:hidden"
        aria-label="Open navigation" onClick={onMenuClick}
      >
        <Menu className="h-5 w-5" />
      </Button>

      <div className="flex min-w-0 flex-1 [&>button]:min-w-0 [&>button]:max-w-full"><GlobalSearch /></div>

      <div className="ml-auto flex shrink-0 items-center gap-2">
        <span className="hidden sm:contents">{location.pathname !== "/hrms/interns/applications" && <PageRefreshButton compact />}<RefreshPagesCatalog /></span>
        <ModuleNewMenu />
        <Button className="hidden sm:inline-flex" variant="outline" size="sm" onClick={openOperator} aria-label="Open suite AI operator"><span className="text-emerald-600">✦</span><span>AI operator</span></Button>
        <div className="hidden max-w-48 truncate rounded-full border bg-muted/40 px-3 py-1 text-xs font-medium text-muted-foreground xl:block">
          {BUSINESS_SUITE_DISPLAY_NAME} / {getProductDisplayName(product)}
        </div>
        <SuiteNotificationBell />
        <span className="hidden sm:contents"><KeyboardShortcuts /><DensityControl /></span>

        {/* Theme toggle */}
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
        >
          {theme === "dark" ? (
            <Sun className="h-5 w-5" />
          ) : (
            <Moon className="h-5 w-5" />
          )}
        </Button>

        <Dialog.Root open={passwordDialogOpen} onOpenChange={setPasswordDialogOpen}>
        {!location.pathname.startsWith("/pms") && <Button className="hidden sm:inline-flex" variant="ghost" size="sm" onClick={() => void handleLogout()}><LogOut className="h-4 w-4" /><span>Logout</span></Button>}
        {location.pathname.startsWith("/pms") ? <PMSProfileMenu onChangePassword={() => setPasswordDialogOpen(true)} /> : <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button aria-label="Account menu" className="flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                {initials}
              </div>
              <span className="hidden max-w-32 truncate text-sm font-medium md:block">
                {user?.email?.split("@")[0]}
              </span>
              <span className="hidden rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground xl:block">
                {roleLabel}
              </span>
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content align="end" sideOffset={8} className="z-50 min-w-56 rounded-md border bg-popover p-1 text-popover-foreground shadow-md">
              <div className="px-3 py-2">
                <p className="truncate text-sm font-medium">{user?.email}</p>
                <p className="text-xs text-muted-foreground">{roleLabel}</p>
              </div>
              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              <DropdownMenu.Item className="flex cursor-pointer items-center gap-2 rounded-sm px-3 py-2 text-sm outline-none hover:bg-accent" onSelect={() => navigate(profilePath)}>
                <UserCircle className="h-4 w-4" />
                My Profile
              </DropdownMenu.Item>
              <DropdownMenu.Item className="flex cursor-pointer items-center gap-2 rounded-sm px-3 py-2 text-sm outline-none hover:bg-accent" onSelect={() => navigate(selfServicePath)}>
                {isHrms ? <LayoutDashboard className="h-4 w-4" /> : <Briefcase className="h-4 w-4" />}
                {isHrms ? "ESS Portal" : "Workspace"}
              </DropdownMenu.Item>
              <DropdownMenu.Item className="flex cursor-pointer items-center gap-2 rounded-sm px-3 py-2 text-sm outline-none hover:bg-accent" onSelect={() => setPasswordDialogOpen(true)}>
                <KeyRound className="h-4 w-4" />
                Change Password
              </DropdownMenu.Item>
              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              <DropdownMenu.Item className="flex cursor-pointer items-center gap-2 rounded-sm px-3 py-2 text-sm text-red-600 outline-none hover:bg-red-50" onSelect={handleLogout}>
                <LogOut className="h-4 w-4" />
                Logout
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>}
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg border bg-background p-6 shadow-xl">
            <Dialog.Title className="text-lg font-semibold">Change Password</Dialog.Title>
            <Dialog.Description className="mt-1 text-sm text-muted-foreground">
              Enter your current password and choose a new one.
            </Dialog.Description>
            <form className="mt-5 space-y-4" onSubmit={submitPasswordChange}>
              <div className="space-y-1.5">
                <Label htmlFor="current-password">Current Password</Label>
                <div className="relative">
                  <Input id="current-password" type={showCurrentPassword ? "text" : "password"} value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required className="pr-10" />
                  <button type="button" className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" onClick={() => setShowCurrentPassword((value) => !value)}>
                    {showCurrentPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="new-password">New Password</Label>
                <div className="relative">
                  <Input id="new-password" type={showNewPassword ? "text" : "password"} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required className="pr-10" />
                  <button type="button" className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" onClick={() => setShowNewPassword((value) => !value)}>
                    {showNewPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                <div className="space-y-1">
                  <div className="flex gap-1">
                    {[0, 1, 2].map((index) => (
                      <span
                        key={index}
                        className={`h-1.5 flex-1 rounded-full ${index < passwordStrength.level ? passwordStrength.color : "bg-muted"}`}
                      />
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground">{passwordStrength.label}</p>
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Dialog.Close asChild>
                  <Button type="button" variant="outline">Cancel</Button>
                </Dialog.Close>
                <Button type="submit" disabled={!currentPassword || !newPassword || changePassword.isPending}>
                  Save Password
                </Button>
              </div>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
        </Dialog.Root>
      </div>
    </header>
  );
}

function getNameInitials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] || ""}${parts[parts.length - 1][0] || ""}`.toUpperCase();
}

function getPasswordStrength(password: string) {
  if (!password) return { level: 0, label: "Use at least 8 characters with letters, numbers, and symbols.", color: "bg-muted" };
  let score = 0;
  if (password.length >= 8) score += 1;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score += 1;
  if (/\d/.test(password) || /[^A-Za-z0-9]/.test(password)) score += 1;
  if (score <= 1) return { level: 1, label: "Weak password", color: "bg-red-500" };
  if (score === 2) return { level: 2, label: "Medium password", color: "bg-amber-500" };
  return { level: 3, label: "Strong password", color: "bg-emerald-500" };
}

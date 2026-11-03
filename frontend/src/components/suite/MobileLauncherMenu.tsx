import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { CircleHelp, Home, LayoutGrid, Menu, Settings, UserRound, X } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { modules } from "@/lib/moduleCatalog";
import { canAccessRoute } from "@/lib/roles";
import CompanySwitcher from "./CompanySwitcher";
import BranchSwitcher from "./BranchSwitcher";
import "./mobile-launcher.css";

export default function MobileLauncherMenu() {
  const [open, setOpen] = useState(false);
  const { user, isAuthenticated, isHydrated } = useAuthStore();
  const authenticated = isHydrated && isAuthenticated;
  const location = useLocation();
  useEffect(() => {
    const media = window.matchMedia("(max-width: 760px)");
    const closeOnDesktop = () => { if (!media.matches) setOpen(false); };
    media.addEventListener("change", closeOnDesktop);
    return () => media.removeEventListener("change", closeOnDesktop);
  }, []);
  const home = authenticated ? "/dashboard" : "/";
  const allowed = authenticated && user?.access
    ? modules.filter(m => canAccessRoute(m.homePath, user.role, user.is_superuser))
    : [];
  return <Dialog.Root open={open} onOpenChange={setOpen}>
    <Dialog.Trigger className="mobile-launcher-trigger" aria-label="Open mobile menu"><Menu size={23} /></Dialog.Trigger>
    <Dialog.Portal>
      <Dialog.Overlay className="mobile-launcher-overlay" />
      <Dialog.Content className="mobile-launcher-drawer">
        <div className="mobile-launcher-drawer-heading">
          <div><Dialog.Title>Business Suite</Dialog.Title><Dialog.Description>{authenticated ? "Your workspace, in one place." : "Explore your connected workspace."}</Dialog.Description></div>
          <Dialog.Close aria-label="Close mobile menu"><X size={22} /></Dialog.Close>
        </div>
        <nav aria-label="Mobile workspace menu" onClick={event => { if ((event.target as HTMLElement).closest("a")) setOpen(false); }}>
          <Link to={home}><Home size={20} /> Home</Link>
          {authenticated && <div className="mobile-launcher-context"><CompanySwitcher /><BranchSwitcher /></div>}
          {!!allowed.length && <p className="mobile-launcher-label">YOUR APPLICATIONS</p>}
          {allowed.map(m => <Link key={m.key} to={m.homePath}><m.icon size={20} />{m.name}</Link>)}
          {authenticated && <><p className="mobile-launcher-label">WORKSPACE</p><Link to="/settings"><Settings size={20} /> Settings</Link><Link to="/account"><UserRound size={20} /> My profile</Link></>}
          <Link to="/help"><CircleHelp size={20} /> Help & support</Link>
          {!authenticated && <Link to="/login"><UserRound size={20} /> Sign in</Link>}
        </nav>
      </Dialog.Content>
    </Dialog.Portal>
    {authenticated && location.pathname === "/dashboard" && <nav className="mobile-launcher-bottom" aria-label="Mobile dashboard navigation">
      <Link to="/dashboard" aria-current="page"><Home size={22} /><span>Home</span></Link>
      <a href="#md-applications"><LayoutGrid size={22} /><span>Apps</span></a>
      <button onClick={() => setOpen(true)}><Menu size={23} /><span>Menu</span></button>
      <Link to="/account"><UserRound size={22} /><span>Profile</span></Link>
    </nav>}
  </Dialog.Root>;
}

import ModuleNavigation from "./ModuleNavigation";

export default function PMSNavigationMenu(props: { workspaceId?: number; collapsed: boolean; onNavigate: () => void }) {
  return <ModuleNavigation {...props} modulePath="/pms" />;
}

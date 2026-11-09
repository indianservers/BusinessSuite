import { Layers3, FolderKanban, Users, ShoppingCart, ContactRound, Landmark, Settings2, Code2, FileText, BarChart3 } from "lucide-react";
export const workspaceIcons = [
  { id: "layers", label: "General", keywords: "workspace space layers", icon: Layers3 },
  { id: "folder", label: "Projects", keywords: "project folder delivery", icon: FolderKanban },
  { id: "team", label: "Teams", keywords: "team people employees", icon: Users },
  { id: "sales", label: "Sales", keywords: "sales orders shopping", icon: ShoppingCart },
  { id: "customers", label: "Customers", keywords: "customers leads contacts", icon: ContactRound },
  { id: "finance", label: "Finance", keywords: "finance bank accounting", icon: Landmark },
  { id: "operations", label: "Operations", keywords: "operations settings", icon: Settings2 },
  { id: "technology", label: "Technology", keywords: "technology software code", icon: Code2 },
  { id: "documents", label: "Documents", keywords: "documents files notes", icon: FileText },
  { id: "analytics", label: "Analytics", keywords: "analytics reports charts", icon: BarChart3 },
];
export const workspaceAccentColors = ["#7632ff", "#1671ff", "#168354", "#bd6500", "#c82f79", "#008596"];
export const workspaceIcon = (id?: string) => workspaceIcons.find(item => item.id === id)?.icon || Layers3;

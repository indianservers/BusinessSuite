import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { useState, type CSSProperties, type ElementType } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BookOpen, CheckSquare, ChevronRight, Copy, ExternalLink, FileText, Folder, Link2, MoreHorizontal, Palette, Pencil, Plus, RotateCcw, Settings2, SlidersHorizontal, Sparkles, Star, Upload, Users, Workflow, type LucideIcon } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { useAuthStore } from "@/store/authStore";
import { defaultSuitePreferences, suiteScope, useSuitePreferences } from "@/store/suitePreferences";
import { toast } from "@/hooks/use-toast";
import type { NewAction } from "@/components/app/NewMenu";
import type { RoleNavItem } from "@/lib/roles";
import "./menu-item-more.css";

export const menuIcons: Record<string, LucideIcon> = { folder: Folder, task: CheckSquare, people: Users, document: FileText, workflow: Workflow, sparkle: Sparkles };
const colors = { default: "", purple: "#7c3aed", blue: "#2563eb", green: "#15803d", orange: "#b45309", pink: "#be185d" };
const rootPath = (path: string) => path.split(/[?#]/)[0];

export function MenuItemIcon({ path, fallback: Fallback, size = 17 }: { path: string; fallback: ElementType; size?: number }) {
  const user = useAuthStore(s => s.user);
  const appearance = useSuitePreferences(s => s.contexts[suiteScope(user?.id, user?.access?.companyId)]?.menuItems?.[rootPath(path)]);
  const Icon = menuIcons[appearance?.icon || ""] || Fallback;
  return <Icon size={size} style={{ color: colors[appearance?.color as keyof typeof colors] || undefined }} />;
}

/** Navigation actions only. Business records retain their domain-specific action controls. */
export default function MenuItemMore({ path, paths = [path], label, originalLabel = label, actions = [], available = [], onNavigate }: {
  path: string; paths?: string[]; label: string; originalLabel?: string; actions?: NewAction[]; available?: RoleNavItem[]; onNavigate: () => void;
}) {
  const user = useAuthStore(s => s.user), navigate = useNavigate();
  const scope = suiteScope(user?.id, user?.access?.companyId);
  const preferences = useSuitePreferences(s => s.contexts[scope] || defaultSuitePreferences);
  const update = useSuitePreferences(s => s.update);
  const key = rootPath(path), appearance = preferences.menuItems?.[key];
  const favorite = preferences.favorites.includes(path);
  const [editor, setEditor] = useState(false), [draft, setDraft] = useState({label:"",color:"default",icon:""});
  const matches = actions.filter(action => !action.disabled && action.menuPaths?.some(to => paths.some(candidate => rootPath(candidate) === to)));
  const go = (action: () => void) => { onNavigate(); requestAnimationFrame(action); };
  const module = key.split("/")[1];
  const related = [
    { label:"Automations", icon:Workflow, paths:[`/${module}/automation`, `/${module}/workflow-designer`, "/power-apps/automations"] },
    { label:"Custom fields", icon:SlidersHorizontal, paths:[`/${module}/custom-fields`, ...(module === "crm" ? ["/crm/settings"] : [])] },
    { label:"Task statuses & workflows", icon:CheckSquare, paths:module === "pms" ? ["/pms/workflows"] : [] },
    { label:"Templates", icon:BookOpen, paths:[`/${module}/templates`] },
    { label:"Import & export", icon:Upload, paths:[`/${module}/import-export`, `/${module}/import-data`] },
    { label:"Settings", icon:Settings2, paths:[`/${module}/settings`] },
  ].flatMap(option => {
    const destination = option.paths.map(to => available.find(item => rootPath(item.to) === to)).find(Boolean);
    return destination && rootPath(destination.to) !== key ? [{...option,to:destination.to}] : [];
  });
  const edit = () => { setDraft({label:appearance?.label || originalLabel,color:appearance?.color || "default",icon:appearance?.icon || ""}); setEditor(true); };
  const save = (reset = false) => {
    const current = useSuitePreferences.getState().contexts[scope] || defaultSuitePreferences;
    const menuItems = {...current.menuItems};
    if (reset) delete menuItems[key]; else menuItems[key] = {label:draft.label.trim().slice(0,60) || originalLabel,color:draft.color,icon:draft.icon};
    update(scope,{menuItems}); setEditor(false);
  };
  return <>
    <Dropdown.Root modal={false}><Dropdown.Trigger className="module-menu-more" aria-label={`More options for ${label}`} title={`More options for ${label}`}><MoreHorizontal size={16}/></Dropdown.Trigger>
      <Dropdown.Portal><Dropdown.Content className="suite-item-menu" side="right" align="start" sideOffset={7} collisionPadding={10}>
        <Dropdown.Label>{label}</Dropdown.Label>
        <Dropdown.Item onSelect={() => {const current=useSuitePreferences.getState().contexts[scope] || defaultSuitePreferences;update(scope,{favorites:favorite?current.favorites.filter(to=>to!==path):[...current.favorites,path]});}}><Star size={15} fill={favorite?"currentColor":"none"}/>{favorite?"Remove from favorites":"Add to favorites"}</Dropdown.Item>
        <Dropdown.Item onSelect={() => requestAnimationFrame(edit)}><Pencil size={15}/>Rename menu item</Dropdown.Item>
        <Dropdown.Item onSelect={() => {void navigator.clipboard.writeText(new URL(path,window.location.origin).href).then(()=>toast({title:"Link copied"})).catch(()=>toast({title:"Could not copy link",description:"Open the page and copy its address.",variant:"destructive"}));}}><Copy size={15}/>Copy link</Dropdown.Item>
        <Dropdown.Item asChild><Link to={path} target="_blank" rel="noopener noreferrer"><ExternalLink size={15}/>Open in new tab</Link></Dropdown.Item>
        {matches.length > 0 && <><Dropdown.Separator/><Dropdown.Sub><Dropdown.SubTrigger><Plus size={15}/>Create new<ChevronRight size={13}/></Dropdown.SubTrigger><Dropdown.Portal><Dropdown.SubContent className="suite-item-menu" sideOffset={5} collisionPadding={10}>{matches.map(action=><Dropdown.Item key={action.label} onSelect={()=>go(action.onSelect)}><action.icon size={15}/>{action.label}</Dropdown.Item>)}</Dropdown.SubContent></Dropdown.Portal></Dropdown.Sub></>}
        <Dropdown.Item onSelect={() => requestAnimationFrame(edit)}><Palette size={15}/>Color & icon</Dropdown.Item>
        {related.length > 0 && <Dropdown.Separator/>}{related.map(option=><Dropdown.Item key={option.label} onSelect={()=>go(()=>navigate(option.to))}><option.icon size={15}/>{option.label}</Dropdown.Item>)}
        <Dropdown.Separator/><Dropdown.Item onSelect={()=>go(()=>navigate(path))}><Link2 size={15}/>Open page</Dropdown.Item>
      </Dropdown.Content></Dropdown.Portal>
    </Dropdown.Root>
    <Dialog open={editor} onOpenChange={setEditor}><DialogContent className="max-w-sm"><DialogTitle>Customize menu item</DialogTitle><p className="text-sm text-muted-foreground">Personal to your account and company in this browser. The underlying page and business records keep their names.</p><form className="space-y-4" onSubmit={event=>{event.preventDefault();save();}}><label className="block space-y-1 text-sm">Menu name<Input autoFocus aria-label="Menu name" required maxLength={60} value={draft.label} onChange={event=>setDraft({...draft,label:event.target.value})}/></label><label className="block space-y-1 text-sm">Icon<NativeSelect aria-label="Menu icon" value={draft.icon} onChange={event=>setDraft({...draft,icon:event.target.value})}><option value="">Default icon</option>{Object.keys(menuIcons).map(icon=><option key={icon} value={icon}>{icon.charAt(0).toUpperCase()+icon.slice(1)}</option>)}</NativeSelect></label><fieldset><legend className="mb-2 text-sm">Icon color</legend><div className="suite-menu-swatches">{Object.entries(colors).map(([color,value])=><button key={color} type="button" aria-label={`${color} menu color`} aria-pressed={draft.color===color} style={{"--swatch":value||"hsl(var(--muted-foreground))"} as CSSProperties} onClick={()=>setDraft({...draft,color})}/>)}</div></fieldset><footer className="flex justify-between gap-2"><Button type="button" variant="ghost" onClick={()=>save(true)}><RotateCcw size={14}/>Reset</Button><Button type="submit">Save menu item</Button></footer></form></DialogContent></Dialog>
  </>;
}

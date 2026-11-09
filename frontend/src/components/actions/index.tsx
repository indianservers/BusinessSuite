import { cloneElement, forwardRef, isValidElement, useState, type ReactElement, type ReactNode } from "react";
import * as Dropdown from "@radix-ui/react-dropdown-menu";
import * as Alert from "@radix-ui/react-alert-dialog";
import { AlertTriangle, ArrowRightLeft, CalendarClock, Clock3, GitMerge, Tag, Check, ClipboardCheck, Copy, Download, Ellipsis, Eye, FileText, Gauge, Loader2, Mail, MessageSquare, Pencil, Phone, Pin, Plus, RefreshCw, Save, ShieldCheck, Sparkles, StickyNote, Trash2, Upload, UserRound, Users, Play, X, ShoppingCart } from "lucide-react";
import { Button, type ButtonProps } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ActionTooltip } from "./ActionTooltip";
import "./actions.css";
export { ActionTooltip, ActionTooltipProvider } from "./ActionTooltip";

import { WhatsAppIcon } from "./BrandIcons";
export { WhatsAppIcon } from "./BrandIcons";
const definitions = {
  whatsapp: [WhatsAppIcon, "WhatsApp", "Send WhatsApp message", "whatsapp"],
  email: [Mail, "Email", "Compose email to this contact", "blue"],
  sms: [MessageSquare, "SMS", "Send SMS to this mobile number", "indigo"],
  call: [Phone, "Call", "Call this contact", "teal"],
  edit: [Pencil, "Edit", "Edit this record", "slate"],
  delete: [Trash2, "Delete", "Move this record to Trash", "red"],
  enrich: [Sparkles, "Enrich contact", "Enrich this contact with additional information", "purple"],
  score: [Gauge, "Recalculate score", "Recalculate lead score using current information", "amber"],
  convert: [ArrowRightLeft, "Convert Lead to Customer", "Convert this lead into a customer", "emerald"],
  quotation: [FileText, "Create Quotation", "Create a quotation for this record", "blue"],
  followup: [CalendarClock, "Follow-up", "Schedule the next follow-up", "orange"],
  more: [Ellipsis, "More actions", "Show all available actions", "purple"],
  note: [StickyNote, "Add note", "Add a note to this record", "slate"],
  task: [Plus, "Add task", "Create a related task", "purple"],
  view: [Eye, "View details", "Open full record details", "slate"],
  pin: [Pin, "Pin record", "Pin this record to your shortcuts", "slate"],
  profile: [UserRound, "View profile", "View this person's profile", "slate"],
  download: [Download, "Download", "Download this record", "emerald"],
  refresh: [RefreshCw, "Refresh", "Refresh the current information", "slate"],
  save: [Save, "Save", "Save your changes", "slate"],
  complete: [Check, "Complete", "Mark this item complete", "emerald"],
  review: [ClipboardCheck, "Submit for review", "Submit this work for review", "slate"],
  approve: [ShieldCheck, "Approve", "Review and approve this record", "emerald"],
  reject: [X, "Reject", "Review and reject this record", "red"],
  assign: [Users, "Assign", "Manage the people assigned to this record", "slate"],
  copy: [Copy, "Copy", "Copy this record", "orange"],
  upload: [Upload, "Upload", "Upload a file", "purple"],
  start: [Play, "Start work", "Start working on this task", "slate"],
  blocker: [AlertTriangle, "Report blocker", "Report a blocker preventing this work", "amber"],
  time: [Clock3, "Log time", "Record time spent on this work", "slate"],
  tag: [Tag, "Manage tags", "Manage tags for this record", "slate"],
  merge: [GitMerge, "Merge duplicates", "Review duplicate records before merging", "slate"],
  purchase: [ShoppingCart, "Create purchase", "Create a purchase for this supplier", "blue"],
} as const;
export type ActionKind = keyof typeof definitions;
export type ActionSpec = { id: string; kind: ActionKind; label?: string; tooltip?: string; onSelect?: () => void | Promise<unknown>; href?: string; available?: boolean; disabled?: boolean; disabledReason?: string; loading?: boolean; prominent?: boolean; primary?: boolean; danger?: boolean; iconOnly?: boolean; confirm?: { title: string; description: string; label?: string } };
export type ActionButtonProps = ButtonProps & { action: ActionKind; tooltip?: string; disabledReason?: string; loading?: boolean; iconOnly?: boolean; primary?: boolean };
export const ActionButton = forwardRef<HTMLButtonElement, ActionButtonProps>(function ActionButton({ action, tooltip, disabledReason, loading, iconOnly, primary, children, className, disabled, asChild = false, ...props }, ref) {
  const [Icon, label, description, tone] = definitions[action];
  const text = typeof children === "string" ? children : label;
  const help = disabledReason || tooltip || description;
  const glyph = loading ? <Loader2 className="animate-spin" aria-hidden="true"/> : <Icon aria-hidden="true"/>;
  const content = asChild && isValidElement(children)
    ? cloneElement(children as ReactElement<{children?: ReactNode}>, {}, <>{glyph}{!iconOnly && <span>{(children.props as {children?: ReactNode}).children}</span>}</>)
    : <>{glyph}{!iconOnly && <span>{children || label}</span>}</>;
  const button = <Button ref={ref} type="button" variant={primary ? "default" : "outline"} {...props} asChild={asChild} disabled={disabled || loading} aria-label={props["aria-label"] || (iconOnly ? text : undefined)} aria-busy={loading || undefined} data-action={action} className={cn("suite-action", `suite-action-${tone}`, primary && "suite-action-primary", iconOnly && "suite-action-icon", className)}>{content}</Button>;

  return <ActionTooltip content={help}>{disabled || loading ? <span className="suite-action-disabled" tabIndex={0} role="group" aria-label={`${text}: ${help}`}>{button}</span> : button}</ActionTooltip>;
});
export const IconActionButton = forwardRef<HTMLButtonElement, Omit<ActionButtonProps, "iconOnly">>(function IconActionButton(props, ref) { return <ActionButton {...props} ref={ref} iconOnly/>; });
export function ConfirmActionDialog({ open, onOpenChange, title, description, label = "Confirm", onConfirm }: { open: boolean; onOpenChange: (open: boolean) => void; title: string; description: string; label?: string; onConfirm: () => void }) {
  return <Alert.Root open={open} onOpenChange={onOpenChange}><Alert.Portal><Alert.Overlay className="fixed inset-0 z-[120] bg-black/45 backdrop-blur-sm"/><Alert.Content className="fixed left-1/2 top-1/2 z-[121] w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border bg-background p-6 shadow-2xl"><div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-red-50 text-red-700"><Trash2 size={20}/></div><Alert.Title className="text-lg font-semibold">{title}</Alert.Title><Alert.Description className="mt-2 text-sm leading-relaxed text-muted-foreground">{description}</Alert.Description><div className="mt-6 flex justify-end gap-2"><Alert.Cancel asChild><ActionButton action="reject" tooltip="Cancel and keep this record" className="suite-action-neutral">Cancel</ActionButton></Alert.Cancel><Alert.Action asChild><ActionButton action="delete" tooltip={label} onClick={onConfirm}>{label}</ActionButton></Alert.Action></div></Alert.Content></Alert.Portal></Alert.Root>;
}
function ActionItem({ action, run }: { action: ActionSpec; run: (action: ActionSpec) => void }) {
  const [Icon, label, description] = definitions[action.kind];
  return <ActionTooltip content={action.disabledReason || action.tooltip || description}><Dropdown.Item disabled={action.disabled || action.loading} onSelect={() => run(action)} data-action={action.kind} className={cn("suite-more-item", action.danger && "suite-more-danger")}><Icon aria-hidden="true"/><span>{action.label || label}{action.disabledReason && <small>{action.disabledReason}</small>}</span>{action.loading && <Loader2 className="animate-spin"/>}</Dropdown.Item></ActionTooltip>;
}
export function MoreActionsMenu({ actions, onAction, label = "More actions", triggerLabel, open, onOpenChange }: { actions: ActionSpec[]; onAction?: (action: ActionSpec) => void; label?: string; triggerLabel?: string; open?: boolean; onOpenChange?: (open: boolean) => void }) {
  const run = onAction || ((action: ActionSpec) => { if (action.href) window.location.assign(action.href); else void action.onSelect?.(); });
  const regular = actions.filter(action => action.available !== false && !action.danger), danger = actions.filter(action => action.available !== false && action.danger);
  return <Dropdown.Root open={open} onOpenChange={onOpenChange}><Dropdown.Trigger asChild><ActionButton action="more" aria-label={label} tooltip="Show all available actions">{triggerLabel}</ActionButton></Dropdown.Trigger><Dropdown.Portal><Dropdown.Content sideOffset={6} align="end" collisionPadding={12} className="suite-more-menu"><Dropdown.Label className="suite-more-label">Record actions</Dropdown.Label>{regular.map(action => <ActionItem key={action.id} action={action} run={run}/>)}{danger.length > 0 && <><Dropdown.Separator className="my-1 border-t"/><Dropdown.Label className="suite-more-label text-red-700">Danger zone</Dropdown.Label>{danger.map(action => <ActionItem key={action.id} action={action} run={run}/>)}</>}<Dropdown.Arrow className="suite-more-arrow fill-background"/></Dropdown.Content></Dropdown.Portal></Dropdown.Root>;
}
export function ActionToolbar({ actions, label = "Record actions", className }: { actions: ActionSpec[]; label?: string; className?: string }) {
  const [confirm, setConfirm] = useState<ActionSpec | null>(null);
  const run = (action: ActionSpec) => { if (action.available === false || action.disabled || action.loading) return; if (action.confirm) { setConfirm(action); return; } if (action.href) window.location.assign(action.href); else void action.onSelect?.(); };
  const eligible = actions.filter(action => action.available !== false);
  const candidates = eligible.filter(action => (action.primary || action.prominent) && !action.danger);
  const primary = candidates.find(action => action.primary && !action.disabled) || candidates.find(action => !action.disabled) || candidates[0];
  const visible = primary ? [primary, ...candidates.filter(action => action !== primary).slice(0, 2)] : [];
  const secondary = eligible.filter(action => !visible.includes(action));
  return <><div role="group" aria-label={label} className={cn("suite-action-toolbar", className)}>{visible.map(action => <ActionButton key={action.id} action={action.kind} tooltip={action.tooltip} disabledReason={action.disabledReason} disabled={action.disabled} loading={action.loading} primary={action === primary} iconOnly={action.iconOnly} onClick={() => run(action)}>{action.label}</ActionButton>)}{secondary.length > 0 && <MoreActionsMenu actions={secondary} onAction={run}/>}</div>{confirm?.confirm && <ConfirmActionDialog open onOpenChange={open => { if (!open) setConfirm(null); }} {...confirm.confirm} onConfirm={() => { const action = eligible.find(item => item.id === confirm.id); setConfirm(null); if (!action || action.disabled || action.loading) return; if (action.href) window.location.assign(action.href); else void action.onSelect?.(); }}/>}</>;
}

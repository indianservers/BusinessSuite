import { ArrowRightLeft, CalendarClock, ClipboardCheck, Download, Ellipsis, Eye, FileText, Gauge, Mail, MessageSquare, Pencil, Phone, Pin, Plus, RefreshCw, Save, ShieldCheck, Sparkles, Trash2, Upload, Users, X } from "lucide-react";
import { WhatsAppIcon } from "@/components/actions/BrandIcons";
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "kf-button inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  available?: boolean;
}

const actionPresentation = [
  {match:/^send whatsapp$|^whatsapp$/i, icon:WhatsAppIcon, tone:"whatsapp", tooltip:"Send WhatsApp message"},
  {match:/^(send |compose )?email$/i, icon:Mail, tone:"blue", tooltip:"Compose email to this contact"},
  {match:/^(send )?sms$/i, icon:MessageSquare, tone:"indigo", tooltip:"Send SMS to this mobile number"},
  {match:/^call( contact)?$/i, icon:Phone, tone:"teal", tooltip:"Call this contact"},
  {match:/^edit\b/i, icon:Pencil, tone:"slate"},
  {match:/^delete\b|^move to trash$/i, icon:Trash2, tone:"red"},
  {match:/^enrich\b/i, icon:Sparkles, tone:"purple", tooltip:"Enrich this contact with additional information"},
  {match:/^recalculate score$/i, icon:Gauge, tone:"amber", tooltip:"Recalculate lead score using current information"},
  {match:/^convert lead/i, icon:ArrowRightLeft, tone:"emerald", tooltip:"Convert this lead into a customer"},
  {match:/^create quotation$|^draft invoice$/i, icon:FileText, tone:"blue"},
  {match:/^(add |schedule )?follow.up$/i, icon:CalendarClock, tone:"orange"},
  {match:/^more( actions)?$/i, icon:Ellipsis, tone:"slate"},
  {match:/^save\b/i, icon:Save, tone:"slate"},
  {match:/^cancel$|^close$/i, icon:X, tone:"slate"},
  {match:/^refresh\b|^retry$/i, icon:RefreshCw, tone:"slate"},
  {match:/^download\b|^export\b/i, icon:Download, tone:"slate"},
  {match:/^upload\b|^attach file$/i, icon:Upload, tone:"slate"},
  {match:/^view( details| profile| record)?$/i, icon:Eye, tone:"slate"},
  {match:/^pin record$/i, icon:Pin, tone:"slate", tooltip:"Pin this record to your shortcuts"},
  {match:/^assign\b|^manage assignments$/i, icon:Users, tone:"slate"},
  {match:/^approve\b|^confirm$/i, icon:ShieldCheck, tone:"emerald"},
  {match:/^submit\b/i, icon:ClipboardCheck, tone:"slate"},
  {match:/^add\b|^create\b|^new\b/i, icon:Plus, tone:"slate"},
];

function iconButtonLabel(children: React.ReactNode): string | undefined {
  const labels: Record<string, string> = {X:"Close", Ellipsis:"More actions", MoreHorizontal:"More actions", MoreVertical:"More actions", Pencil:"Edit record", Edit:"Edit record", Edit3:"Edit record", Trash2:"Move this record to Trash", RefreshCw:"Refresh information", Search:"Search", Download:"Download", Upload:"Upload", Copy:"Copy", ChevronLeft:"Previous", ChevronRight:"Next", ChevronsLeft:"First page", ChevronsRight:"Last page", Eye:"View details", Plus:"Add new", Check:"Confirm", Settings:"Settings", Filter:"Filter records", SlidersHorizontal:"Customize view", Bell:"Notifications", Menu:"Open navigation"};
  const items = React.Children.toArray(children);
  if (items.some(item => typeof item === "string" && item.trim())) return undefined;
  for (const child of items) {
    if (!React.isValidElement(child)) continue;
    const component = child.type as { displayName?: string };
    const name = component.displayName?.replace(/^Lucide/, "");
    if (name && labels[name]) return labels[name];
  }
  return undefined;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, available = true, ...props }, ref) => {
    if (!available) return null;
    const Comp = asChild ? Slot : "button";
    const plainLabel = typeof props.children === "string" ? props.children : undefined;
    const presentation = plainLabel ? actionPresentation.find(item => item.match.test(plainLabel.trim())) : undefined;
    const LeadingIcon = presentation?.icon;
    const content = LeadingIcon && !asChild ? <><LeadingIcon aria-hidden="true"/>{props.children}</> : props.children;
    const inferredLabel = !asChild && !props["aria-label"] ? props.title || iconButtonLabel(props.children) : undefined;
    const buttonProps = asChild || props.type || !props.onClick ? props : { type: "button" as const, ...props };
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        data-variant={variant || "default"}
        aria-label={props["aria-label"] || inferredLabel}
        data-action-tooltip={props.title || presentation?.tooltip || props["aria-label"] || inferredLabel}
        data-action-tone={presentation?.tone}
        {...buttonProps}
      >{content}</Comp>
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };

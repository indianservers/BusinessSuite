import { FocusScope } from "@radix-ui/react-focus-scope";
import { useRecordSync } from "@/shared/record-sync/store";
import { CompactFields, isEditorDialog } from "@/components/forms/CompactForm";
import * as React from "react";
import * as Primitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { CreationSurfaceContext } from "@/shared/creation/CreationSurfaceContext";
const DialogSyncContext=React.createContext<{open:boolean;background:boolean;modal:boolean;setElement:(node:HTMLElement|null)=>void}>({open:true,background:false,modal:true,setElement:()=>{}});
export function Dialog({open,defaultOpen,onOpenChange,modal=true,children,...props}:React.ComponentPropsWithoutRef<typeof Primitive.Root>){
 const [localOpen,setLocalOpen]=React.useState(defaultOpen||false),[element,setElement]=React.useState<HTMLElement|null>(null);
 const entries=useRecordSync(),foreground=open??localOpen,background=foreground&&entries.some(item=>item.origin===element&&item.phase==="pending");
 React.useEffect(()=>{if(background)requestAnimationFrame(()=>document.getElementById("suite-main")?.focus());},[background]);
 return <DialogSyncContext.Provider value={{open:foreground,background,modal,setElement}}><Primitive.Root {...props} modal={false} open={foreground&&!background} onOpenChange={value=>{if(background)return;setLocalOpen(value);onOpenChange?.(value);}}>{children}</Primitive.Root></DialogSyncContext.Provider>;
}
export const DialogTitle = Primitive.Title;
export const DialogDescription = Primitive.Description;
export function DialogHeader(props: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...props}
      className={cn("mb-4 pr-8 text-lg font-semibold", props.className)}
    />
  );
}
export const DialogContent = React.forwardRef<
  React.ElementRef<typeof Primitive.Content>,
  React.ComponentPropsWithoutRef<typeof Primitive.Content> & { overlayClassName?: string }
>(({ className, children, overlayClassName, ...props }, ref) => {
  const state=React.useContext(DialogSyncContext);
  const attach=React.useCallback((node:HTMLDivElement|null)=>{state.setElement(node);if(typeof ref==="function")ref(node);else if(ref)ref.current=node;},[state.setElement,ref]);
  if(!state.open)return null;
  return <Primitive.Portal forceMount>
    {state.modal&&<div aria-hidden="true" style={state.background?{display:"none"}:undefined} className={cn("fixed inset-0 z-50 bg-black/40", overlayClassName)} />}
    <Primitive.Content
      forceMount
      ref={attach}
      aria-modal={state.modal&&!state.background}
      aria-describedby={undefined}
      {...props}
      style={state.background?{...props.style,display:"none"}:props.style}
      onEscapeKeyDown={event => {
        if (document.activeElement?.matches('[data-record-picker][aria-expanded="true"]')) { event.preventDefault(); return; }
        props.onEscapeKeyDown?.(event);
      }}
      className={cn(
        "fixed left-1/2 top-1/2 z-50 grid min-w-0 max-h-[calc(100dvh-2rem)] overflow-y-auto overscroll-contain w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 gap-4 rounded-xl border bg-background p-4 shadow-xl sm:p-6",
        className,
        isEditorDialog(children) && !props.style?.height && "max-h-[min(85dvh,44rem)]",
      )}
    >
      <FocusScope asChild trapped={state.modal&&!state.background} loop={state.modal&&!state.background}><div className="contents"><CreationSurfaceContext.Provider value={true}><CompactFields className="contents" enabled={isEditorDialog(children)}>{children}</CompactFields></CreationSurfaceContext.Provider>
      <Primitive.Close
        aria-label="Close dialog"
        className="absolute right-2 top-2 z-10 flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <X size={18} />
      </Primitive.Close></div></FocusScope>
    </Primitive.Content>
  </Primitive.Portal>;
});
DialogContent.displayName = "DialogContent";

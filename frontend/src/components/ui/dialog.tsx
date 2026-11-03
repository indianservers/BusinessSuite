import { CompactFields, isEditorDialog } from "@/components/forms/CompactForm";
import * as React from "react";
import * as Primitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
export const Dialog = Primitive.Root;
export const DialogTitle = Primitive.Title;
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
>(({ className, children, overlayClassName, ...props }, ref) => (
  <Primitive.Portal>
    <Primitive.Overlay className={cn("fixed inset-0 z-50 bg-black/40", overlayClassName)} />
    <Primitive.Content
      ref={ref}
      aria-describedby={undefined}
      {...props}
      className={cn(
        "fixed left-1/2 top-1/2 z-50 grid min-w-0 max-h-[calc(100dvh-2rem)] overflow-y-auto overscroll-contain w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 gap-4 rounded-xl border bg-background p-4 shadow-xl sm:p-6",
        className,
        isEditorDialog(children) && !props.style?.height && "max-h-[min(85dvh,44rem)]",
      )}
    >
      <CompactFields className="contents" enabled={isEditorDialog(children)}>{children}</CompactFields>
      <Primitive.Close
        aria-label="Close dialog"
        className="absolute right-2 top-2 z-10 flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <X size={18} />
      </Primitive.Close>
    </Primitive.Content>
  </Primitive.Portal>
));
DialogContent.displayName = "DialogContent";

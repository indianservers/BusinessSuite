import * as React from "react";
import * as Primitive from "@radix-ui/react-popover";
import { cn } from "@/lib/utils";

export const Popover = Primitive.Root;
export const PopoverTrigger = Primitive.Trigger;
export const PopoverAnchor = Primitive.Anchor;
export const PopoverContent = React.forwardRef<
  React.ElementRef<typeof Primitive.Content>,
  React.ComponentPropsWithoutRef<typeof Primitive.Content>
>(({ className, align = "center", sideOffset = 4, ...props }, ref) => (
  <Primitive.Portal>
    <Primitive.Content ref={ref} align={align} sideOffset={sideOffset}
      className={cn("z-[80] w-72 rounded-md border bg-popover p-4 text-popover-foreground shadow-md outline-none", className)}
      {...props}/>
  </Primitive.Portal>
));
PopoverContent.displayName = Primitive.Content.displayName;

import { useToast } from "@/hooks/use-toast";
import { useLayoutEffect, useState } from "react";
import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from "@/components/ui/toast";

export function Toaster() {
  const { toasts } = useToast();
  const [modalActive, setModalActive] = useState(false);
  useLayoutEffect(() => {
    const update = () => setModalActive(document.body.hasAttribute("data-scroll-locked") || !!document.querySelector(':is([role="dialog"], [role="alertdialog"])[aria-modal="true"]:not([hidden]):not([data-state="closed"])'));
    update();
    const observer = new MutationObserver(update);
    observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["aria-modal", "data-state", "hidden", "data-scroll-locked"] });
    return () => observer.disconnect();
  }, []);
  return (
    <ToastProvider>
      {/* CSS-hidden Radix toasts still consume Escape through their dismissable layers.
          Queue notices until the modal releases keyboard interaction. */}
      {!modalActive && toasts.filter(toast => toast.open !== false).map(function ({ id, title, description, action, ...props }) {
        return (
          <Toast key={id} {...props}>
            <div className="grid min-w-0 gap-1 break-words">
              {title && <ToastTitle>{title}</ToastTitle>}
              {description && <ToastDescription>{description}</ToastDescription>}
            </div>
            {action}
            <ToastClose />
          </Toast>
        );
      })}
      <ToastViewport />
    </ToastProvider>
  );
}

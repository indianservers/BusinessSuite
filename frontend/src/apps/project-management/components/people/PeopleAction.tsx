import { useId, type ButtonHTMLAttributes } from "react";

/** Disabled actions remain keyboard discoverable, with the exact reason. */
export default function PeopleAction({ reason, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { reason?: string }) {
  const id = useId();
  return <span className="pd-action-help" tabIndex={reason ? 0 : undefined} title={reason} aria-describedby={reason ? id : undefined}>
    <button type="button" {...props} disabled={!!reason || props.disabled}>{children}</button>
    {reason && <small id={id} role="tooltip">{reason}</small>}
  </span>;
}

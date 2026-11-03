import { Children, cloneElement, forwardRef, isValidElement, type ReactNode, type SelectHTMLAttributes } from "react";

type Props = SelectHTMLAttributes<HTMLSelectElement> & {
  loading?: boolean;
  error?: boolean;
  loadingText?: string;
  emptyText?: string;
};

function hasChoices(children: ReactNode): boolean {
  return Children.toArray(children).some(child => {
    if (!isValidElement<{ value?: unknown; children?: ReactNode }>(child)) return false;
    if (child.type === "option") return child.props.value !== "";
    return hasChoices(child.props.children);
  });
}

/** A native select: retains browser keyboard, form, styling and ref behavior. */
export const NativeSelect = forwardRef<HTMLSelectElement, Props>(function NativeSelect({
  children, loading = false, error = false, loadingText = "Loading choices…", emptyText = "No data found", ...props
}, ref) {
  const empty = !hasChoices(children);
  return <select {...props} ref={ref} aria-busy={loading || undefined}>
    {loading ? Children.map(children, child => isValidElement<{ value?: unknown; children?: ReactNode }>(child) && child.type === "option" && child.props.value === "" ? cloneElement(child, {}, loadingText) : child) : children}
    {(loading || error || empty) && <option disabled value="">
      {loading ? loadingText : error ? "Could not load choices" : emptyText}
    </option>}
  </select>;
});
// CompactForm recognizes this as a field, exactly as it does a native select.
NativeSelect.displayName = "select";

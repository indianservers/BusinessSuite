import { Children, cloneElement, forwardRef, isValidElement, useEffect, useId, useMemo, useRef, useState, type FormEvent, type FormHTMLAttributes, type ReactElement, type ReactNode } from "react";
import "./compact-forms.css";
import { useMobile } from "@/components/mobile/useMobile";

type Section = { id: string; label: string; content: ReactNode };
export function FormSectionTabs({ sections, active, onChange, label = "Form sections" }: { sections: Section[]; active: string; onChange: (id: string) => void; label?: string }) {
  const id = useId();
  return <div className="suite-form-sections"><div role="tablist" aria-label={label} className="suite-form-tabs" onKeyDown={event => { const index = sections.findIndex(section => section.id === active); const next = event.key === "ArrowRight" ? (index + 1) % sections.length : event.key === "ArrowLeft" ? (index - 1 + sections.length) % sections.length : event.key === "Home" ? 0 : event.key === "End" ? sections.length - 1 : -1; if (next >= 0) { event.preventDefault(); onChange(sections[next].id); event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus(); } }}>{sections.map(section => <button key={section.id} type="button" role="tab" id={`${id}-tab-${section.id}`} aria-controls={`${id}-panel-${section.id}`} aria-selected={active === section.id} tabIndex={active === section.id ? 0 : -1} onClick={() => onChange(section.id)}>{section.label}</button>)}</div>{sections.map(section => <section key={section.id} id={`${id}-panel-${section.id}`} role="tabpanel" aria-labelledby={`${id}-tab-${section.id}`} hidden={active !== section.id} className="suite-form-panel" style={active !== section.id ? { display: "none" } : undefined}>{section.content}</section>)}</div>;
}

type ElementProps = { children?: ReactNode; label?: string; title?: string; name?: string; placeholder?: string; className?: string; role?: string; type?: string; hidden?: boolean; style?: Record<string, unknown>; [key: string]: unknown };
const asElement = (node: ReactNode) => isValidElement<ElementProps>(node) ? node : null;
const componentName = (element: ReactElement<ElementProps>) => typeof element.type === "string" ? element.type : (element.type as { displayName?: string; name?: string }).displayName || (element.type as { name?: string }).name || "";
function text(node: ReactNode): string { return Children.toArray(node).map(value => typeof value === "string" || typeof value === "number" ? String(value) : asElement(value) ? text(asElement(value)!.props.children) : "").join(" ").trim(); }
function findHeading(nodes: ReactNode): string { for (const child of Children.toArray(nodes)) { const element = asElement(child); if (!element) continue; if (/^h[1-4]$|legend|CardTitle/i.test(componentName(element))) return text(element.props.children); const found = findHeading(element.props.children); if (found) return found; } return ""; }
function heading(element: ReactElement<ElementProps>): string {
  if (typeof element.props.title === "string" && element.props.children) return element.props.title.replace(/^\d+[.\s]+/, "");
  for (const child of Children.toArray(element.props.children)) { const node = asElement(child); if (!node) continue; const name = componentName(node); if (/^h[1-4]$|legend|CardTitle/i.test(name)) return text(node.props.children); if (/header|CardHeader/.test(name)) { const value = findHeading(node.props.children); if (value) return value; } }
  return "";
}
function category(label: string) {
  if (/^(name|title|type|code|sku|identifier|reference|first name|last name|full name|employee|task title)|\brequired\b/i.test(label)) return "Basic details";
  if (/email|phone|mobile|address|city|country|company|website|contact/i.test(label)) return "Contact & company";
  if (/price|amount|currency|tax|discount|salary|revenue|bank|payment|cost|rate|quantity/i.test(label)) return "Pricing & finance";
  if (/product|service|item|catalog/i.test(label)) return "Products & services";
  if (/note|description|comment|attachment|image|file/i.test(label)) return "Notes & extras";
  if (/owner|assignee|assigned|member|reviewer|team/i.test(label)) return "Basic details";
  if (/date|time|priority|status|stage|schedule|due/i.test(label)) return "Planning & ownership";
  return "Additional details";
}
// Feedback is not an input, even when it has a label for its loading message.
function isFormFeedback(element: ReactElement<ElementProps>) {
  const name = componentName(element), props = element.props;
  return props['data-form-feedback'] === true || props.role === 'status' || props.role === 'alert'
    || name === 'LoadingState' || (name === 'State' && ('isLoading' in props || 'isError' in props));
}
function analyse(children: ReactNode, phone = false) {
  const units = new Map<string, { label: string; section: string }>();
  const linkedLabels = new Map<string, {label:string;path:string}>(); const linkedInputs = new Map<string,string>();
  function labels(nodes:ReactNode,path:string) { Children.toArray(nodes).forEach((node,index) => { const element=asElement(node); if(!element)return; const key=`${path}.${index}`; if(typeof element.props.htmlFor === 'string') linkedLabels.set(element.props.htmlFor,{label:text(element.props.children),path:key}); if(typeof element.props.children !== 'function')labels(element.props.children,key); }); }
  labels(children,'root');
  let existingNavigation = false; let sectionCount = 0;
  function walk(nodes: ReactNode, path: string, section: string) {
    Children.toArray(nodes).forEach((node, index) => {
      const element = asElement(node); if (!element || element.props.hidden) return;
      const key = `${path}.${index}`, name = componentName(element), props = element.props;
      if (name === "aside" || (phone && isFormFeedback(element))) return;
      if (props.role === "tablist" || /(?:tabs|steps|wizard)/i.test(String(props.className || "")) || /(?:Tabs|FormSectionTabs|CompactForm)/.test(name) || name === "form") { existingNavigation = true; return; }
      if (name === "table") { sectionCount++; units.set(key, {label:"Line items",section:section || "Line items"}); return; }
      const sectionTitle = typeof props['data-form-section-label'] === "string" ? String(props['data-form-section-label']) : heading(element);
      if (sectionTitle && (name === "section" || name === "fieldset" || name === "Card" || (typeof element.type !== "string" && typeof props.title === "string") || props['data-form-section-label'])) {
        sectionCount++; units.set(key, { label: sectionTitle, section: sectionTitle }); return;
      }
      if (typeof props.htmlFor === "string" && /label/i.test(name)) return;
      const unit = name === "label" || typeof props.label === "string" || /^(input|select|textarea)$/.test(name) || /(?:Input|RichTextField)$/.test(name);
      if (unit && props.type !== "hidden" && props.type !== "checkbox" && props.type !== "radio") {
        const label = String(props.label || props['aria-label'] || (typeof props.id === "string" ? linkedLabels.get(props.id)?.label : undefined) || props.name || props.placeholder || text(props.children) || "Field");
        units.set(key, { label, section: section || category(label) }); if(typeof props.id === "string")linkedInputs.set(props.id,key); return;
      }
      walk(props.children, key, heading(element) || section);
    });
  }
  walk(children, "root", "");
  const groups: string[] = [], assignments = new Map<string, number>();
  // Keep related fields together; overflow categories share the third tab.
  const initialCategories = [...new Set([...units.values()].map(unit => unit.section))];
  const basic = initialCategories.find(label=>/basic|essential|overview|general/i.test(label)) || initialCategories[0];
  for(const unit of units.values())if(/^(?:\d+[. ]*)?(?:assignment|members|team members|ownership|people & access)$/i.test(unit.section))unit.section=basic;
  const categories = [...new Set([...units.values()].map(unit => unit.section))];
  const groupLabels = categories.length > 3 ? [...categories.slice(0, 2), "More details"] : categories;
  groups.push(...groupLabels);
  for (const [key, unit] of units) {
    assignments.set(key, Math.min(categories.indexOf(unit.section), 2));
  }
  for (const [id, key] of linkedInputs) { const label=linkedLabels.get(id),group=assignments.get(key); if(label && group !== undefined)assignments.set(label.path,group); }
  return { groups, assignments, enabled: !existingNavigation && (units.size >= 9 || sectionCount >= 2) && groups.length > 1 };
}

/** Native form semantics, refs and payloads are retained; only long unsectioned forms gain navigation. */
const CompactForm = forwardRef<HTMLFormElement, FormHTMLAttributes<HTMLFormElement> & { compactTabs?: boolean; renderAs?: "form" | "div" }>(({ children, className, compactTabs = true, renderAs = "form", onInvalidCapture, onInputCapture, onChangeCapture, onSubmit, ...props }, ref) => {
  const phone = useMobile(480);
  const plan = useMemo(() => analyse(children, phone), [children, phone]); const [active, setActive] = useState(0); const [validation, setValidation] = useState(""); const handlingInvalid = useRef(false); const id = useId(); const nativeForm = useRef<HTMLFormElement | null>(null);
  const enabled = compactTabs && plan.enabled, current = Math.min(active, Math.max(0, plan.groups.length - 1));
  const invalidField = useRef<HTMLInputElement | null>(null);
  const embeddedRoot = useRef<HTMLDivElement | null>(null);
  const [serverErrors, setServerErrors] = useState<number[]>([]);
  const groupSignature = plan.groups.join("\0");
  useEffect(() => {
    const root = renderAs === "div" ? embeddedRoot.current : nativeForm.current;
    if (!phone || !enabled || !root) { setServerErrors(previous => previous.length ? [] : previous); return; }
    let previousErrors = new Map<HTMLElement, string>();
    const scan = () => {
      const errors = [...root.querySelectorAll<HTMLElement>('[aria-invalid="true"], [role="alert"]')].filter(node =>
        node.closest('[data-compact-form]') === root && node.closest('[data-form-section]')
        && (node.getAttribute('aria-invalid') === 'true' || !!(node.textContent?.trim() || node.getAttribute('aria-label'))));
      const describedAlerts = new Set<HTMLElement>();
      for (const node of errors) if (node.getAttribute('aria-invalid') === 'true') {
        for (const id of (node.getAttribute('aria-describedby') || '').split(/\s+/)) {
          const message = id ? document.getElementById(id) : null;
          if (message && root.contains(message) && message.getAttribute('role') === 'alert') describedAlerts.add(message);
        }
      }
      const counts: number[] = [], nextErrors = new Map<HTMLElement, string>();
      let firstNew: { node: HTMLElement; group: number } | undefined;
      for (const node of errors) {
        const section = node.closest<HTMLElement>('[data-form-section]')!;
        const group = Number(section.dataset.formSection);
        const signature = `${group}:${node.getAttribute('aria-invalid')}:${node.textContent}:${node.getAttribute('aria-label')}`;
        nextErrors.set(node, signature);
        if (!describedAlerts.has(node)) counts[group] = (counts[group] || 0) + 1;
        if (!firstNew && previousErrors.get(node) !== signature) firstNew = { node, group };
      }
      previousErrors = nextErrors;
      setServerErrors(previous => previous.join(',') === counts.join(',') ? previous : counts);
      if (firstNew) {
        setActive(firstNew.group);
        // Expose an error inside an optional section without opening the keyboard.
        for (let ancestor = firstNew.node.parentElement; ancestor && ancestor !== root; ancestor = ancestor.parentElement)
          if (ancestor instanceof HTMLDetailsElement) ancestor.open = true;
      }
    };
    scan();
    const observer = new MutationObserver(scan);
    observer.observe(root, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['aria-invalid', 'aria-describedby', 'aria-label', 'role', 'data-form-section'] });
    return () => observer.disconnect();
  }, [phone, enabled, renderAs, groupSignature]);
  function clearResolvedValidation() {
    const field = invalidField.current;
    if (field && (!field.isConnected || field.validity.valid)) {
      invalidField.current = null;
      setValidation("");
    }
  }
  useEffect(() => {
    const root = renderAs === "div" && phone ? embeddedRoot.current : nativeForm.current;
    if (!root || !enabled) return;
    const target = root.closest('form') || root;
    const reveal = (event: Event) => {
      const field = (event as CustomEvent<HTMLElement>).detail;
      if (!(field instanceof HTMLElement) || !root.contains(field)) return;
      if (renderAs === "div" && field.closest('[data-compact-form]') !== root) return;
      const section = field.closest<HTMLElement>('[data-form-section]');
      if (section && root.contains(section)) setActive(Number(section.dataset.formSection));
    };
    target.addEventListener('suite:reveal-form-field', reveal);
    return () => target.removeEventListener('suite:reveal-form-field', reveal);
  }, [enabled, phone, renderAs, plan.groups]);
  function render(nodes: ReactNode, path: string): { nodes: ReactNode; groups: Set<number>; feedback: boolean } {
    const groups = new Set<number>();
    let feedback = false;
    const result = Children.toArray(nodes).map((node, index) => {
      const element = asElement(node); if (!element) return node;
      if (phone && isFormFeedback(element)) { feedback = true; return element; }
      const key = `${path}.${index}`, group = plan.assignments.get(key);
      if (group !== undefined) {
        groups.add(group); const hidden = group !== current;
        const attrs = { 'data-form-section': group, hidden, style: hidden ? { ...element.props.style, display: "none" } : element.props.style };
        return typeof element.type === "string" ? cloneElement(element, attrs) : <div key={element.key || key} {...attrs} style={{ display: hidden ? "none" : "contents" }}>{element}</div>;
      }
      if (!element.props.children || typeof element.props.children === "function") return element;
      const child = render(element.props.children, key); child.groups.forEach(value => groups.add(value));
      feedback ||= child.feedback;
      if (!child.groups.size) return element;
      const nextChildren = !Array.isArray(element.props.children) && Children.count(element.props.children) === 1 ? Children.toArray(child.nodes)[0] : child.nodes;
      const copy = cloneElement(element, { children: nextChildren });
      if (child.groups.size && typeof element.type !== "string") return <div key={element.key || key} style={{ display: (child.feedback || child.groups.has(current)) ? "contents" : "none" }}>{copy}</div>;
      if (child.groups.size && !child.feedback && !child.groups.has(current)) return cloneElement(copy, { hidden: true, style: { ...element.props.style, display: "none" } });
      return copy;
    });
    return { nodes: result, groups, feedback };
  }
  function invalid(event: FormEvent<HTMLElement>) {
    onInvalidCapture?.(event as FormEvent<HTMLFormElement>); if (!enabled || event.defaultPrevented) return;
    const field = event.target as HTMLInputElement, section = field.closest<HTMLElement>('[data-form-section]');
    const root = renderAs === "div" && phone ? embeddedRoot.current : nativeForm.current;
    if (!section || !root?.contains(field)) return;
    if (renderAs === "div" ? field.closest('[data-compact-form]') !== root : field.form !== nativeForm.current) return;
    event.preventDefault(); if (handlingInvalid.current) return;
    handlingInvalid.current = true; invalidField.current = field; const index = Number(section.dataset.formSection); setActive(index); setValidation(`Check ${plan.groups[index]}: ${field.validationMessage || "complete the highlighted field"}`);
    requestAnimationFrame(() => { field.focus(); handlingInvalid.current = false; });
  }
  const content = <>{enabled && <><nav className="suite-form-tabs suite-auto-form-tabs" aria-label="Form sections">{plan.groups.map((label, index) => <button key={`${id}-${label}`} type="button" aria-pressed={current === index} onClick={() => { setActive(index); setValidation(""); }}>{label}{phone && serverErrors[index] > 0 && <span className="suite-form-error-count" aria-label={`${serverErrors[index]} errors`}>{serverErrors[index]}</span>}</button>)}</nav>{validation && <p role="alert" className="suite-form-validation">{validation}</p>}</>}{enabled ? render(children, "root").nodes : children}</>;
  if (renderAs === "div") return <div ref={embeddedRoot} className={`${className || ""} suite-compact-form`} data-compact-form="true" onInvalidCapture={phone ? invalid : undefined} onInputCapture={phone ? () => queueMicrotask(clearResolvedValidation) : undefined} onChangeCapture={phone ? () => queueMicrotask(clearResolvedValidation) : undefined}>{content}</div>;
  return <form {...props} ref={element => { nativeForm.current = element; if (typeof ref === "function") ref(element); else if (ref) ref.current = element; }} className={`${className || ""} suite-compact-form`} data-compact-form="true" onSubmit={event => { if (event.target === event.currentTarget) onSubmit?.(event); }} onInputCapture={event => { onInputCapture?.(event); queueMicrotask(clearResolvedValidation); }} onChangeCapture={event => { onChangeCapture?.(event); queueMicrotask(clearResolvedValidation); }} onInvalidCapture={invalid}>{content}</form>;
});
CompactForm.displayName = "CompactForm";
export function CompactFields({children,className,enabled=true}:{children:ReactNode;className?:string;enabled?:boolean}) { return <CompactForm renderAs="div" compactTabs={enabled} className={className}>{children}</CompactForm>; }
export function isEditorDialog(children:ReactNode):boolean { return Children.toArray(children).some(child => {const element=asElement(child);if(!element)return false;const name=componentName(element);if (/DialogTitle|^h[12]$/.test(name) && /^(create|edit|new|add|invite|configure)\b/i.test(text(element.props.children)))return true;return isEditorDialog(element.props.children);}); }
export function revealFormField(field:HTMLElement|null) { if (!field) return; (field.closest('form') || (window.matchMedia('(max-width: 480px)').matches ? field.closest('[data-compact-form]') : null))?.dispatchEvent(new CustomEvent('suite:reveal-form-field',{detail:field})); requestAnimationFrame(() => { field.scrollIntoView({behavior:'smooth',block:'center'}); (field.matches('input,select,textarea,button') ? field : field.querySelector<HTMLElement>('input,select,textarea,button') || field).focus(); }); }
export default CompactForm;


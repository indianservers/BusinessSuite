import { Children, cloneElement, forwardRef, isValidElement, useEffect, useId, useMemo, useRef, useState, type FormEvent, type FormHTMLAttributes, type ReactElement, type ReactNode } from "react";
import "./compact-forms.css";

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
  if (/date|time|owner|assig|priority|status|stage|team|schedule|due/i.test(label)) return "Planning & ownership";
  return "Additional details";
}
function analyse(children: ReactNode) {
  const units = new Map<string, { label: string; section: string }>();
  const linkedLabels = new Map<string, {label:string;path:string}>(); const linkedInputs = new Map<string,string>();
  function labels(nodes:ReactNode,path:string) { Children.toArray(nodes).forEach((node,index) => { const element=asElement(node); if(!element)return; const key=`${path}.${index}`; if(typeof element.props.htmlFor === 'string') linkedLabels.set(element.props.htmlFor,{label:text(element.props.children),path:key}); if(typeof element.props.children !== 'function')labels(element.props.children,key); }); }
  labels(children,'root');
  let existingNavigation = false; let sectionCount = 0;
  function walk(nodes: ReactNode, path: string, section: string) {
    Children.toArray(nodes).forEach((node, index) => {
      const element = asElement(node); if (!element || element.props.hidden) return;
      const key = `${path}.${index}`, name = componentName(element), props = element.props;
      if (name === "aside") return;
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
  // Keep related fields together; overflow categories share the fourth tab.
  const categories = [...new Set([...units.values()].map(unit => unit.section))];
  const groupLabels = categories.length > 4 ? [...categories.slice(0, 3), "More details"] : categories;
  groups.push(...groupLabels);
  for (const [key, unit] of units) {
    assignments.set(key, Math.min(categories.indexOf(unit.section), 3));
  }
  for (const [id, key] of linkedInputs) { const label=linkedLabels.get(id),group=assignments.get(key); if(label && group !== undefined)assignments.set(label.path,group); }
  return { groups, assignments, enabled: !existingNavigation && (units.size >= 9 || sectionCount >= 2) && groups.length > 1 };
}

/** Native form semantics, refs and payloads are retained; only long unsectioned forms gain navigation. */
const CompactForm = forwardRef<HTMLFormElement, FormHTMLAttributes<HTMLFormElement> & { compactTabs?: boolean; renderAs?: "form" | "div" }>(({ children, className, compactTabs = true, renderAs = "form", onInvalidCapture, onSubmit, ...props }, ref) => {
  const plan = useMemo(() => analyse(children), [children]); const [active, setActive] = useState(0); const [validation, setValidation] = useState(""); const handlingInvalid = useRef(false); const id = useId(); const nativeForm = useRef<HTMLFormElement | null>(null);
  const enabled = compactTabs && plan.enabled, current = Math.min(active, Math.max(0, plan.groups.length - 1));
  useEffect(() => {
    const form = nativeForm.current; if (!form || !enabled) return;
    const reveal = (event: Event) => { const field = (event as CustomEvent<HTMLElement>).detail; const section = field.closest<HTMLElement>('[data-form-section]'); if (section && form.contains(section)) setActive(Number(section.dataset.formSection)); };
    form.addEventListener('suite:reveal-form-field', reveal); return () => form.removeEventListener('suite:reveal-form-field', reveal);
  }, [enabled, plan.groups]);
  function render(nodes: ReactNode, path: string): { nodes: ReactNode; groups: Set<number> } {
    const groups = new Set<number>();
    const result = Children.toArray(nodes).map((node, index) => {
      const element = asElement(node); if (!element) return node;
      const key = `${path}.${index}`, group = plan.assignments.get(key);
      if (group !== undefined) {
        groups.add(group); const hidden = group !== current;
        const attrs = { 'data-form-section': group, hidden, style: hidden ? { ...element.props.style, display: "none" } : element.props.style };
        return typeof element.type === "string" ? cloneElement(element, attrs) : <div key={element.key || key} {...attrs} style={{ display: hidden ? "none" : "contents" }}>{element}</div>;
      }
      if (!element.props.children || typeof element.props.children === "function") return element;
      const child = render(element.props.children, key); child.groups.forEach(value => groups.add(value));
      if (!child.groups.size) return element;
      const nextChildren = !Array.isArray(element.props.children) && Children.count(element.props.children) === 1 ? Children.toArray(child.nodes)[0] : child.nodes;
      const copy = cloneElement(element, { children: nextChildren });
      if (child.groups.size && typeof element.type !== "string") return <div key={element.key || key} style={{ display: child.groups.has(current) ? "contents" : "none" }}>{copy}</div>;
      if (child.groups.size && !child.groups.has(current)) return cloneElement(copy, { hidden: true, style: { ...element.props.style, display: "none" } });
      return copy;
    });
    return { nodes: result, groups };
  }
  function invalid(event: FormEvent<HTMLFormElement>) {
    onInvalidCapture?.(event); if (!enabled || event.defaultPrevented) return;
    const field = event.target as HTMLInputElement, section = field.closest<HTMLElement>('[data-form-section]'); if (!section) return;
    event.preventDefault(); if (handlingInvalid.current) return;
    handlingInvalid.current = true; const index = Number(section.dataset.formSection); setActive(index); setValidation(`Check ${plan.groups[index]}: ${field.validationMessage || "complete the highlighted field"}`);
    requestAnimationFrame(() => { field.focus(); handlingInvalid.current = false; });
  }
  const content = <>{enabled && <><nav className="suite-form-tabs suite-auto-form-tabs" aria-label="Form sections">{plan.groups.map((label, index) => <button key={`${id}-${label}`} type="button" aria-pressed={current === index} onClick={() => { setActive(index); setValidation(""); }}>{label}</button>)}</nav>{validation && <p role="alert" className="suite-form-validation">{validation}</p>}</>}{enabled ? render(children, "root").nodes : children}</>;
  if (renderAs === "div") return <div className={`${className || ""} suite-compact-form`} data-compact-form="true">{content}</div>;
  return <form {...props} ref={element => { nativeForm.current = element; if (typeof ref === "function") ref(element); else if (ref) ref.current = element; }} className={`${className || ""} suite-compact-form`} data-compact-form="true" onSubmit={event => { if (event.target === event.currentTarget) onSubmit?.(event); }} onInvalidCapture={invalid}>{content}</form>;
});
CompactForm.displayName = "CompactForm";
export function CompactFields({children,className,enabled=true}:{children:ReactNode;className?:string;enabled?:boolean}) { return <CompactForm renderAs="div" compactTabs={enabled} className={className}>{children}</CompactForm>; }
export function isEditorDialog(children:ReactNode):boolean { return Children.toArray(children).some(child => {const element=asElement(child);if(!element)return false;const name=componentName(element);if (/DialogTitle|^h[12]$/.test(name) && /^(create|edit|new|add|invite|configure)\b/i.test(text(element.props.children)))return true;return isEditorDialog(element.props.children);}); }
export function revealFormField(field:HTMLElement|null) { if (!field) return; field.closest('form')?.dispatchEvent(new CustomEvent('suite:reveal-form-field',{detail:field})); requestAnimationFrame(() => { field.scrollIntoView({behavior:'smooth',block:'center'}); (field.matches('input,select,textarea,button') ? field : field.querySelector<HTMLElement>('input,select,textarea,button') || field).focus(); }); }
export default CompactForm;


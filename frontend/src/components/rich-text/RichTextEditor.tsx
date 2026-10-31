import BlockDragHandle from "./BlockDragHandle";
import "./block-drag.css";
import { richTextExtensions } from "./extensions";
import { forwardRef, useEffect, useId, useRef, useState, type TextareaHTMLAttributes } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import { Extension, type Editor } from "@tiptap/core";
import { Plugin } from "@tiptap/pm/state";
import { CheckSquare, AlignCenter, AlignJustify, AlignLeft, AlignRight, Bold, ChevronDown, Code2, Eraser, Highlighter, IndentDecrease, IndentIncrease, Italic, Link2, List, ListOrdered, Maximize2, Minimize2, Minus, MoreHorizontal, Paperclip, Quote, Redo2, Strikethrough, Table2, Underline, Undo2, X } from "lucide-react";
import { contentToHtml, fontFamilies, fontSizes, RICH_TEXT_PREFIX, safeLink, sanitizeRichHtml, richTextPlainText } from "./content";
import "./rich-text.css";

export type RichTextEditorProps = {
  value: string; onChange?: (value: string) => void; onBlur?: () => void;
  onSelection?: (text: string) => void; readOnly?: boolean; disabled?: boolean;
  legacyFormat?: "plain" | "markdown" | "html";
  variant?: "compact" | "standard" | "document"; label?: string; id?: string;
  placeholder?: string; maxLength?: number; required?: boolean;
  onAttach?: () => void; className?: string;
  onKeyDown?: React.KeyboardEventHandler<HTMLDivElement>;
  saveStatus?: "saving" | "saved" | "failed"; onRetry?: () => void;
};
export default function RichTextEditor({ value, onChange, onBlur, onSelection, readOnly = false, disabled = false,
  legacyFormat = "markdown", variant = "standard", label = "Formatted content", id, placeholder = "Start writing...", maxLength,
  required, onAttach, className = "", saveStatus, onRetry, onKeyDown }: RichTextEditorProps) {
  const callbacks = useRef({ onChange, onSelection }); callbacks.current = { onChange, onSelection };
  const lastEmitted = useRef(value);
  const [fullscreen, setFullscreen] = useState(false);
  const [link, setLink] = useState<string | null>(null);
  const [error, setError] = useState("");
  const editor: Editor | null = useEditor({
    extensions: [...richTextExtensions(placeholder), Extension.create({ name: "meaningfulTextLimit",
      addProseMirrorPlugins() { return [new Plugin({ filterTransaction(transaction, state) {
        const allowed = !maxLength || !transaction.docChanged || Array.from(transaction.doc.textContent).length <= maxLength || Array.from(transaction.doc.textContent).length <= Array.from(state.doc.textContent).length;
        if (!allowed) queueMicrotask(() => setError(`Maximum ${maxLength?.toLocaleString()} text characters. The existing content is retained.`));
        return allowed;
      } })]; } })],
    content: contentToHtml(value, legacyFormat), contentType: "html", editable: !readOnly && !disabled,
    shouldRerenderOnTransaction: true,
    editorProps: { attributes: { id: id || "", role: "textbox", "aria-label": label,
      "aria-multiline": "true", "aria-required": String(Boolean(required)), "data-placeholder": placeholder },
      transformPastedHTML: sanitizeRichHtml,
      handleKeyDown: (view, event): boolean => {
        if (event.isComposing) return false;
        if (event.key === "Tab" && (view.state.selection.$from.parent.type.name === "listItem" || editor?.isActive("listItem") || editor?.isActive("taskItem"))) {
          event.preventDefault();
          const type = editor?.isActive("taskItem") ? "taskItem" : "listItem";
          return Boolean(event.shiftKey ? editor?.commands.liftListItem(type) : editor?.commands.sinkListItem(type));
        }
        return false;
      },
    },
    onUpdate: ({ editor: current }) => {
      setError("");
      // The constrained editor schema already owns this document. Sanitize at
      // import/paste, on the server, and when rendering, without reparsing the
      // entire DOM on every keystroke in a long document.
      const html = current.getHTML();
      const serialized = current.state.doc.textContent.trim() || /<(?:table|hr)(?:\s|>)/.test(html) ? RICH_TEXT_PREFIX + html : "";
      lastEmitted.current = serialized;
      callbacks.current.onChange?.(serialized);
    },
    onSelectionUpdate: ({ editor: current }) => {
      const { from, to } = current.state.selection;
      callbacks.current.onSelection?.(current.state.doc.textBetween(from, to, "\n"));
    },
  });
  useEffect(() => {
    if (!editor || editor.isDestroyed) return;
    // Lazy route transitions and StrictMode may run effects before EditorContent
    // mounts its view. Let Tiptap apply options when the view becomes available.
    editor.setOptions({ editable: !readOnly && !disabled, editorProps: {
      ...editor.options.editorProps,
      attributes: { id: id || "", role: "textbox", "aria-label": label,
        "aria-multiline": "true", "aria-required": String(Boolean(required)),
        "aria-readonly": String(readOnly || disabled), "data-placeholder": placeholder },
    } });
  }, [editor, readOnly, disabled, label, id, required, placeholder]);
  useEffect(() => {
    if (!editor || value === lastEmitted.current || editor.isFocused) return;
    // Parent acknowledgement must not replace the live document/cursor.
    const html = contentToHtml(value, legacyFormat);
    if (html !== sanitizeRichHtml(editor.getHTML())) editor.commands.setContent(html, { contentType: "html", emitUpdate: false });
    lastEmitted.current = value;
  }, [editor, value]);
  useEffect(() => {
    if (!fullscreen) return;
    const listener = (event: KeyboardEvent) => { if (event.key === "Escape") { event.stopPropagation(); setFullscreen(false); } };
    document.addEventListener("keydown", listener, true);
    return () => document.removeEventListener("keydown", listener, true);
  }, [fullscreen]);
  if (!editor) return <div role="status">Loading editor...</div>;
  const locked = readOnly || disabled;
  const tool = (name: string, Icon: typeof Bold, action: () => void, active?: boolean, unavailable = false) =>
    <button key={name} type="button" aria-label={name} title={name} aria-pressed={active} disabled={locked || unavailable}
      onMouseDown={event => event.preventDefault()} onClick={action}><Icon size={16}/></button>;
  const indent = (amount: number) => {
    const type = editor.isActive("taskItem") ? "taskItem" : "listItem";
    if (editor.isActive(type)) { if (amount > 0) editor.chain().focus().sinkListItem(type).run(); else editor.chain().focus().liftListItem(type).run(); return; }
    const node = editor.isActive("heading") ? "heading" : "paragraph";
    editor.chain().focus().updateAttributes(node, { indent: Math.min(6, Math.max(0, (editor.getAttributes(node).indent || 0) + amount)) }).run();
  };
  const style = editor.isActive("heading") ? String(editor.getAttributes("heading").level) : "paragraph";
  return <div className={`suite-rte suite-rte-${variant} ${fullscreen ? "suite-rte-fullscreen" : ""} ${locked ? "suite-rte-locked" : ""} ${className}`}
    onKeyDownCapture={onKeyDown} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) onBlur?.(); }}>
    {!readOnly && <div role="toolbar" aria-label={`${label} formatting`} className="suite-rte-toolbar">
      <div className="suite-rte-tools">{tool("Undo (Ctrl+Z)", Undo2, () => { editor.chain().focus().undo().run(); }, undefined, !editor.can().undo())}
        {tool("Redo (Ctrl+Shift+Z)", Redo2, () => { editor.chain().focus().redo().run(); }, undefined, !editor.can().redo())}</div>
      <select aria-label="Paragraph style" disabled={locked} value={style} onChange={event => {
        if (event.target.value === "paragraph") editor.chain().focus().setParagraph().run();
        else editor.chain().focus().setHeading({ level: Number(event.target.value) as 1 | 2 | 3 | 4 }).run();
      }}><option value="paragraph">Normal</option><option value="1">Title</option><option value="2">Heading 1</option><option value="3">Heading 2</option><option value="4">Heading 3</option></select>
      <select aria-label="Font family" disabled={locked} value={String(editor.getAttributes("textStyle").fontFamily || "Inter").replace(/["']/g, "")} onChange={event => editor.chain().focus().setFontFamily(event.target.value).run()}>{fontFamilies.map(font => <option key={font}>{font}</option>)}</select>
      <select aria-label="Font size" disabled={locked} value={editor.getAttributes("textStyle").fontSize || "14px"} onChange={event => editor.chain().focus().setFontSize(event.target.value).run()}>{fontSizes.map(size => <option key={size} value={size}>{parseInt(size)}</option>)}</select>
      <div className="suite-rte-tools">{tool("Bold (Ctrl+B)", Bold, () => { editor.chain().focus().toggleBold().run(); }, editor.isActive("bold"), !editor.can().toggleBold())}
        {tool("Italic (Ctrl+I)", Italic, () => { editor.chain().focus().toggleItalic().run(); }, editor.isActive("italic"), !editor.can().toggleItalic())}
        {tool("Underline (Ctrl+U)", Underline, () => { editor.chain().focus().toggleUnderline().run(); }, editor.isActive("underline"), !editor.can().toggleUnderline())}</div>
      <div className="suite-rte-tools">{tool("Bulleted list", List, () => { editor.chain().focus().toggleBulletList().run(); }, editor.isActive("bulletList"))}
        {tool("Numbered list", ListOrdered, () => { editor.chain().focus().toggleOrderedList().run(); }, editor.isActive("orderedList"))}
        {tool("Insert or edit link", Link2, () => { setLink(editor.getAttributes("link").href || "https://"); setError(""); }, editor.isActive("link"))}</div>
      <details className="suite-rte-overflow"><summary aria-label="More formatting" title="More formatting"><MoreHorizontal size={18}/><ChevronDown size={12}/></summary>
        <div className="suite-rte-menu">
          {tool("Strikethrough", Strikethrough, () => { editor.chain().focus().toggleStrike().run(); }, editor.isActive("strike"), !editor.can().toggleStrike())}
          <label title="Text color">A<input type="color" aria-label="Text color" disabled={locked} onChange={event => editor.chain().focus().setColor(event.target.value).run()}/></label>
          <label title="Highlight color"><Highlighter size={16}/><input type="color" aria-label="Highlight color" defaultValue="#fff0a6" disabled={locked} onChange={event => editor.chain().focus().setHighlight({ color: event.target.value }).run()}/></label>
          {tool("Remove highlight", Eraser, () => { editor.chain().focus().unsetHighlight().run(); })}
          {([['left',AlignLeft],['center',AlignCenter],['right',AlignRight],['justify',AlignJustify]] as const).map(([alignment,Icon]) => tool(`Align ${alignment}`, Icon, () => { editor.chain().focus().setTextAlign(alignment).run(); }, editor.isActive({ textAlign: alignment }), !editor.can().setTextAlign(alignment)))}
          {tool("Increase indent", IndentIncrease, () => indent(1))}{tool("Decrease indent", IndentDecrease, () => indent(-1))}
          {tool("Block quote", Quote, () => { editor.chain().focus().toggleBlockquote().run(); }, editor.isActive("blockquote"))}
          {tool("Checklist", CheckSquare, () => { editor.chain().focus().toggleTaskList().run(); }, editor.isActive("taskList"))}
          {tool("Code block", Code2, () => { editor.chain().focus().toggleCodeBlock().run(); }, editor.isActive("codeBlock"))}
          {tool("Horizontal divider", Minus, () => { editor.chain().focus().setHorizontalRule().run(); })}
          {tool("Insert table", Table2, () => { editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(); }, undefined, !editor.can().insertTable({rows:3,cols:3,withHeaderRow:true}))}
          {tool("Clear formatting", Eraser, () => { editor.chain().focus().unsetAllMarks().clearNodes().resetAttributes("paragraph",["indent","textAlign"]).run(); })}
        </div>
      </details>
      {onAttach && tool("Attach files", Paperclip, onAttach)}
      {tool(fullscreen ? "Exit full screen" : "Full screen", fullscreen ? Minimize2 : Maximize2, () => setFullscreen(!fullscreen))}
    </div>}
    {!readOnly && editor.isActive("table") && <div className="suite-rte-table-tools" role="toolbar" aria-label="Table formatting">
      {([['Add row','addRowAfter'],['Remove row','deleteRow'],['Add column','addColumnAfter'],['Remove column','deleteColumn'],['Header row','toggleHeaderRow'],['Delete table','deleteTable']] as const).map(([name,command]) => <button type="button" key={name} disabled={locked || !editor.can()[command]()} onMouseDown={event => event.preventDefault()} onClick={() => editor.chain().focus()[command]().run()}>{name}</button>)}
    </div>}
    {link !== null && !readOnly && <div className="suite-rte-link" role="group" aria-label="Edit hyperlink">
      <input autoFocus aria-label="Link address" type="url" value={link} placeholder="https://example.com" onChange={event => setLink(event.target.value)} onKeyDown={event => { if (event.key === "Enter") event.preventDefault(); if (event.key === "Escape") { event.stopPropagation(); setLink(null); } }}/>
      <button type="button" onClick={() => { if (!safeLink(link.trim())) { setError("Use an https://, http:// or mailto: address."); return; } editor.chain().focus().extendMarkRange("link").setLink({ href: link.trim() }).run(); setLink(null); setError(""); }}>Save link</button>
      <button type="button" disabled={!editor.isActive("link")} onClick={() => { editor.chain().focus().extendMarkRange("link").unsetLink().run(); setLink(null); }}>Remove</button>
      <button type="button" aria-label="Close link editor" onClick={() => setLink(null)}><X size={16}/></button>
    </div>}
    {error && <p role="alert" className="suite-rte-error">{error}</p>}
    {!readOnly && !disabled ? <BlockDragHandle editor={editor} onEdit={() => undefined}><EditorContent editor={editor}/></BlockDragHandle> : <EditorContent editor={editor}/>}
    {!readOnly && (maxLength || saveStatus) && <div className="suite-rte-status" aria-live="polite">
      {maxLength && <span>{Array.from(editor.state.doc.textContent).length.toLocaleString()} / {maxLength.toLocaleString()}</span>}
      {saveStatus && <span>{saveStatus === "saving" ? "Saving..." : saveStatus === "saved" ? "Saved" : "Save failed. Your edits are retained."}{saveStatus === "failed" && onRetry && <button type="button" onClick={onRetry}>Retry</button>}</span>}
    </div>}
  </div>;
}

export { RichTextContent } from "./RichTextContent";

// Adapter for existing textarea-style forms. Hook Form integrations use Controller.
export const RichTextField = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement> & { "data-legacy-format"?: "plain" | "markdown" | "html" }>(
  function RichTextField({ value, defaultValue, onChange, onBlur, onKeyDown, maxLength, rows, className, readOnly, disabled, required, ...props }, ref) {
    const [local, setLocal] = useState(String(defaultValue || ""));
    const field = useRef<HTMLTextAreaElement | null>(null);
    const unique = useId();
    const editorId = `${props.id || props.name || "rich-field"}-${unique}`;
    const [inheritedDisabled,setInheritedDisabled] = useState(false);
    useEffect(() => {
      const ancestors: HTMLFieldSetElement[] = [];
      let parent = field.current?.parentElement;
      while (parent) { if (parent.tagName === "FIELDSET") ancestors.push(parent as HTMLFieldSetElement); parent = parent.parentElement; }
      const sync = () => setInheritedDisabled(ancestors.some(item => item.disabled));
      sync(); const observer = new MutationObserver(sync);
      ancestors.forEach(item => observer.observe(item,{attributes:true,attributeFilter:["disabled"]}));
      return () => observer.disconnect();
    }, []);
    const current = value === undefined ? local : String(value || "");
    const [formLabel,setFormLabel] = useState(props["aria-label"] || props.placeholder || props.name || "Formatted content");
    useEffect(() => {
      const label = field.current?.labels?.[0];
      const text = label ? Array.from(label.childNodes).filter(node => node.nodeType === Node.TEXT_NODE).map(node => node.textContent?.trim()).filter(Boolean).join(" ") : "";
      setFormLabel(props["aria-label"] || text || props.placeholder || props.name || "Formatted content");
    }, [props.id,props.name,props["aria-label"],props.placeholder]);
    useEffect(() => {
      const form = field.current?.form;
      const reset = () => queueMicrotask(() => setLocal(field.current?.value || ""));
      form?.addEventListener("reset",reset);
      return () => form?.removeEventListener("reset",reset);
    }, []);
    return <div className={className} style={{ minWidth: 0, display: "block", padding: 0, border: 0 }}>
      <textarea {...props} ref={element => { field.current = element; if (typeof ref === "function") ref(element); else if (ref) ref.current = element; }}
        className="suite-rte-form-value" tabIndex={-1} aria-hidden="true" value={current} readOnly={readOnly} onChange={() => {}} disabled={disabled} required={required}
        onFocus={() => document.getElementById(editorId)?.focus()}/>
      <RichTextEditor value={current} onChange={next => { setLocal(next); if (field.current) { field.current.value = next; onChange?.({ target: field.current, currentTarget: field.current, type: "change" } as React.ChangeEvent<HTMLTextAreaElement>); } }}
        onBlur={() => { if (field.current) onBlur?.({ target: field.current, currentTarget: field.current, type: "blur" } as React.FocusEvent<HTMLTextAreaElement>); }}
        id={editorId} label={formLabel}
        onKeyDown={event => onKeyDown?.(event as unknown as React.KeyboardEvent<HTMLTextAreaElement>)} legacyFormat={props["data-legacy-format"] || "plain"} placeholder={props.placeholder} maxLength={maxLength} readOnly={readOnly} disabled={disabled || inheritedDisabled} required={required} variant={rows && rows > 5 ? "document" : rows && rows < 4 ? "compact" : "standard"}/>
    </div>;
  },
);
export { richTextPlainText };

import { useEffect, useRef, useState } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { TableKit } from "@tiptap/extension-table";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";
import Highlight from "@tiptap/extension-highlight";
import { Markdown } from "@tiptap/markdown";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Props = { value: string; onChange?: (value: string) => void; onSelection?: (text: string) => void; readOnly?: boolean };
export default function NoteRichEditor({ value, onChange, onSelection, readOnly = false }: Props) {
  const changeRef = useRef(onChange); changeRef.current = onChange;
  const selectionRef = useRef(onSelection); selectionRef.current = onSelection;
  const [source, setSource] = useState(false);
  const [link, setLink] = useState<string | null>(null);
  const [error, setError] = useState("");
  const editor = useEditor({
    extensions: [StarterKit.configure({ heading: { levels: [1, 2, 3] }, link: {
      openOnClick: false, autolink: false, protocols: ["http", "https"],
      isAllowedUri: url => /^https?:\/\/[^\s]+$/i.test(url),
      HTMLAttributes: { target: "_blank", rel: "noopener noreferrer" },
    } }), TableKit, TaskList, TaskItem.configure({ nested: true }), Highlight,
      Markdown.configure({ markedOptions: { gfm: true, breaks: false } })],
    content: value, contentType: "markdown", editable: !readOnly,
    shouldRerenderOnTransaction: true,
    editorProps: { attributes: { role: "textbox", "aria-label": "Note content", "aria-multiline": "true", "aria-readonly": String(readOnly), "data-placeholder": "Start writing…" } },
    onUpdate: ({ editor: current }) => changeRef.current?.(current.getMarkdown()),
    onSelectionUpdate: ({ editor: current }) => {
      const { from, to } = current.state.selection;
      selectionRef.current?.(current.state.doc.textBetween(from, to, "\n"));
    },
  });
  useEffect(() => {
    // Viewing, previewing and opening a legacy note must never trigger a save/normalization.
    editor?.setEditable(!readOnly, false);
  }, [editor, readOnly]);
  useEffect(() => {
    if (editor && editor.getMarkdown() !== value) editor.commands.setContent(value, { contentType: "markdown", emitUpdate: false });
  }, [editor, value]);
  if (!editor) return <p role="status">Loading editor…</p>;
  const tool = (label: string, action: () => void, active?: boolean, disabled = false) => <button type="button" key={label} aria-label={label} title={label} aria-pressed={active} disabled={disabled} onMouseDown={event => event.preventDefault()} onClick={action}>{label}</button>;
  return <div className="note-rich-editor">
    {!readOnly && <>
      <div className="notes-editor-mode"><span>Write naturally. Formatting is saved with your note.</span><Button size="sm" variant="ghost" aria-pressed={source} onClick={() => { setSource(v => !v); setLink(null); }}>{source ? "Rich editor" : "Markdown source"}</Button></div>
      {!source && <div role="toolbar" aria-label="Note formatting" className="note-rich-toolbar">
        <select aria-label="Text style" value={editor.isActive("heading", { level: 1 }) ? "1" : editor.isActive("heading", { level: 2 }) ? "2" : editor.isActive("heading", { level: 3 }) ? "3" : "paragraph"} onChange={e => { if (e.target.value === "paragraph") editor.chain().focus().setParagraph().run(); else editor.chain().focus().toggleHeading({ level: Number(e.target.value) as 1 | 2 | 3 }).run(); }}><option value="paragraph">Paragraph</option><option value="1">Heading 1</option><option value="2">Heading 2</option><option value="3">Heading 3</option></select>
        {tool("Bold", () => { editor.chain().focus().toggleBold().run(); }, editor.isActive("bold"))}
        {tool("Italic", () => { editor.chain().focus().toggleItalic().run(); }, editor.isActive("italic"))}
        {tool("Underline", () => { editor.chain().focus().toggleUnderline().run(); }, editor.isActive("underline"))}
        {tool("Strike", () => { editor.chain().focus().toggleStrike().run(); }, editor.isActive("strike"))}
        {tool("Highlight", () => { editor.chain().focus().toggleHighlight().run(); }, editor.isActive("highlight"))}
        {tool("Bullet list", () => { editor.chain().focus().toggleBulletList().run(); }, editor.isActive("bulletList"))}
        {tool("Numbered list", () => { editor.chain().focus().toggleOrderedList().run(); }, editor.isActive("orderedList"))}
        {tool("Checklist", () => { editor.chain().focus().toggleTaskList().run(); }, editor.isActive("taskList"))}
        {tool("Quote", () => { editor.chain().focus().toggleBlockquote().run(); }, editor.isActive("blockquote"))}
        {tool("Code block", () => { editor.chain().focus().toggleCodeBlock().run(); }, editor.isActive("codeBlock"))}
        {tool("Link", () => { setLink(String(editor.getAttributes("link").href || "https://")); setError(""); }, editor.isActive("link"))}
        {tool("Insert table", () => { editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(); })}
        {editor.isActive("table") && <>{tool("Add row", () => { editor.chain().focus().addRowAfter().run(); })}{tool("Add column", () => { editor.chain().focus().addColumnAfter().run(); })}{tool("Delete row", () => { editor.chain().focus().deleteRow().run(); })}{tool("Delete column", () => { editor.chain().focus().deleteColumn().run(); })}{tool("Delete table", () => { editor.chain().focus().deleteTable().run(); })}</>}
        {tool("Undo", () => { editor.chain().focus().undo().run(); }, undefined, !editor.can().undo())}
        {tool("Redo", () => { editor.chain().focus().redo().run(); }, undefined, !editor.can().redo())}
      </div>}
      {link !== null && <form className="note-link-form" onSubmit={e => { e.preventDefault(); if (!/^https?:\/\/[^\s]+$/i.test(link.trim())) { setError("Use a complete http:// or https:// link."); return; } editor.chain().focus().extendMarkRange("link").setLink({ href: link.trim() }).run(); setLink(null); setError(""); }}><label>Link address<Input aria-label="Link address" value={link} onChange={e => setLink(e.target.value)} autoFocus /></label><Button size="sm" type="submit">Apply link</Button><Button size="sm" type="button" variant="outline" onClick={() => { editor.chain().focus().unsetLink().run(); setLink(null); }}>Remove link</Button><Button size="sm" type="button" variant="ghost" onClick={() => { setLink(null); setError(""); }}>Cancel</Button></form>}
      {error && <p role="alert" className="text-destructive text-sm">{error}</p>}
    </>}
    {source && !readOnly ? <textarea aria-label="Note Markdown source" value={value} maxLength={200000} onChange={e => onChange?.(e.target.value)} onSelect={e => { const target = e.currentTarget; onSelection?.(target.value.slice(target.selectionStart, target.selectionEnd)); }} /> : <EditorContent editor={editor} />}
  </div>;
}

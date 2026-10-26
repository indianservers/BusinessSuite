import RichTextEditor, { type RichTextEditorProps } from "@/components/rich-text/LazyRichText";
export default function NoteRichEditor(props: RichTextEditorProps) {
  return <RichTextEditor label="Note content" variant="document" maxLength={200000} {...props}/>;
}

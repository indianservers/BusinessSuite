import NoteEditor, { type NoteEditorProps } from "@/shared/productivity/NoteEditor";
import PrivateNoteImage from "./PrivateNoteImage";

export default function NoteRichEditor(props: Omit<NoteEditorProps, "AttachmentView">) {
  return <NoteEditor {...props} AttachmentView={PrivateNoteImage} />;
}

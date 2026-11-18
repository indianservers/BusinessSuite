import { AllSelection, Selection, type EditorState } from "@tiptap/pm/state";

/** Wrap/lift commands need endpoints inside text blocks, not document edges. */
export function blockTextSelection(state: EditorState) {
  if (!(state.selection instanceof AllSelection)) return undefined;
  return { from: Selection.atStart(state.doc).from, to: Selection.atEnd(state.doc).to };
}

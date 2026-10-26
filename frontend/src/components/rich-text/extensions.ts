import { Placeholder } from "@tiptap/extensions";
import { Extension } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { TableKit } from "@tiptap/extension-table";
import { TextStyleKit } from "@tiptap/extension-text-style";
import TextAlign from "@tiptap/extension-text-align";
import Highlight from "@tiptap/extension-highlight";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";
import { Markdown } from "@tiptap/markdown";
import { safeLink } from "./content";
const Indent = Extension.create({
  name: "suiteIndent",
  addGlobalAttributes() {
    return [{ types: ["paragraph", "heading"], attributes: { indent: {
      default: 0,
      parseHTML: element => Math.min(6, Math.max(0, parseInt(element.getAttribute("data-indent") || "0", 10) || 0)),
      renderHTML: attributes => attributes.indent ? { "data-indent": attributes.indent, style: `margin-left: ${attributes.indent * 24}px` } : {},
    } } }];
  },
});
export function richTextExtensions(placeholder = "Start writing...") {
  return [Placeholder.configure({ placeholder }), StarterKit.configure({ heading: { levels: [1, 2, 3, 4] }, link: {
    openOnClick: false, autolink: false, isAllowedUri: safeLink,
    HTMLAttributes: { target: "_blank", rel: "noopener noreferrer" },
  } }), TableKit, TaskList, TaskItem.configure({ nested: true }),
  TextStyleKit, TextAlign.configure({ types: ["heading", "paragraph"] }),
  Highlight.configure({ multicolor: true }), Indent,
  Markdown.configure({ markedOptions: { gfm: true, breaks: false } })];
}

import { useEffect, useRef, useState } from "react";
import { EditorContent, NodeViewWrapper, ReactNodeViewRenderer, useEditor, type NodeViewProps } from "@tiptap/react";
import { Node, Extension, type Editor, type JSONContent } from "@tiptap/core";
import { Plugin } from "@tiptap/pm/state";
import { AlignCenter, AlignJustify, AlignLeft, AlignRight, Bold, Calendar, CheckSquare, Code2, Eraser, Highlighter, ImagePlus, IndentDecrease, IndentIncrease, Italic, Link2, List, ListOrdered, Maximize2, Minimize2, Minus, MoreHorizontal, Paintbrush, Paperclip, Quote, Redo2, Replace, Strikethrough, Table2, Underline, Undo2, X, GripVertical, Info, FileText, Folder } from "lucide-react";
import { api } from "@/services/api";
import { richTextExtensions } from "@/components/rich-text/extensions";
import { contentToHtml, RICH_TEXT_PREFIX, sanitizeRichHtml, fontSizes } from "@/components/rich-text/content";
import type { RichTextEditorProps } from "@/components/rich-text/RichTextEditor";
import "@/components/rich-text/rich-text.css";

import NoteBlockDragHandle from "./NoteBlockDragHandle";

type Props = RichTextEditorProps & { noteId?: number; onImage?: (file: File) => Promise<{ id: number; filename: string }>; onFile?: (file:File)=>Promise<{id:number;filename:string}>; onReady?: (editor: Editor) => void; onReference?: (kind: "task" | "project") => void };
export default function NoteRichEditor({ value, onChange, onSelection, readOnly, noteId, onImage, onFile, onAttach, onReady, onReference }: Props) {
  const callbacks = useRef({onChange, onSelection, onReady}); callbacks.current = {onChange, onSelection, onReady};
  const emitted = useRef(value);
  const interacted=useRef(false);
  const noteIdRef=useRef(noteId);noteIdRef.current=noteId;
  const [error, setError] = useState("");
  const [fullscreen, setFullscreen] = useState(false);
  const [find, setFind] = useState<string | null>(null);
  const [replacement, setReplacement] = useState("");
  const [link, setLink] = useState<string | null>(null);
  const [slash, setSlash] = useState<string | null>(null);
  const [paint, setPaint] = useState<JSONContent[] | null>(null);
  const imageInput = useRef<HTMLInputElement>(null);
  const PrivateImage = Node.create({ name: "privateImage", priority: 1000, group: "block", atom: true, draggable: true,
    addAttributes: () => ({ attachmentId: {default: null}, alt: {default: "Image"} }),
    parseHTML: () => [{tag: "p[data-note-image]", priority: 1000, getAttrs: element => ({ attachmentId: Number((element as HTMLElement).getAttribute("data-note-image")), alt: (element as HTMLElement).textContent || "Image" })}],
    renderHTML: ({node}) => ["p", {"data-note-image": String(node.attrs.attachmentId)}, String(node.attrs.alt)],
    addNodeView: () => ReactNodeViewRenderer((props: NodeViewProps) => <PrivateNoteImage {...props} noteId={noteIdRef.current} />),
    renderMarkdown: (node: any) => `![${String(node.attrs.alt).replace(/[\[\]]/g, "") }](attachment:${node.attrs.attachmentId})`,
  });
  const editor = useEditor({
    extensions: [...richTextExtensions("Start writing, or type / for commands…", [1,2,3,4,5,6]), PrivateImage, Extension.create({name:"notesLimit",addKeyboardShortcuts(){return {"Mod-y":()=>this.editor.commands.redo()};},addProseMirrorPlugins(){return [new Plugin({filterTransaction(tr,state){return !tr.docChanged || tr.doc.textContent.length<=200000 || tr.doc.textContent.length<state.doc.textContent.length;}})];}})],
    content: contentToHtml(value), editable: !readOnly, shouldRerenderOnTransaction: true,
    editorProps: { attributes: { role: "textbox", "aria-label": "Note content", "aria-multiline": "true" }, transformPastedHTML: sanitizeRichHtml },
    onUpdate: ({editor: current}) => {
      if(!interacted.current)return;
      const html=current.getHTML(); const serialized=current.isEmpty?"":RICH_TEXT_PREFIX+html;
      emitted.current=serialized; callbacks.current.onChange?.(serialized);
      const { $from }=current.state.selection;
      const before=$from.parent.textBetween(0,$from.parentOffset);
      const command=before.match(/(?:^| )\/([a-z]*)$/i); setSlash(command?command[1]:null);
    },
    onSelectionUpdate: ({editor: current}) => {
      if(!interacted.current)return; const {from,to}=current.state.selection; callbacks.current.onSelection?.(current.state.doc.textBetween(from,to,"\n")); },
    onCreate: ({editor: current}) => callbacks.current.onReady?.(current),
  });
  useEffect(()=>{editor?.setEditable(!readOnly);},[editor,readOnly]);
  useEffect(()=>{if(editor && value!==emitted.current && !editor.isFocused){editor.commands.setContent(contentToHtml(value),{emitUpdate:false});emitted.current=value;}},[editor,value]);
  if(!editor) return <p role="status">Loading editor…</p>;
  const command=(action:()=>void)=>{setError("");action();};
  const tool=(name:string, Icon:typeof Bold, action:()=>void, active=false, disabled=false)=><button key={name} type="button" aria-label={name} title={name} aria-pressed={active} disabled={readOnly||disabled} onMouseDown={e=>e.preventDefault()} onClick={()=>command(action)}><Icon size={16}/></button>;
  const indent=(increase:boolean)=>{const kind=editor.isActive("taskItem")?"taskItem":"listItem";if(editor.isActive(kind)){if(increase)editor.chain().focus().sinkListItem(kind).run();else editor.chain().focus().liftListItem(kind).run();}else{const type=editor.isActive("heading")?"heading":"paragraph";editor.chain().focus().updateAttributes(type,{indent:Math.max(0,Math.min(6,(editor.getAttributes(type).indent||0)+(increase?1:-1)))}).run();}};
  const table=()=>editor.chain().focus().insertTable({rows:3,cols:3,withHeaderRow:true}).run();
  const callout=()=>editor.chain().focus().insertContent('<blockquote><p><strong>Note</strong></p><p>Write your callout here.</p></blockquote>').run();
  const matches=()=>{const found:{from:number;to:number}[]=[];if(find)editor.state.doc.descendants((node,pos)=>{if(node.isTextblock){const text=node.textContent.toLowerCase();let i=0;while((i=text.indexOf(find.toLowerCase(),i))!==-1){found.push({from:pos+1+i,to:pos+1+i+find.length});i+=find.length;}}});return found;};
  const nextMatch=()=>{const found=matches();const target=found.find(item=>item.from>editor.state.selection.from)||found[0];if(target)editor.chain().focus().setTextSelection(target).scrollIntoView().run();else setError("No matches found.");};
  const replaceAll=()=>{const found=matches();const chain=editor.chain().focus();for(const item of found.reverse()){chain.deleteRange(item);if(replacement)chain.insertContentAt(item.from,{type:"text",text:replacement});}chain.run();};
  const slashCommands=[{name:"Heading",run:()=>editor.chain().focus().setHeading({level:2}).run()},{name:"Checklist",run:()=>editor.chain().focus().toggleTaskList().run()},{name:"Table",run:table},{name:"Code block",run:()=>editor.chain().focus().toggleCodeBlock().run()},{name:"Callout",run:callout},{name:"Date",run:()=>editor.chain().focus().insertContent(new Date().toLocaleDateString()).run()}].filter(item=>item.name.toLowerCase().includes(slash||""));
  const receiveFiles=async(files:File[])=>{interacted.current=true;for(const file of files){try{if(file.type.startsWith("image/")&&onImage){const uploaded=await onImage(file);editor.chain().focus().insertContent({type:"privateImage",attrs:{attachmentId:uploaded.id,alt:uploaded.filename}}).run();}else if(onFile){await onFile(file);}else setError("Use Attach files to upload this file.");}catch(failure){setError(failure instanceof Error?failure.message:"File upload failed");break;}}};
  const applySlash=(run:()=>void)=>{const to=editor.state.selection.from;editor.chain().focus().deleteRange({from:to-(slash?.length||0)-1,to}).run();run();setSlash(null);};
  return <div className={`note-writer suite-rte suite-rte-document ${fullscreen?"note-writer-fullscreen":""}`} onDragOver={e=>{if(!readOnly&&e.dataTransfer.types.includes("Files")){e.preventDefault();e.dataTransfer.dropEffect="copy";}}} onDropCapture={e=>{if(!readOnly&&e.dataTransfer.files.length){e.preventDefault();e.stopPropagation();void receiveFiles(Array.from(e.dataTransfer.files));}}} onPasteCapture={e=>{if(!readOnly&&e.clipboardData.files.length){e.preventDefault();void receiveFiles(Array.from(e.clipboardData.files));}}} onPointerDownCapture={()=>{interacted.current=true;}} onKeyDownCapture={e=>{interacted.current=true;if(e.key==="Escape"){setFullscreen(false);setSlash(null);}if(slash!==null&&e.key==="Enter"&&slashCommands[0]){e.preventDefault();e.stopPropagation();applySlash(slashCommands[0].run);}}}>
    {!readOnly && <div role="toolbar" aria-label="Note content formatting" className="note-icon-toolbar">
      {tool("Undo (Ctrl+Z)",Undo2,()=>{editor.chain().focus().undo().run();},false,!editor.can().undo())}{tool("Redo (Ctrl+Y)",Redo2,()=>{editor.chain().focus().redo().run();},false,!editor.can().redo())}
      <i/>
      <select aria-label="Paragraph style" value={editor.isActive("heading")?String(editor.getAttributes("heading").level):"p"} onChange={e=>e.target.value==="p"?editor.chain().focus().setParagraph().run():editor.chain().focus().setHeading({level:Number(e.target.value) as 1|2|3|4|5|6}).run()}><option value="p">Paragraph</option>{[1,2,3,4,5,6].map(level=><option key={level} value={level}>Heading {level}</option>)}</select>
      <select aria-label="Font size" value={editor.getAttributes("textStyle").fontSize||"14px"} onChange={e=>editor.chain().focus().setFontSize(e.target.value).run()}>{fontSizes.map(size=><option key={size} value={size}>{parseInt(size)}</option>)}</select><i/>
      {tool("Bold (Ctrl+B)",Bold,()=>{editor.chain().focus().toggleBold().run();},editor.isActive("bold"))}{tool("Italic (Ctrl+I)",Italic,()=>{editor.chain().focus().toggleItalic().run();},editor.isActive("italic"))}{tool("Underline (Ctrl+U)",Underline,()=>{editor.chain().focus().toggleUnderline().run();},editor.isActive("underline"))}{tool("Strikethrough",Strikethrough,()=>{editor.chain().focus().toggleStrike().run();},editor.isActive("strike"))}
      <label title="Text color" className="note-color"><span>A</span><input type="color" aria-label="Text color" onChange={e=>editor.chain().focus().setColor(e.target.value).run()}/></label>
      <label title="Highlight color" className="note-color"><Highlighter size={16}/><input type="color" aria-label="Highlight color" defaultValue="#fff0a6" onChange={e=>editor.chain().focus().setHighlight({color:e.target.value}).run()}/></label><i/>
      {tool("Bulleted list",List,()=>{editor.chain().focus().toggleBulletList().run();},editor.isActive("bulletList"))}{tool("Numbered list",ListOrdered,()=>{editor.chain().focus().toggleOrderedList().run();},editor.isActive("orderedList"))}{tool("Checklist",CheckSquare,()=>{editor.chain().focus().toggleTaskList().run();},editor.isActive("taskList"))}{tool("Insert or edit link",Link2,()=>setLink(editor.getAttributes("link").href||"https://"))}
      {tool("Insert image",ImagePlus,()=>imageInput.current?.click(),false,!onImage)}{tool("Insert table",Table2,table)}
      <details className="notes-command-menu" onClick={event=>{if((event.target as Element).closest("button"))event.currentTarget.removeAttribute("open");}}><summary aria-label="More formatting" title="More formatting"><MoreHorizontal size={18}/></summary><div className="note-more-tools">
        {([['left',AlignLeft],['center',AlignCenter],['right',AlignRight],['justify',AlignJustify]] as const).map(([align,Icon])=>tool(`Align ${align}`,Icon,()=>{editor.chain().focus().setTextAlign(align).run();},editor.isActive({textAlign:align})))}
        {tool("Increase indent",IndentIncrease,()=>indent(true))}{tool("Decrease indent",IndentDecrease,()=>indent(false))}{tool("Block quote",Quote,()=>{editor.chain().focus().toggleBlockquote().run();})}{tool("Horizontal divider",Minus,()=>{editor.chain().focus().setHorizontalRule().run();})}{tool("Code block",Code2,()=>{editor.chain().focus().toggleCodeBlock().run();})}{tool("Callout",Info,callout)}{tool("Insert date",Calendar,()=>{editor.chain().focus().insertContent(new Date().toLocaleDateString()).run();})}
        {tool("Clear formatting",Eraser,()=>{editor.chain().focus().unsetAllMarks().clearNodes().run();})}{tool(paint?"Apply copied formatting":"Copy formatting",Paintbrush,()=>{if(paint){const chain=editor.chain().focus().unsetAllMarks();for(const mark of paint)chain.setMark(mark.type!,mark.attrs);chain.run();setPaint(null);}else setPaint((editor.state.selection.$from.marks()).map(mark=>mark.toJSON()));},!!paint)}
        {tool("Find and replace",Replace,()=>setFind(""))}{tool("Attach files",Paperclip,()=>onAttach?.(),false,!onAttach)}{tool("Insert task reference",FileText,()=>onReference?.("task"),false,!onReference)}{tool("Insert project reference",Folder,()=>onReference?.("project"),false,!onReference)}
      </div></details>
      <button type="button" title={fullscreen?"Exit focus mode":"Full-screen focus mode"} aria-label={fullscreen?"Exit focus mode":"Full-screen focus mode"} onClick={()=>setFullscreen(!fullscreen)}>{fullscreen?<Minimize2 size={16}/>:<Maximize2 size={16}/>}</button>
    </div>}
    {!readOnly&&editor.isActive("table")&&<div className="note-table-tools" role="toolbar" aria-label="Table formatting">{([['Add row','addRowAfter'],['Remove row','deleteRow'],['Add column','addColumnAfter'],['Remove column','deleteColumn'],['Merge cells','mergeCells'],['Split cell','splitCell'],['Header row','toggleHeaderRow'],['Remove table','deleteTable']] as const).map(([name,action])=><button key={name} type="button" aria-label={name} title={name} onMouseDown={e=>e.preventDefault()} onClick={()=>{(editor.chain().focus() as any)[action]().run();}}><Table2 size={14}/><span aria-hidden="true">{name.startsWith("Add")?"+":name.startsWith("Remove")?"-":name.startsWith("Merge")?"M":name.startsWith("Split")?"S":"H"}</span></button>)}</div>}
    {link!==null&&<form className="note-find-bar" onSubmit={e=>{e.preventDefault();if(!/^(https?:\/\/|mailto:)[^\s<>]+$/i.test(link)){setError("Enter a valid HTTPS, HTTP or email link.");return;}editor.chain().focus().setLink({href:link}).run();setLink(null);}}><input aria-label="Link URL" value={link} onChange={e=>setLink(e.target.value)} autoFocus/><button>Apply link</button><button type="button" onClick={()=>{editor.chain().focus().unsetLink().run();setLink(null);}}>Remove link</button><button type="button" onClick={()=>setLink(null)} aria-label="Close link"><X size={14}/></button></form>}
    {find!==null&&<div className="note-find-bar"><input aria-label="Find in note" placeholder="Find…" value={find} onChange={e=>setFind(e.target.value)}/><input aria-label="Replace with" placeholder="Replace with…" value={replacement} onChange={e=>setReplacement(e.target.value)}/><button type="button" onClick={nextMatch}>Next</button><button type="button" onClick={replaceAll} disabled={!find||readOnly}>Replace all</button><button type="button" onClick={()=>setFind(null)} aria-label="Close find"><X size={14}/></button></div>}
    {!readOnly&&!editor.state.selection.empty&&<div className="notes-floating-format">{tool("Selection bold",Bold,()=>{editor.chain().focus().toggleBold().run();})}{tool("Selection italic",Italic,()=>{editor.chain().focus().toggleItalic().run();})}{tool("Selection highlight",Highlighter,()=>{editor.chain().focus().toggleHighlight().run();})}</div>}
    {readOnly?<EditorContent editor={editor}/>:<NoteBlockDragHandle editor={editor} onEdit={()=>{interacted.current=true;}}><EditorContent editor={editor}/></NoteBlockDragHandle>}
    {slash!==null&&!readOnly&&<div className="notes-slash-menu" role="menu" aria-label="Insert block">{slashCommands.map(item=><button key={item.name} role="menuitem" onMouseDown={e=>e.preventDefault()} onClick={()=>applySlash(item.run)}>{item.name}</button>)}</div>}
    <input ref={imageInput} type="file" accept="image/png,image/jpeg,image/gif,image/webp" hidden aria-label="Insert private image" onChange={async e=>{interacted.current=true;const file=e.target.files?.[0];if(!file||!onImage)return;try{const uploaded=await onImage(file);editor.chain().focus().insertContent({type:"privateImage",attrs:{attachmentId:uploaded.id,alt:uploaded.filename}}).run();}catch(failure){setError(failure instanceof Error?failure.message:"Image upload failed");}finally{e.target.value="";}}}/>
    {error&&<p role="alert" className="notes-error">{error}</p>}
  </div>;
}

function PrivateNoteImage({node,noteId}:NodeViewProps&{noteId?:number}){
  const [url,setUrl]=useState("");const [failed,setFailed]=useState(false);
  useEffect(()=>{if(!noteId)return;const abort=new AbortController();let objectUrl="";void api.get(`/project-management/notes/${noteId}/attachments/${node.attrs.attachmentId}/download`,{responseType:"blob",signal:abort.signal}).then(({data})=>{if(abort.signal.aborted)return;if(!["image/png","image/jpeg","image/gif","image/webp"].includes(data.type)){setFailed(true);return;}objectUrl=URL.createObjectURL(data);setUrl(objectUrl);}).catch(()=>{if(!abort.signal.aborted)setFailed(true);});return()=>{abort.abort();if(objectUrl)URL.revokeObjectURL(objectUrl);};},[noteId,node.attrs.attachmentId]);
  return <NodeViewWrapper className="note-inline-image" contentEditable={false}><span data-drag-handle draggable className="note-image-handle" title="Drag image block"><GripVertical size={16}/></span>{url?<img src={url} alt={node.attrs.alt}/>:<span>{failed?"Image unavailable":noteId?"Loading private image…":"Saving image…"}</span>}</NodeViewWrapper>;
}

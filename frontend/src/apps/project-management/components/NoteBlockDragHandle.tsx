import { useRef, useState, type DragEvent, type ReactNode } from "react";
import type { Editor } from "@tiptap/core";
import { NodeSelection, Selection } from "@tiptap/pm/state";
import { GripVertical } from "lucide-react";

/** Drag complete document blocks, leaving ordinary text selection untouched. */
export default function NoteBlockDragHandle({editor,onEdit,children}:{editor:Editor;onEdit:()=>void;children:ReactNode}){
  const [block,setBlock]=useState<{from:number;to:number;top:number}|null>(null);
  const [dragging,setDragging]=useState(false);
  const drag=useRef<{from:number;to:number}|null>(null);
  function move(from:number,to:number,target:number){
    if(target>=from&&target<=to)return;
    const fragment=editor.state.doc.slice(from,to).content;
    const transaction=editor.state.tr.delete(from,to);
    const destination=transaction.mapping.map(target);
    transaction.insert(destination,fragment);
    transaction.setSelection(Selection.near(transaction.doc.resolve(destination)));
    onEdit();editor.view.dispatch(transaction.scrollIntoView());editor.commands.focus();setBlock(null);
  }
  function drop(event:DragEvent){
    const source=drag.current;if(!source)return;
    event.preventDefault();event.stopPropagation();
    const found=editor.view.posAtCoords({left:event.clientX,top:event.clientY});
    if(found){
      const resolved=editor.state.doc.resolve(found.pos);
      let target=resolved.depth?resolved.before(1):found.pos;
      const node=editor.state.doc.nodeAt(target);
      const element=editor.view.nodeDOM(target) as HTMLElement|null;
      if(node&&element?.getBoundingClientRect&&event.clientY>element.getBoundingClientRect().top+element.getBoundingClientRect().height/2)target+=node.nodeSize;
      move(source.from,source.to,target);
    }
    drag.current=null;setDragging(false);
  }
  return <div className={`note-block-drag-layer ${dragging?"dragging":""}`} onDragOver={event=>{if(drag.current){event.preventDefault();event.dataTransfer.dropEffect="move";}}} onDropCapture={drop} onMouseMove={event=>{
      if(drag.current)return;
      const position=editor.view.posAtCoords({left:event.clientX,top:event.clientY});if(!position)return;
      const resolved=editor.state.doc.resolve(position.pos);if(!resolved.depth)return;
      const from=resolved.before(1),node=editor.state.doc.nodeAt(from),element=editor.view.nodeDOM(from) as HTMLElement|null;
      const root=event.currentTarget.getBoundingClientRect();
      if(node&&element?.getBoundingClientRect&&root)setBlock({from,to:from+node.nodeSize,top:element.getBoundingClientRect().top-root.top});
    }}>
    {children}
    {block&&<button type="button" className="note-block-handle" aria-label="Drag block to reorder" title="Drag block · Alt+↑/↓ to move" draggable style={{top:block.top}} onClick={()=>{editor.view.dispatch(editor.state.tr.setSelection(NodeSelection.create(editor.state.doc,block.from)));editor.commands.focus();}} onDragStart={event=>{drag.current={from:block.from,to:block.to};setDragging(true);event.dataTransfer.effectAllowed="move";event.dataTransfer.setData("application/x-karyaflow-block",String(block.from));}} onDragEnd={()=>{drag.current=null;setDragging(false);}} onKeyDown={event=>{
      if(!event.altKey||!["ArrowUp","ArrowDown"].includes(event.key))return;event.preventDefault();
      const resolved=editor.state.doc.resolve(block.from);const previous=resolved.nodeBefore,next=editor.state.doc.nodeAt(block.to);
      if(event.key==="ArrowUp"&&previous)move(block.from,block.to,block.from-previous.nodeSize);
      if(event.key==="ArrowDown"&&next)move(block.from,block.to,block.to+next.nodeSize);
    }}><GripVertical size={16}/></button>}
  </div>;
}

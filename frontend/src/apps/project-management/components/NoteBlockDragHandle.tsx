import { useEffect, useRef, useState, type DragEvent, type ReactNode } from "react";
import type { Editor } from "@tiptap/core";
import { NodeSelection, Selection } from "@tiptap/pm/state";
import { GripVertical } from "lucide-react";

type Block={from:number;to:number;top:number};
type DropPoint={target:number;top:number};
/** Separate block grips preserve ordinary click-and-drag text selection. */
export default function NoteBlockDragHandle({editor,onEdit,children}:{editor:Editor;onEdit:()=>void;children:ReactNode}){
  const root=useRef<HTMLDivElement>(null);
  const [block,setBlock]=useState<Block|null>(null);
  const [dragging,setDragging]=useState(false);
  const [line,setLine]=useState<DropPoint|null>(null);
  const drag=useRef<{from:number;to:number}|null>(null);
  const pointer=useRef<{x:number;y:number}|null>(null);
  const touchPointer=useRef<number|null>(null);
  const ignoreClick=useRef(false);
  const edit=useRef(onEdit);edit.current=onEdit;
  function showBlock(position:number){
    const resolved=editor.state.doc.resolve(position);if(!resolved.depth)return;
    const from=resolved.before(1),node=editor.state.doc.nodeAt(from),element=editor.view.nodeDOM(from) as HTMLElement|null;
    if(node&&element?.getBoundingClientRect&&root.current){const top=element.getBoundingClientRect().top-root.current.getBoundingClientRect().top;setBlock(prior=>prior?.from===from&&prior.top===top?prior:{from,to:from+node.nodeSize,top});}
  }
  function dropPoint(x:number,y:number):DropPoint|null{
    const area=editor.view.dom.getBoundingClientRect();
    const found=editor.view.posAtCoords({left:Math.max(area.left+2,Math.min(area.right-2,x)),top:Math.max(area.top+1,Math.min(area.bottom-1,y))});
    if(!found||!root.current)return null;
    const resolved=editor.state.doc.resolve(found.pos);
    let target=resolved.depth?resolved.before(1):found.pos;
    const node=editor.state.doc.nodeAt(target),element=editor.view.nodeDOM(target) as HTMLElement|null;
    let top=area.bottom;
    if(node&&element?.getBoundingClientRect){const rect=element.getBoundingClientRect();const after=y>rect.top+rect.height/2;top=after?rect.bottom:rect.top;if(after)target+=node.nodeSize;}
    return {target,top:top-root.current.getBoundingClientRect().top};
  }
  function updateLine(x:number,y:number){pointer.current={x,y};const next=dropPoint(x,y);setLine(prior=>prior?.target===next?.target&&prior?.top===next?.top?prior:next);return next;}
  function move(from:number,to:number,target:number){
    if(target>=from&&target<=to)return;
    const fragment=editor.state.doc.slice(from,to).content;
    const transaction=editor.state.tr.delete(from,to);
    const destination=transaction.mapping.map(target);
    transaction.insert(destination,fragment).setSelection(Selection.near(transaction.doc.resolve(destination)));
    edit.current();editor.view.dispatch(transaction.scrollIntoView());editor.commands.focus();setBlock(null);
  }
  function finish(x?:number,y?:number){
    const source=drag.current;const destination=x!==undefined&&y!==undefined?dropPoint(x,y):null;
    if(source&&destination)move(source.from,source.to,destination.target);
    drag.current=null;pointer.current=null;touchPointer.current=null;setDragging(false);setLine(null);
  }
  useEffect(()=>{
    const selection=()=>{if(!drag.current)showBlock(editor.state.selection.from);};
    editor.on("selectionUpdate",selection);selection();return()=>{editor.off("selectionUpdate",selection);};
  },[editor]);
  useEffect(()=>{
    if(!dragging)return;
    let frame=0;
    const tick=()=>{const point=pointer.current;const scroller=editor.view.dom.closest<HTMLElement>(".note-writer-fullscreen")||editor.view.dom.closest<HTMLElement>(".notes-document-scroll");if(point&&scroller){const rect=scroller.getBoundingClientRect();const delta=point.y<rect.top+45?-Math.min(18,(rect.top+45-point.y)/3):point.y>rect.bottom-45?Math.min(18,(point.y-rect.bottom+45)/3):0;if(delta){scroller.scrollTop+=delta;updateLine(point.x,point.y);}}frame=requestAnimationFrame(tick);};
    frame=requestAnimationFrame(tick);return()=>cancelAnimationFrame(frame);
  },[dragging,editor]);
  return <div ref={root} className={`note-block-drag-layer ${dragging?"dragging":""}`} onDragOver={event=>{if(drag.current){event.preventDefault();event.dataTransfer.dropEffect="move";updateLine(event.clientX,event.clientY);}}} onDropCapture={(event:DragEvent)=>{if(!drag.current)return;event.preventDefault();event.stopPropagation();finish(event.clientX,event.clientY);}} onMouseMove={event=>{if(drag.current)return;const position=editor.view.posAtCoords({left:event.clientX,top:event.clientY});if(position)showBlock(position.pos);}}>
    {children}
    {line&&dragging&&<div className="note-block-insertion" aria-hidden="true" style={{top:line.top}}/>}
    {block&&<button type="button" className="note-block-handle" aria-label="Drag block to reorder" title="Drag block · Alt+↑/↓ to move" draggable style={{top:block.top}} onClick={()=>{if(ignoreClick.current){ignoreClick.current=false;return;}editor.view.dispatch(editor.state.tr.setSelection(NodeSelection.create(editor.state.doc,block.from)));editor.commands.focus();}} onDragStart={event=>{drag.current={from:block.from,to:block.to};setDragging(true);event.dataTransfer.effectAllowed="move";event.dataTransfer.setData("application/x-karyaflow-block",String(block.from));updateLine(event.clientX,event.clientY);}} onDragEnd={()=>finish()} onPointerDown={event=>{
      if(event.pointerType==="mouse")return;event.preventDefault();touchPointer.current=event.pointerId;drag.current={from:block.from,to:block.to};event.currentTarget.setPointerCapture(event.pointerId);setDragging(true);updateLine(event.clientX,event.clientY);
    }} onPointerMove={event=>{if(touchPointer.current===event.pointerId){event.preventDefault();updateLine(event.clientX,event.clientY);}}} onPointerUp={event=>{if(touchPointer.current===event.pointerId){ignoreClick.current=true;finish(event.clientX,event.clientY);}}} onPointerCancel={()=>{if(touchPointer.current!==null)finish();}} onKeyDown={event=>{
      if(!event.altKey||!["ArrowUp","ArrowDown"].includes(event.key))return;event.preventDefault();
      const resolved=editor.state.doc.resolve(block.from);const previous=resolved.nodeBefore,next=editor.state.doc.nodeAt(block.to);
      if(event.key==="ArrowUp"&&previous)move(block.from,block.to,block.from-previous.nodeSize);
      if(event.key==="ArrowDown"&&next)move(block.from,block.to,block.to+next.nodeSize);
    }}><GripVertical size={16}/></button>}
  </div>;
}

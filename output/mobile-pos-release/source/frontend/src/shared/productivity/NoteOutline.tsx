import { useEffect,useState } from "react";
import type { Editor } from "@tiptap/core";
import { ChevronDown,ChevronRight,ListTree } from "lucide-react";
import { noteSectionsKey } from "./noteSections";
export default function NoteOutline({editor}:{editor:Editor}){
  const [open,setOpen]=useState(false);const [,update]=useState(0);
  useEffect(()=>{const refresh=()=>update(value=>value+1);editor.on("transaction",refresh);return()=>{editor.off("transaction",refresh);};},[editor]);
  const headings:{position:number;title:string;level:number}[]=[];
  editor.state.doc.forEach((node,position)=>{if(node.type.name==="heading")headings.push({position,title:node.textContent||"Untitled section",level:node.attrs.level});});
  const folded=noteSectionsKey.getState(editor.state)||new Set<number>();
  return <div className="note-outline"><button type="button" aria-label="Document outline" aria-expanded={open} onClick={()=>setOpen(!open)}><ListTree size={15}/>Outline <small>{headings.length}</small></button>{open&&<nav aria-label="Document outline"><p>Jump to a heading or fold its section.</p>{!headings.length&&<p>Add a heading to build your outline.</p>}{headings.map(heading=><div key={heading.position} style={{paddingLeft:(heading.level-1)*12}}><button type="button" aria-label={`${folded.has(heading.position)?"Expand":"Collapse"} section ${heading.title}`} aria-expanded={!folded.has(heading.position)} onClick={()=>editor.view.dispatch(editor.state.tr.setMeta(noteSectionsKey,heading.position))}>{folded.has(heading.position)?<ChevronRight size={14}/>:<ChevronDown size={14}/>}</button><button type="button" onClick={()=>{const transaction=editor.state.tr;if(folded.has(heading.position))transaction.setMeta(noteSectionsKey,heading.position);editor.view.dispatch(transaction);editor.chain().focus().setTextSelection(heading.position+1).scrollIntoView().run();}}>{heading.title}</button></div>)}</nav>}</div>;
}

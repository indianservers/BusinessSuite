import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
export const noteSectionsKey=new PluginKey<Set<number>>("noteSections");
export const NoteSections=Extension.create({
  name:"noteSections",
  addProseMirrorPlugins(){return [new Plugin({
    key:noteSectionsKey,
    state:{init:()=>new Set<number>(),apply(transaction,prior){
      const next=new Set<number>();prior.forEach(position=>{const mapped=transaction.mapping.map(position);if(transaction.doc.nodeAt(mapped)?.type.name==="heading")next.add(mapped);});
      const toggle=transaction.getMeta(noteSectionsKey);if(typeof toggle==="number"){if(next.has(toggle))next.delete(toggle);else next.add(toggle);}
      if(transaction.selectionSet&&typeof toggle!=="number")for(const position of next){const heading=transaction.doc.nodeAt(position);if(!heading)continue;let end=transaction.doc.content.size;transaction.doc.forEach((node,offset)=>{if(offset>position&&offset<end&&node.type.name==="heading"&&node.attrs.level<=heading.attrs.level)end=offset;});if(transaction.selection.head>=position+heading.nodeSize&&transaction.selection.head<end)next.delete(position);}
      return next;
    }},
    props:{decorations(state){
      const folded=noteSectionsKey.getState(state)||new Set<number>();const decorations:Decoration[]=[];let level=0;
      state.doc.forEach((node,position)=>{
        const heading=node.type.name==="heading";
        if(heading&&level&&node.attrs.level<=level)level=0;
        if(level)decorations.push(Decoration.node(position,position+node.nodeSize,{class:"note-folded-block"}));
        if(heading&&folded.has(position)&&!level)level=node.attrs.level;
      });return DecorationSet.create(state.doc,decorations);
    }},
  })];},
});

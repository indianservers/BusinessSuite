import {useState} from 'react';

export type ArtifactSlide={title:string;bullets:string[]};
export default function SlidePreview({slides,label='Presentation',disabled=false,onChange}:{slides:ArtifactSlide[];label?:string;disabled?:boolean;onChange?:(slides:ArtifactSlide[])=>void}){
 const [index,setIndex]=useState(0);const position=Math.min(index,Math.max(0,slides.length-1));const slide=slides[position];
 function update(value:ArtifactSlide){onChange?.(slides.map((s,i)=>i===position?value:s))}
 if(!slide)return <p>No slides in this draft.</p>;
 return <section className="bot-slide-deck" aria-label={label}>
  <div className="bot-file-actions"><button type="button" disabled={position===0} onClick={()=>setIndex(n=>Math.max(0,n-1))}>Previous slide</button><span>Slide {position+1} of {slides.length}</span><button type="button" disabled={position>=slides.length-1} onClick={()=>setIndex(n=>n+1)}>Next slide</button></div>
  <div className="bot-slide-preview"><h4>{slide.title}</h4><ul>{slide.bullets.map((point,i)=><li key={i}>{point}</li>)}</ul></div>
  {onChange&&<fieldset disabled={disabled}><legend>Edit slide {position+1}</legend><label>Slide title<input aria-label={`${label} slide ${position+1} title`} maxLength={160} value={slide.title} onChange={e=>update({...slide,title:e.target.value})}/></label>{slide.bullets.map((point,i)=><label key={i}>Point {i+1}<textarea aria-label={`${label} slide ${position+1} point ${i+1}`} maxLength={240} rows={2} value={point} onChange={e=>update({...slide,bullets:slide.bullets.map((p,j)=>j===i?e.target.value:p)})}/></label>)}</fieldset>}
  <small>Long slides continue across export pages. Sources, when available, appear after the slides.</small>
 </section>
}

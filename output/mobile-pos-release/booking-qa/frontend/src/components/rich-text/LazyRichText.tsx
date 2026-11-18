import type { RichTextEditorProps } from "./RichTextEditor";
import {lazy,Suspense,forwardRef,type TextareaHTMLAttributes} from "react";
const EditorField=lazy(()=>import("./RichTextEditor").then(module=>({default:module.RichTextField})));
export const RichTextField=forwardRef<HTMLTextAreaElement,TextareaHTMLAttributes<HTMLTextAreaElement>>((props,ref)=><Suspense fallback={<p role="status">Loading editor...</p>}><EditorField {...props} ref={ref}/></Suspense>);
export {RichTextContent,richTextPlainText} from "./RichTextContent";

const Editor=lazy(()=>import("./RichTextEditor"));
export default function RichTextEditor(props:RichTextEditorProps){return <Suspense fallback={<p role="status">Loading editor...</p>}><Editor {...props}/></Suspense>;}
export type {RichTextEditorProps} from "./RichTextEditor";

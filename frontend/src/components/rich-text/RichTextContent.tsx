import { contentToHtml } from "./content";
import "./rich-text.css";
export function RichTextContent({value,className="",legacyFormat="markdown"}:{value?:string|null;className?:string;legacyFormat?:"plain"|"markdown"|"html"}) {
 return <div className={`suite-rich-content ${className}`} dangerouslySetInnerHTML={{__html:contentToHtml(value||"",legacyFormat)}}/>;
}
export {richTextPlainText} from "./content";

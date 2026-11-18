import { RichTextContent } from "@/components/rich-text/RichTextContent";
export default function DocumentPreview({ content }: { content: string }) { return <RichTextContent value={content}/>; }

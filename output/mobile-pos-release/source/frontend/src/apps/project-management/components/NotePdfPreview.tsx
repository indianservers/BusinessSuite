import { useEffect, useRef, useState } from "react";
import { getDocument, GlobalWorkerOptions, type PDFDocumentProxy } from "pdfjs-dist";
import pdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { Button } from "@/components/ui/button";

GlobalWorkerOptions.workerSrc = pdfWorker;

export default function NotePdfPreview({ file }: { file: Blob }) {
  const [document, setDocument] = useState<PDFDocumentProxy | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [width, setWidth] = useState(700);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [text, setText] = useState("");
  const container = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    let active = true;
    let cancel: (() => void) | undefined;
    setLoading(true); setError(""); setPageNumber(1); setDocument(null);
    void file.arrayBuffer().then(async bytes => {
      if (!active) return;
      // Only render page graphics/text; never instantiate PDF scripting or form actions.
      const task = getDocument({ data: new Uint8Array(bytes), enableXfa: false, useSystemFonts: true, stopAtErrors: true });
      cancel = () => { void task.destroy().catch(() => undefined); };
      const pdf = await task.promise;
      if (active) setDocument(pdf);
    }).catch(() => { if (active) { setError("This PDF cannot be previewed. Download it to view it in your PDF application."); setLoading(false); } });
    return () => { active = false; cancel?.(); };
  }, [file]);
  useEffect(() => {
    if (!container.current) return;
    const observer = new ResizeObserver(entries => { setWidth(Math.max(160, Math.min(740, entries[0].contentRect.width))); });
    observer.observe(container.current); return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!document || !canvas.current) return;
    let active = true;
    let cancel: (() => void) | undefined;
    setLoading(true); setError("");
    void document.getPage(pageNumber).then(async page => {
      if (!active || !canvas.current) return;
      const original = page.getViewport({ scale: 1 });
      const viewport = page.getViewport({ scale: width / original.width });
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      const target = canvas.current;
      target.width = Math.ceil(viewport.width * ratio); target.height = Math.ceil(viewport.height * ratio);
      target.style.width = `${viewport.width}px`; target.style.height = `${viewport.height}px`;
      const task = page.render({ canvas: target, viewport, transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0] });
      cancel = () => task.cancel();
      await task.promise;
      const content = await page.getTextContent();
      if (active) { setText(content.items.map(item => "str" in item ? item.str : "").join(" ")); setLoading(false); }
    }).catch(error => { if (active && error?.name !== "RenderingCancelledException") { setError("This page could not be rendered. You can still download the PDF."); setLoading(false); } });
    return () => { active = false; cancel?.(); };
  }, [document, pageNumber, width]);
  return <div ref={container} className="note-pdf-preview">
    <div className="note-pdf-controls"><Button variant="outline" size="sm" disabled={!document || pageNumber <= 1 || loading} onClick={() => setPageNumber(p => p - 1)}>Previous page</Button><span>Page {pageNumber} of {document?.numPages ?? "…"}</span><Button variant="outline" size="sm" disabled={!document || pageNumber >= document.numPages || loading} onClick={() => setPageNumber(p => p + 1)}>Next page</Button></div>
    {loading && <p role="status">Rendering private PDF…</p>}{error && <p role="alert">{error}</p>}
    <canvas ref={canvas} role="img" aria-label={`PDF page ${pageNumber}`} />
    <p className="sr-only">{text}</p>
  </div>;
}

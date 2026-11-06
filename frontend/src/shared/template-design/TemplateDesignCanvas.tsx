import { useState } from 'react';
import RichTextEditor, { richTextPlainText } from '@/components/rich-text/LazyRichText';
import type { DesignBlock, TemplateDesign } from './types';
import './template-design.css';

type Props = {
  design: TemplateDesign;
  renderedBlocks: {id: string; html: string}[] | null;
  selected: string;
  labels: Record<DesignBlock['type'], string>;
  readOnly?: boolean;
  busy?: boolean;
  onSelect: (id: string) => void;
  onChange: (id: string, changes: Partial<DesignBlock>) => void;
  onMove: (id: string, target: string) => void;
  onAddText: () => void;
  onEdit?: () => void;
};

/** Shared flowing design canvas for email, invoice and mail-merge layouts.
 * Editing uses the suite's existing rich-text editor and drag handle system.
 * The authoritative server output supplies every non-editing block.
 */
export default function TemplateDesignCanvas({design, renderedBlocks, selected, labels, readOnly, busy, onSelect, onChange, onMove, onAddText, onEdit}: Props) {
  const [editing, setEditing] = useState('');
  const [dragged, setDragged] = useState('');
  return <div className="ts-paper template-design-paper" style={{background: design.background, fontFamily: design.font}} aria-label="Shared template design canvas" aria-busy={busy}>
    {renderedBlocks ? renderedBlocks.map(rendered => {
      const source = design.blocks.find(block => block.id === rendered.id);
      if (!source) return null;
      const editable = !readOnly && ['brand', 'heading', 'text', 'signature'].includes(source.type);
      const active = editing === source.id && selected === source.id && editable;
      return <div key={source.id} className={`template-design-block ts-canvas-block ${selected === source.id ? 'selected' : ''}`} role="button" tabIndex={0} aria-label={`Select ${labels[source.type]} block`}
        draggable={!readOnly && !busy && !active} onDragStart={() => setDragged(source.id)} onDragOver={e => e.preventDefault()} onDrop={e => {e.preventDefault(); onMove(dragged, source.id);}}
        onClick={e => {if (!active) e.preventDefault(); onSelect(source.id);}}
        onDoubleClick={() => {if (editable) {onSelect(source.id); setEditing(source.id); onEdit?.();}}}
        onKeyDown={e => {if (!active && (e.key === 'Enter' || e.key === ' ')) {e.preventDefault(); onSelect(source.id);} if (e.key === 'Escape') setEditing('');}}>
        {active ? <div className="template-design-text" onClick={e => e.stopPropagation()} onKeyDown={e => e.stopPropagation()}>
          <RichTextEditor key={source.id} label="Edit canvas text" variant="compact" legacyFormat={source.html ? 'html' : 'plain'} value={source.html || source.text} disabled={busy} maxLength={15000}
            onChange={html => onChange(source.id, {html, text: richTextPlainText(html)})}/>
          <button type="button" className="template-design-done" onClick={() => setEditing('')}>Done editing</button>
        </div> : <div dangerouslySetInnerHTML={{__html: rendered.html}}/>}
      </div>;
    }) : <p className="ts-loading" role="status">Preparing your design…</p>}
    {!design.blocks.length && <button className="ts-empty-paper" disabled={readOnly} onClick={onAddText}>+ Add your first text block</button>}
  </div>;
}

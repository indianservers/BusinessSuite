export type BlockType = 'brand' | 'heading' | 'text' | 'image' | 'button' | 'divider' | 'spacer' | 'items' | 'totals' | 'signature' | 'columns';
export type DesignBlock = { id: string; type: BlockType; text: string; html?: string; columns?: 2 | 3; url: string; align: 'left' | 'center' | 'right'; size: number; color: string; bold: boolean; padding: number };
export type TemplateDesign = { blocks: DesignBlock[]; accent: string; background: string; font: string };

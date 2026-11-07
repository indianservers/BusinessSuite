const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const { Schema } = require('@tiptap/pm/model');
const { EditorState, AllSelection, TextSelection } = require('@tiptap/pm/state');
const { lift } = require('@tiptap/pm/commands');
const source = fs.readFileSync(path.join(__dirname, '../src/components/rich-text/blockSelection.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const exported = {};
vm.runInNewContext(compiled, { exports: exported, require });
const { blockTextSelection } = exported;
const schema = new Schema({ nodes: {
  doc: { content: 'block+' },
  paragraph: { content: 'text*', group: 'block' },
  blockquote: { content: 'block+', group: 'block' },
  codeBlock: { content: 'text*', group: 'block', code: true },
  text: {},
} });
const paragraph = schema.node('paragraph', null, schema.text('QA selection'));
for (const block of [paragraph, schema.node('blockquote', null, paragraph), schema.node('codeBlock', null, schema.text('QA selection'))]) {
  const doc = schema.node('doc', null, block);
  const state = EditorState.create({ doc, selection: new AllSelection(doc) });
  const range = blockTextSelection(state);
  assert.ok(range.from > 0 && range.to < doc.content.size);
  assert.equal(doc.textBetween(range.from, range.to), 'QA selection');
}
const quoteDoc = schema.node('doc', null, schema.node('blockquote', null, paragraph));
const wholeQuote = EditorState.create({ doc: quoteDoc, selection: new AllSelection(quoteDoc) });
assert.equal(lift(wholeQuote), false, 'Document-edge selection cannot lift the quote');
const normalized = blockTextSelection(wholeQuote);
const insideQuote = wholeQuote.apply(wholeQuote.tr.setSelection(TextSelection.create(quoteDoc, normalized.from, normalized.to)));
let lifted;
assert.equal(lift(insideQuote, transaction => { lifted = insideQuote.apply(transaction); }), true);
assert.equal(lifted.doc.firstChild.type.name, 'paragraph');
assert.equal(lifted.doc.textContent, 'QA selection');
const partial = EditorState.create({ doc: quoteDoc, selection: TextSelection.create(quoteDoc, 3, 5) });
assert.equal(blockTextSelection(partial), undefined, 'Partial selections must remain unchanged');
const emptyDoc = schema.node('doc', null, schema.node('paragraph'));
const empty = blockTextSelection(EditorState.create({ doc: emptyDoc, selection: new AllSelection(emptyDoc) }));
assert.equal(empty.from, 1);
assert.equal(empty.to, 1);
console.log('6 block-selection regression scenarios passed');

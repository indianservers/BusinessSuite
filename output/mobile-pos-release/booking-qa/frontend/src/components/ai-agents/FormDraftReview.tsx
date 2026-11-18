import {useState} from 'react';
import FormBuilder from '@/features/forms/FormBuilder';
import FormResponse from '@/features/forms/FormResponse';
import type {Definition} from '@/features/forms/formsTypes';
import {api} from '@/services/api';
import '@/features/forms/FormsPage.css';
export type FormReview={operation:string;definition:Definition;audience:string;form_id:number|null;effect:string;changes:{field:string;before:unknown;after:unknown}[]};
export default function FormDraftReview({review,value,onChange}:{review:FormReview;value?:Definition;onChange?:(value:Definition)=>void}){
 const draft=value||review.definition;const [selected,setSelected]=useState(draft.fields[0]?.id||''),[error,setError]=useState('');
 return <section className="bot-result-card suite-forms" aria-label="Native form review"><h3>{draft.name}</h3>{review.form_id&&<p>Form #{review.form_id}</p>}<p>{review.effect}</p><p><strong>Audience on publication:</strong> {draft.settings?.public?'Anyone with the public link':review.audience}</p>
  {draft.workflow?.enabled&&<p>Task intake is enabled for project #{draft.workflow.project_id}. New valid submissions will create tasks when this form is published and open.</p>}
  {review.operation==='publish'&&<p role="note">Approving this action publishes this exact saved draft and opens intake. Review the audience, questions and workflow first.</p>}
  <FormResponse definition={draft} disabled submit={async()=>{}}/>
  <details><summary>All {draft.fields.length} questions and conditions</summary><ol>{draft.fields.map(field=><li key={field.id}><strong>{field.label}</strong> · {field.type} · {field.required?'Required':'Optional'} · {field.id}{field.options?.length?` · Choices: ${field.options.join(', ')}`:''}{field.condition?` · When ${draft.fields.find(source=>source.id===field.condition!.field)?.label||field.condition.field} ${field.condition.operator} ${field.condition.value}`:''}</li>)}</ol></details>
  {review.changes.length>0&&<details><summary>Before and after changes</summary>{review.changes.map(change=><div key={change.field}><strong>{change.field.replace(/_/g,' ')}</strong><pre className="whitespace-pre-wrap break-words">Current: {JSON.stringify(change.before,null,2)}{'\n'}Proposed: {JSON.stringify(change.after,null,2)}</pre></div>)}</details>}
  {onChange&&<details><summary>Edit form questions</summary><FormBuilder draft={draft} selected={selected} setSelected={setSelected} edit={onChange} error={setError} importForm={async value=>{const result=await api.post('/forms/validate',value);onChange(result.data)}} share={()=>{}} close={()=>{}} open={false} reviewMode/><p>These edits require saving a new review. They do not publish or submit this form.</p></details>}
  {error&&<p role="alert">{error}</p>}
 </section>
}

import {useMemo} from 'react';
import EmployeeCategoryMultiSelect from './EmployeeCategoryMultiSelect';
import {parseCategorySelections,useEmployeeTaxonomy} from './employee-category-taxonomy';
export default function ServiceEmployeeCategoryFields({categories,subcategories,onChange}:{categories:string;subcategories:string;onChange:(categories:string,subcategories:string)=>void}){
 const query=useEmployeeTaxonomy();const tree=query.data?.categories||[];const stored=parseCategorySelections(categories),storedChildren=parseCategorySelections(subcategories);
 const parents=useMemo(()=>[...new Set(stored.map(value=>tree.find(x=>x.children.some(c=>c.value===value))?.value||value))],[categories,tree]);
 const inferred=tree.flatMap(x=>x.children).filter(x=>stored.includes(x.value)).map(x=>x.value),selectedChildren=[...new Set([...storedChildren,...inferred])];
 const parentOptions=tree.filter(x=>x.active).map(x=>({value:x.value,label:x.name}));const childOptions=tree.filter(x=>x.active&&parents.includes(x.value)).flatMap(x=>x.children.filter(c=>c.active).map(c=>({value:c.value,label:c.name+' · '+x.name})));
 const changeParents=(values:string[])=>{const valid=new Set(tree.filter(x=>x.active&&values.includes(x.value)).flatMap(x=>x.children.filter(c=>c.active).map(c=>c.value)));onChange(JSON.stringify(values),JSON.stringify(selectedChildren.filter(x=>valid.has(x))));};
 return <><EmployeeCategoryMultiSelect label="Employee categories" value={parents} options={parentOptions} onChange={changeParents} loading={query.isPending} error={query.isError} retry={()=>{void query.refetch();}} empty="No HRMS categories. Add them in HRMS."/><EmployeeCategoryMultiSelect label="Employee subcategories" value={selectedChildren.filter(x=>childOptions.some(c=>c.value===x))} options={childOptions} onChange={values=>onChange(JSON.stringify(parents),JSON.stringify(values))} disabled={!parents.length||query.isPending} placeholder={parents.length?'Select':'Choose categories first'} empty="No subcategories for these categories"/></>;
}

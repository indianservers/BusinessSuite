const fs=require('fs'),ts=require('../frontend/node_modules/typescript');
const configs=[
 ['frontend/src/apps/fam/FAMWorkspacePage.tsx','Card',s=>s.includes('Create SRM product')&&s.includes('fields.map')&&!s.includes('Stock items'),'{isSrmInventory ? "Create SRM product" : "Create item"}',''],
 ['frontend/src/apps/hrms/pages/employees/EmployeeDetailPage.tsx','CompactForm',s=>s.includes('createUserAccountMutation.mutate'),'"Create employee login"',''],
 ['frontend/src/apps/project-management/pages/TagManagerPage.tsx','CompactForm',s=>s.includes('Save tag'),'"Create tag"',' inline={!!editing}'],
 ['frontend/src/apps/project-management/pages/TeamsPage.tsx','CompactForm',s=>s.includes('Save team'),'"Create team"',' inline={!!editing}'],
 ['frontend/src/apps/project-management/pages/MilestonesPage.tsx','Card',s=>s.includes('Create milestone')&&s.includes('onSubmit={submit}'),'"Create milestone"',''],
 ['frontend/src/apps/project-management/pages/RisksPage.tsx','Card',s=>s.includes('Close risk form')&&s.includes('onSubmit={submit}'),'{editing ? "Edit risk" : "Add risk"}',' autoOpen onClose={resetForm}'],
 ['frontend/src/apps/project-management/pages/TaskDetail.tsx','CompactForm',s=>s.includes('onSubmit={addChecklistItem}'),'"Add checklist item"',''],
 ['frontend/src/apps/project-management/pages/TaskDetail.tsx','CompactForm',s=>s.includes('onSubmit={addTag}'),'"Add tag"',''],
 ['frontend/src/apps/project-management/pages/TaskDetail.tsx','CompactForm',s=>s.includes('onSubmit={addSubtask}'),'"Create subtask"',''],
 ['frontend/src/apps/project-management/pages/WorkspaceMemberPanel.tsx','form',s=>s.includes('invite.mutate()'),'"Invite workspace member"','']
];
for(const [file,tag,match,title,props] of configs){let s=fs.readFileSync(file,'utf8');const sf=ts.createSourceFile(file,s,99,true,4);let nodes=[];function walk(n){if(ts.isJsxElement(n)&&n.openingElement.tagName.getText(sf)===tag&&match(n.getText(sf)))nodes.push(n);ts.forEachChild(n,walk);}walk(sf);if(nodes.length!==1)throw Error(file+' '+tag+' matches '+nodes.length);const n=nodes[0];let inner=n.getText(sf);if(tag==='CompactForm'&&/onSubmit=\{(?:addChecklistItem|addTag|addSubtask|submit)\}/.test(inner))inner=inner.replace('<Button type="submit"','<Button data-save-action type="submit"').replace('<Button aria-label="Add subtask"','<Button data-save-action aria-label="Add subtask"');s=s.slice(0,n.getStart(sf))+`<SmartCreateSection title=${title}${props}>`+inner+'</SmartCreateSection>'+s.slice(n.end);if(!/import\s*\{[^}]*SmartCreateSection/.test(s))s='import {SmartCreateSection} from "@/shared/creation/SmartCreateSection";\n'+s;fs.writeFileSync(file,s);console.log(file,tag,title);}

const fs=require('fs'),ts=require('../frontend/node_modules/typescript');
const configs=[
 ['frontend/src/apps/project-management/pages/GanttPage.tsx','CompactForm',s=>s.includes('void createDependency()'),'"Add dependency"',''],
 ['frontend/src/components/scheduling/ModuleGanttPage.tsx','CompactForm',s=>s.includes('Add dependency'),'"Add dependency"',''],
 ['frontend/src/apps/hrms/pages/employees/ProbationPage.tsx','Card',s=>s.includes('Manager review')&&s.includes('submitReview.mutate()'),'"Submit probation review"',''],
 ['frontend/src/apps/project-management/components/InlineSubtaskComposer.tsx','CompactForm',s=>s.includes('Save subtask'),'"Create subtask"',' autoOpen onClose={onCancel}'],
 ['frontend/src/shared/communication/MeetingPanel.tsx','CompactForm',s=>s.includes('Save meeting'),'"Schedule meeting"',' autoOpen onClose={()=>setOpen(false)}'],
 ['frontend/src/shared/productivity/ProductivityWorkspace.tsx','CompactForm',s=>s.includes('Notebook name'),'"Create notebook"',' autoOpen onClose={()=>setFolderName(null)}'],
 ['frontend/src/shared/productivity/TaskCreationForm.tsx','section',s=>s.startsWith('<section className="crm-task-creation"'),'"Create task"',' inline={!!initialDraft} autoOpen onClose={onCancel}'],
 ['frontend/src/apps/project-management/ProjectManagementHomePage.tsx','CompactForm',s=>s.includes('Submit Intake'),'"Submit intake"',''],
 ['frontend/src/apps/saas/PortalPage.tsx','Card',s=>s.includes('Submit lead')&&s.includes('onSubmit'),'"Submit lead"','']
];
for(const [file,tag,match,title,props] of configs){let s=fs.readFileSync(file,'utf8');const sf=ts.createSourceFile(file,s,99,true,4);const nodes=[];function walk(n){if(ts.isJsxElement(n)&&n.openingElement.tagName.getText(sf)===tag&&match(n.getText(sf)))nodes.push(n);ts.forEachChild(n,walk);}walk(sf);if(nodes.length!==1)throw Error(file+' '+nodes.length);const n=nodes[0];let inner=n.getText(sf);if(tag==='CompactForm')inner=inner.replace('<Button type="submit"','<Button data-save-action type="submit"').replace('<button type="submit"','<button data-save-action type="submit"');s=s.slice(0,n.getStart(sf))+`<SmartCreateSection title=${title}${props}>`+inner+'</SmartCreateSection>'+s.slice(n.end);if(!/import\s*\{[^}]*SmartCreateSection/.test(s))s='import {SmartCreateSection} from "@/shared/creation/SmartCreateSection";\n'+s;if(file.includes('InlineSubtaskComposer'))s=s.replace('event.stopPropagation();\n    if (event.key === "Escape" && !busy) { event.preventDefault(); onCancel(); }','if (event.key !== "Escape") event.stopPropagation();');fs.writeFileSync(file,s);console.log(file);}

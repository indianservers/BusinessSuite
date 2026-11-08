// Reviewed source-only migration: preserve existing JSX, owner state, validation and handlers.
const fs=require('node:fs'),ts=require('../frontend/node_modules/typescript');
const rows=JSON.parse(fs.readFileSync('outputs/creation-inventory/all-module-creation-surfaces.json','utf8'));
const forms={
 'frontend/src/apps/communication/center/CampaignWorkspace.tsx':/Create reviewed draft/,
 'frontend/src/apps/communication/center/CustomerMatchingReview.tsx':/Create and link record/,
 'frontend/src/apps/crm/CRMReportBuilder.tsx':/Save and run report/,
 'frontend/src/apps/fam/RecurringPurchasesPage.tsx':/Create recurring schedule/,
 'frontend/src/apps/hrms/pages/compliance/BackgroundVerificationPage.tsx':/Save vendor/,
 'frontend/src/apps/hrms/pages/compliance/EmployeeVerificationPanel.tsx':/Create verification case|Upload to employee documents/,
 'frontend/src/apps/hrms/pages/compliance/VerificationCasePanel.tsx':/Add check/,
 'frontend/src/apps/hrms/pages/employees/EmployeeIncrements.tsx':/Submit increment/,
 'frontend/src/apps/hrms/pages/engagement/EngagementPage.tsx':/Publish/,
 'frontend/src/apps/hrms/pages/interns/InternApplicationSettings.tsx':/Add role/,
 'frontend/src/apps/hrms/pages/interns/InternsHubAdminPage.tsx':/Publish Module/,
 'frontend/src/apps/hrms/pages/interns/InternTaskProgramsPanel.tsx':/Save task pack/,
 'frontend/src/apps/hrms/pages/profile/ProfilePage.tsx':/Upload document/,
 'frontend/src/apps/hrms/pages/recruitment/HiringCandidateDetails.tsx':/Schedule interview|Create employee/,
 'frontend/src/apps/hrms/pages/recruitment/RecruitmentPage.tsx':/Add candidate/,
 'frontend/src/apps/project-management/components/ExternalDeliveryPanel.tsx':/Add webhook connection/,
 'frontend/src/apps/project-management/components/ProjectPreviewDetails.tsx':/Add milestone|Save private note/,
 'frontend/src/apps/project-management/pages/FilesPage.tsx':/Create folder/,
 'frontend/src/apps/project-management/pages/KanbanBoard.tsx':/Create pipeline/,
 'frontend/src/apps/project-management/pages/TaskTypesPage.tsx':/Save and create fields/,
 'frontend/src/components/reports/ReportDeliverySchedule.tsx':/Save delivery schedule/,
 'frontend/src/shared/follow-ups/FollowUpsPage.tsx':/Save follow-up/,
 'frontend/src/shared/master-data/RelationshipEditor.tsx':/Save relationship/,
 'frontend/src/shared/pipeline/PipelineDomainDetails.tsx':/Schedule follow-up/,
};
const cards={
 'frontend/src/apps/automation/AutomationStudioPage.tsx':/Create Workflow/,
 'frontend/src/apps/crm/CRMWorkspacePage.tsx':/^$/,
 'frontend/src/apps/hrms/pages/employees/EmployeeDirectoryPage.tsx':/Report Wrong Info/,
 'frontend/src/apps/hrms/pages/leave/LeavePage.tsx':/Employee Account Wizard|Leave Encashment/,
 'frontend/src/apps/hrms/pages/lms/LMSPage.tsx':/Publish Course/,
 'frontend/src/apps/hrms/pages/payroll/PayrollPage.tsx':/^(LOP Adjustment|Overtime Pay|Leave Encashment|Legal Entity|Pay Group|Salary Components|Salary Structure|Statutory Profiles|Pay Groups and Calendar|Salary Templates|Tax Declarations|Proof Workflow)$/,
};
const selected=rows.filter(r=>!r.protected && ((['form','CompactForm'].includes(r.kind)&&forms[r.file]?.test(r.actions.join(' | '))) || (r.kind==='CardContent'&&cards[r.file]?.test(r.title)&& (r.title||r.actions.join('')==='Create'))));
const log=[];
for(const file of new Set(selected.map(r=>r.file))){
 let text=fs.readFileSync(file,'utf8');const sf=ts.createSourceFile(file,text,99,true,4),edits=[];
 function visit(n){const row=selected.find(r=>r.file===file&&r.start===n.getStart(sf)&&r.end===n.end);if(row){
   let start=n.getStart(sf),end=n.end,original=n.getText(sf);
   // Retain registry/history/list content on the originating page.
   if(row.kind==='CardContent'){
    const children=n.children.filter(c=>!ts.isJsxText(c)||c.text.trim());
    let last=children.findIndex(c=>/GroupedRecords|GridTable|<table/.test(c.getText(sf)));
    if(last===0)return;
    const formChildren=last<0?children:children.slice(0,last);
    if(!formChildren.length)return;
    start=formChildren[0].getStart(sf);end=formChildren.at(-1).end;
    original=`<div className="space-y-4">${text.slice(start,end)}</div>`;
   }
   const action=row.actions.find(a=>!/^Add (Lesson|Question|criterion|weekly step|line)/i.test(a))||row.actions[0];
   const title=row.title?(/^(create|new|add|request|upload|publish|submit)/i.test(row.title)?row.title:`Create ${row.title.toLowerCase()}`):action;
   const size=row.fields>10?'large':row.fields>3?'standard':'compact';
   edits.push({start,end,text:`<SmartCreateSection title=${JSON.stringify(title)} size="${size}">${original}</SmartCreateSection>`});log.push({file,line:row.line,title,size,formOnly:true,actions:row.actions});return;
  }ts.forEachChild(n,visit);
 }visit(sf);
 for(const e of edits.sort((a,b)=>b.start-a.start))text=text.slice(0,e.start)+e.text+text.slice(e.end);
 if(edits.length&&!text.includes('import { SmartCreateSection }'))text='import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";\n'+text;
 fs.writeFileSync(file,text);
}
const target='outputs/creation-inventory/remaining-creation-migrations.json';fs.writeFileSync(target,JSON.stringify(log,null,2));console.log(JSON.stringify(log,null,2));

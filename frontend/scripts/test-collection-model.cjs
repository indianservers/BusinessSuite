const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),ts=require('typescript'),Module=require('node:module');
const filename=path.resolve(__dirname,'../src/shared/data-grid/collection-model.ts');const loaded=new Module(filename,module);loaded.filename=filename;loaded.paths=Module._nodeModulePaths(path.dirname(filename));loaded._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,filename);
const {calendarDay,percentage,scheduleRecords,statusCounts}=loaded.exports;
assert.equal(calendarDay('2026-11-08'),Date.UTC(2026,10,8));assert.equal(calendarDay('08/11/2026'),Date.UTC(2026,10,8));assert.equal(calendarDay('31/02/2026'),undefined);assert.equal(calendarDay('2026-02-30'),undefined);assert.equal(calendarDay('unknown'),undefined);assert.equal(calendarDay('2026-11-08Tinvalid'),undefined);
for(const value of [null,undefined,'',-1,101,'unknown'])assert.equal(percentage(value),undefined);assert.equal(percentage('50%'),50);assert.equal(percentage(0),0);
const rows=[{name:'Scheduled',start:'2026-11-01',end:'2026-11-08',status:'Active',progress:50},{name:'Reversed',start:'2026-11-08',end:'2026-11-01',status:'Active',progress:0},{name:'Missing',start:'',end:'2026-11-08',status:'Done',progress:100}];const fields=[['name','Name'],['start','Start date'],['end','End date'],['status','Status'],['progress','Progress']].map(([id,title])=>({id,title,value:row=>row[id]}));
assert.equal(scheduleRecords(rows,fields).length,1);assert.equal(scheduleRecords(rows,fields)[0].progress,50);assert.equal(scheduleRecords(rows,fields.filter(f=>f.id!=='start')).length,0);
assert.equal(scheduleRecords(rows,fields.map(f=>f.id==='start'?{...f,title:'Created'}:f)).length,0,'Creation time is not a planned start');
assert.deepEqual(statusCounts(rows,fields),[{title:'Active',count:2},{title:'Done',count:1}]);const many=Array.from({length:8},(_,i)=>({status:'Status '+i}));assert.equal(statusCounts(many,fields).reduce((sum,row)=>sum+row.count,0),8);
console.log('Collection model checks passed');

const localFile=path.resolve(__dirname,'../src/shared/data-grid/local-source.ts');const local=new Module(localFile,module);local.filename=localFile;local.paths=Module._nodeModulePaths(path.dirname(localFile));local._compile(ts.transpileModule(fs.readFileSync(localFile,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,localFile);
const source=local.exports.localGridSource('test',rows,fields.map(field=>({id:field.id,title:field.title,accessor:field.value})),row=>row.name);
const query={search:'Scheduled',filters:{logic:'and',rules:[]},sorting:[],grouping:['status'],path:[],page:1,pageSize:1};assert.equal(source.summaryRows(query).length,1);assert.equal(source.summaryRows({...query,search:''}).length,3,'Summaries must ignore collapsed groups and pagination');
console.log('Filtered summary scope checks passed');

const definitionsFile=path.resolve(__dirname,'../src/shared/data-grid/collection-definitions.ts');const definitions=new Module(definitionsFile,module);definitions._compile(ts.transpileModule(fs.readFileSync(definitionsFile,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,definitionsFile);
assert.deepEqual(definitions.exports.collectionDefinition('/hrms/exit:records-1').columns,['employee_id','exit_type','status','resignation_date','last_working_date']);assert(definitions.exports.collectionDefinition('/hrms/onboarding:records-1').columns.includes('expected_end'));assert(definitions.exports.collectionDefinition('/hrms/benefits:records-1').columns.includes('employer_contribution'));assert(!definitions.exports.collectionDefinition('/crm/contacts').columns.includes('progress'));
console.log('Entity default column checks passed');

const alternatives=[{name:'Planned',start:'',end:'',plannedStart:'2026-11-03',plannedEnd:'2026-11-09'},{name:'Standard',start:'2026-11-02',end:'2026-11-05'}];
const alternativesFields=[...fields,{id:'plannedStart',title:'Planned start date',value:row=>row.plannedStart},{id:'plannedEnd',title:'Planned end date',value:row=>row.plannedEnd}];
assert.equal(scheduleRecords(alternatives,alternativesFields).length,2,'Blank default dates must not mask valid alternate schedules');
assert.equal(scheduleRecords(alternatives,alternativesFields)[0].start,Date.UTC(2026,10,3));
console.log('Alternate date-pair regressions passed');

const leaveFields=fields.map(field=>field.id==='start'?{...field,title:'From'}:field.id==='end'?{...field,title:'To'}:field);assert.equal(scheduleRecords(rows,leaveFields).length,1,'Leave date ranges must expose the applicable Gantt schedule');
const calculatedFields=fields.map(field=>field.id==='start'?{...field,title:'Calculated start'}:field.id==='end'?{...field,title:'Calculated due'}:field);assert.equal(scheduleRecords(rows,calculatedFields).length,1,'Calculated plans must expose their schedule without treating it as applied');
console.log('Leave and calculated-plan schedule checks passed');

const meetingFields=[{id:'title',title:'Meeting',value:row=>row.title},{id:'start_time',title:'Start time',value:row=>row.start},{id:'end_time',title:'End time',value:row=>row.end}];
assert.equal(scheduleRecords([{title:'Review',start:'2026-11-08T09:00:00Z',end:'2026-11-08T10:00:00Z'}],meetingFields).length,1,'Recorded meeting times expose a calendar-day Gantt');
assert.equal(scheduleRecords([{title:'Unscheduled',start:'',end:''}],meetingFields).length,0);
console.log('Meeting schedule checks passed');

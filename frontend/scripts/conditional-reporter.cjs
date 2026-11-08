const fs=require('fs'),path=require('path');
const file=path.resolve(__dirname,'../../outputs/conditional-121/native-results.json');
class Reporter{onTestEnd(test,result){let rows=fs.existsSync(file)?JSON.parse(fs.readFileSync(file,'utf8')):[];const title=test.title;rows=rows.filter(r=>r.title!==title);rows.push({title,status:result.status,expected:test.expectedStatus,duration:result.duration,verifiedAt:new Date().toISOString(),file:test.location.file,error:result.error?.message?.replace(/\x1b\[[0-9;]*m/g,'').slice(0,1500)});fs.writeFileSync(file,JSON.stringify(rows,null,2));}}
module.exports=Reporter;

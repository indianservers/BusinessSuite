const q=require('./custom_fields_live.cjs');
(async()=>{const a=await q.auth(),b=await q.browserContext(a),p=b.page;try{await q.check(p,'Quote create','quotations','create',async()=>{await p.goto(q.origin+'/crm/quotes');await p.getByRole('button',{name:/Create quote/i}).first().click();});}finally{await b.browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});

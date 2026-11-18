const y=[{key:"email",label:"Email",description:"Welcome messages, follow-ups, reminders, invitations and updates."},{key:"inventory",label:"Business documents",description:"Invoices, quotations, sales orders and purchase orders."},{key:"mail_merge",label:"Mail merge",description:"Letters, agreements, forms, address labels and envelopes."}],c={email:[{key:"email",label:"Email"}],inventory:[{key:"invoice",label:"Invoice"},{key:"quotation",label:"Quotation"},{key:"sales_order",label:"Sales order"},{key:"purchase_order",label:"Purchase order"}],mail_merge:[{key:"letter",label:"Letter"},{key:"agreement",label:"Agreement"},{key:"form",label:"Form"},{key:"label",label:"Address label"},{key:"envelope",label:"Envelope"}]},k={brand:"Brand header",heading:"Heading",text:"Text",image:"Logo / image",button:"Button",divider:"Divider",spacer:"Spacing",items:"Line items",totals:"Totals",signature:"Signature",columns:"Columns"};function o(e,n){const t={brand:"{{organization.name}}",heading:"A heading that makes an impression",text:`Hello {{name}},
Add your message here. Use placeholders to personalize each copy.`,image:"Company logo",button:"Explore more",divider:"",spacer:"",items:"",totals:"",signature:`{{sender}}
{{sender_title}}`,columns:`Your first highlight
A useful benefit or next step.
---
Your second highlight
Supporting details for your customer.`};return{id:crypto.randomUUID(),type:e,text:n??t[e],url:e==="button"?"https://example.com":"",align:"left",size:e==="heading"?32:e==="brand"?18:14,color:"#243047",bold:!1,padding:12}}function r(e,n,t,s){var u;const a=n||c[e][0].key,l=((u=c[e].find(h=>h.key===a))==null?void 0:u.label)||"Email";let i;return e==="email"?i=[o("brand","YOUR COMPANY"),o("divider"),o("heading",t||"Welcome aboard, {{name}}"),o("text",s||`Hi {{name}},

Thank you for choosing us. We look forward to helping {{company}} achieve its goals.

Reply to this email whenever you need a hand.`),o("button","Get started"),o("text",`Warm regards,
Your customer success team`)]:e==="inventory"?i=[o("brand"),o("text",`{{organization.address}}
{{organization.email}} · {{organization.phone}}
Tax / GST: {{organization.tax_id}}`),o("divider"),o("heading",l.toUpperCase()),o("text",`Reference: {{document.number}}
Issued: {{document.date}}
Due / valid until: {{document.due_date}}`),o("text",(a==="purchase_order"?"SUPPLIER":"BILL TO")+`
{{name}}
{{company}}
{{address}}`),o("items"),o("totals"),o("text","{{document.terms}}"),o("signature")]:a==="label"||a==="envelope"?i=[o("text",`FROM
{{organization.name}}
{{organization.address}}`),o("spacer"),o("heading","{{name}}"),o("text",`{{company}}
{{address}}`)]:i=[o("brand"),o("text",`{{organization.address}}
{{organization.email}}`),o("divider"),o("heading",a==="agreement"?"Service agreement":a==="form"?"Customer information form":"A letter to {{name}}"),o("text",`Date: {{document.date}}
To: {{name}}
{{company}}
{{address}}`),o("text",a==="agreement"?`This agreement is between {{organization.name}} and {{company}}, effective {{contract.start_date}} through {{contract.end_date}}.

Scope of services: {{product}}

Add the agreed responsibilities, commercial terms and termination provisions here.`:a==="form"?`Full name: {{name}}
Email address: {{email}}
Phone number: {{phone}}
Company: {{company}}

Additional information: ______________________

Consent / signature: ______________________`:`Dear {{name}},

Thank you for your continued partnership with {{organization.name}}. We are pleased to share this personalized update with you.

Add the details of your letter here.`),o("signature")],{name:t||(e==="email"?"Welcome email":`${l} · Modern`),category:e,document_type:a,module:"contact",subject:e==="email"?"Welcome, {{name}} — let’s get started":"",folder:"General",status:"draft",version:1,design:{accent:"#6554c0",background:"#ffffff",font:"Arial",blocks:i}}}function v(e){return e!=="email"?c[e].map(n=>r(e,n.key)):[r("email"),r("email","email","Sales follow-up",`Hi {{name}},

It was lovely speaking with you about the needs of {{company}}. Would you have time this week to discuss the next steps?

Looking forward to hearing from you.`),r("email","email","Payment reminder",`Hi {{name}},

A friendly reminder that your payment is due soon. Please contact our accounts team if you need a copy of your invoice.

Thank you for your business.`),r("email","email","Meeting invitation",`Hi {{name}},

We would love to meet with the team at {{company}}. Please reply with a suitable time and we will send you an invitation.`),r("email","email","Thank you",`Hi {{name}},

Thank you for trusting us. We appreciate your partnership and look forward to working together again.`),r("email","email","Product announcement",`Hello {{name}},

We have something new to share with {{company}}. Discover our latest product improvements and tell us what you think.`)]}function b(e){return{name:e.name,category:e.category,document_type:e.document_type,module:e.module,subject:e.subject,folder:e.folder,status:e.status,version:e.version,design:e.design}}const m=[["lead","Notification","Your enquiry, acknowledged","Thanks for reaching out, {{name}}",`Hi {{name}},

Thank you for telling us what you are looking for. Your enquiry is with our team, and we will confirm the right next step after reviewing your requirements.

If there is a deadline or an urgent question, reply here so we can take it into account.`,"Share your requirements","minimal"],["lead","Invitation","See it working for your team","Your personalized product demo",`Hi {{name}},

Let’s explore how {{product}} could support the way {{company}} works. We suggest a short demonstration focused on your current process, challenges and questions.

Proposed time: {{meeting.date}} at {{meeting.time}}. Please confirm or suggest a more convenient time.`,"Confirm my demo","spotlight"],["lead","Follow-up","After the first demonstration","What stood out in your demo?",`Hi {{name}},

Thank you for exploring {{product}} with us. Which part looked most useful for your team, and what would you like to test more closely?

We can arrange a focused follow-up around your real workflow rather than repeat the full demonstration.`,"Discuss the next step","editorial"],["lead","Product Promotion","A useful introduction","Meet {{product}}",`Hello {{name}},

{{product}} brings your team’s work and customer context into one place. Start with the workflow that matters most, then expand when you are ready.

We would be happy to show how this could fit {{company}} and explain the options before you decide.`,"Explore the product","digest"],["lead","Follow-up","A gentle final check-in","Should we keep this conversation open?",`Hi {{name}},

We have not heard back, so we will pause our follow-ups for now. If your priorities change, reply to this message and we can pick up where we left off.

Thank you for considering us.`,"Keep the conversation open","minimal"],["lead","Invitation","An invitation to learn together","Join our practical webinar",`Hello {{name}},

You are invited to a practical session about improving the way teams manage their customer work. We will share examples, answer questions and leave time for discussion.

When: {{meeting.date}} · {{meeting.time}}. Please review the details before registering.`,"View the session","spotlight"],["lead","Celebration","A fresh start for your business","Wishing {{company}} a successful new year",`Hello {{name}},

Wishing you and everyone at {{company}} a happy new year. May it bring clear priorities, rewarding partnerships and time for the work you enjoy.

If a new goal would benefit from our support, we would love to hear about it.`,"Share your next goal","spotlight"],["lead","Basic","A simple personal introduction","An introduction from {{sender}}",`Hello {{name}},

I’m {{sender}}, {{sender_title}}. I would like to understand what your team is working towards and whether our experience would be useful.

Would you prefer a short call or a conversation by email?`,"Reply to {{sender}}","formal"],["contact","Celebration","A birthday note, just for you","Happy birthday, {{name}}",`Hi {{name}},

Wishing you a wonderful birthday and a year filled with good health, rewarding work and moments worth celebrating.

Warm wishes from all of us at {{organization.name}}.`,"Send a hello","spotlight"],["contact","Celebration","Thank you for being part of our year","Warm festive wishes from our team",`Dear {{name}},

Wishing you and your loved ones a peaceful festive season. Thank you for the conversations, trust and collaboration we have shared this year.

We look forward to another year of doing meaningful work together.`,"Stay in touch","editorial"],["contact","Notification","Your onboarding starts here","Welcome to your next chapter, {{name}}",`Hi {{name}},

Welcome to {{organization.name}}. We are pleased to be working with you.

Your first steps are to confirm your main point of contact, tell us your immediate priorities and choose a kickoff time. We will guide you through the rest.`,"Begin onboarding","digest"],["contact","Follow-up","How are things going?","A quick check on your experience",`Hi {{name}},

How is your experience with {{product}} so far? We would like to know what is working well and what still feels difficult.

A short reply is enough. Your feedback will help us focus our next conversation.`,"Share your feedback","minimal"],["contact","Invitation","A conversation with your customer team","Let’s review your goals",`Hi {{name}},

Let’s take a little time to review your progress, current questions and priorities for the next quarter. We will agree a short action plan together.

Suggested time: {{meeting.date}} at {{meeting.time}}.`,"Plan our review","formal"],["contact","Product Promotion","What’s new, and why it matters","A useful update to {{product}}",`Hello {{name}},

We have improvements to share that may help your team work more smoothly. Explore what has changed, decide what is relevant and ask us about anything you would like to try.

Your current setup stays as agreed unless you choose a change.`,"See what’s new","digest"],["contact","Follow-up","A referral, only if it feels right","Know a team we could help?",`Hi {{name}},

If working with us has been useful, you may know another team facing similar challenges. We would appreciate an introduction if you feel comfortable making one.

There is no obligation, and we will treat every introduction with care.`,"Make an introduction","editorial"],["contact","Notification","We’ve noted your preference","Your communication preference is updated",`Hello {{name}},

We have recorded your request about optional communications. If you asked to unsubscribe, you will no longer receive the updates covered by that preference.

Messages needed to provide an active service may still apply. Contact us if you would like to clarify your choices.`,"Contact our team","minimal"],["account","Invitation","Your quarterly business review","Let’s plan the next quarter for {{company}}",`Hello {{name}},

We propose a review of our work with {{company}}: outcomes so far, open risks and the priorities ahead. Please bring the colleagues who can help shape the next steps.

Suggested meeting: {{meeting.date}} · {{meeting.time}}.`,"Arrange the review","formal"],["account","Follow-up","Renewal without last-minute surprises","Planning your next term together",`Hello {{name}},

As we look towards the next term, let’s confirm what {{company}} will need, who should be involved and when a decision is expected.

We will review scope and commercial terms with you before anything is renewed.`,"Discuss renewal options","editorial"],["account","Notification","Introducing your account partner","Your point of contact at {{organization.name}}",`Hello {{name}},

I’m {{sender}}, and I will coordinate our relationship with {{company}}. You can reach me at {{sender_email}} for questions, planning or help finding the right specialist.

I look forward to learning about your team’s priorities.`,"Meet your account team","minimal"],["account","Product Promotion","An option worth exploring","Could {{product}} help your next priority?",`Hello {{name}},

Based on our conversations, {{product}} may be useful for the next stage of work at {{company}}. We would like to explore the fit with you before recommending any change.

Let’s review the expected outcome, effort and costs together.`,"Explore the fit","digest"],["account","Celebration","Celebrating our partnership","Thank you, {{company}}",`Hello {{name}},

We value the trust your team has placed in us. Thank you for the candid feedback, collaboration and commitment that make this partnership work.

Here’s to the next milestone together.`,"Share your next milestone","spotlight"],["account","Notification","A service update for your team","An important update for {{company}}",`Hello {{name}},

We have a service update to discuss with your team. We will explain the change, who it affects, the expected timing and any action needed before it takes effect.

Please reply with the colleagues who should receive the detailed notice.`,"Request the details","formal"],["deal","Notification","A new opportunity, a clear plan","Next steps for {{deal.name}}",`Hello {{name}},

We have opened our discussion around {{deal.name}}. To make it useful, let’s confirm the desired outcome, the stakeholders involved and how your team will evaluate the options.

We will agree the next action together.`,"Confirm our next step","formal"],["deal","Follow-up","A proposal review that answers questions","Let’s review {{deal.name}} together",`Hi {{name}},

Does the proposal give {{company}} the information needed to decide? We can walk through scope, assumptions, timeline and pricing with the right stakeholders.

Tell us what still needs clarification and we will focus there.`,"Schedule a proposal review","editorial"],["deal","Notification","From a successful decision to delivery","Thank you for choosing our team",`Hi {{name}},

Thank you for choosing us for {{deal.name}}. We are ready to turn the agreed plan into a smooth start.

We will confirm the delivery contact, kickoff agenda, responsibilities and milestones with you.`,"Plan the kickoff","spotlight"],["deal","Notification","A respectful close to the conversation","Thank you for considering us",`Hi {{name}},

Thank you for the time your team spent evaluating our proposal. We understand you have chosen a different direction and respect that decision.

If you are comfortable sharing feedback, it would help us improve. We would welcome a future conversation if circumstances change.`,"Share your feedback","minimal"],["deal","Follow-up","Resolve the last open questions","What remains before your decision?",`Hi {{name}},

Before your team makes a decision on {{deal.name}}, let’s check whether any scope, security, legal or commercial questions remain open.

We can bring the relevant colleagues together and agree how to resolve them.`,"Review open questions","digest"],["deal","Follow-up","Pick up when the timing is right","Revisiting {{deal.name}}",`Hello {{name}},

When we last spoke, the timing was not right for {{deal.name}}. Has anything changed in the priorities or constraints at {{company}}?

If a fresh conversation would be useful, we can start with what is different now.`,"Revisit the opportunity","editorial"],["quotation","Notification","Your quotation, explained","Quotation {{document.number}} is ready",`Hi {{name}},

Your quotation for {{product}} is ready. Please review the scope, quantities, currency, tax and payment terms before accepting.

Reference: {{document.number}}
Total: {{document.currency}} {{document.total}}
Valid until: {{document.due_date}}`,"Review your quotation","formal"],["quotation","Follow-up","Before your quotation expires","A check-in on quotation {{document.number}}",`Hi {{name}},

Your quotation is valid until {{document.due_date}}. Is your team ready to review it, or would more time or clarification help?

We will confirm any extension or revised terms with you in writing.`,"Discuss the quotation","minimal"],["quotation","Notification","A revised scope, clearly explained","Updated quotation {{document.number}}",`Hi {{name}},

We have revised the quotation following our discussion. Please compare the updated scope and commercial terms with your requirements.

Reference: {{document.number}} · Total: {{document.currency}} {{document.total}}. Ask us to explain any change before you decide.`,"Review the changes","editorial"],["quotation","Notification","Acceptance received, next steps ahead","Next steps after quotation approval",`Hi {{name}},

Thank you for confirming quotation {{document.number}}. We will check the agreed terms and coordinate the next steps with your team.

Please tell us who should receive delivery, billing and scheduling updates.`,"Confirm your contacts","digest"],["task","Notification","An action with an owner","Action needed: {{task.title}}",`Hi {{name}},

Please review the action below and confirm that the expected result and timing are clear.

Action: {{task.title}}
Due: {{task.due_date}}

If a dependency is blocking progress, let us know early.`,"Review the action","formal"],["task","Follow-up","A helpful overdue reminder","Checking in on {{task.title}}",`Hi {{name}},

We are checking on the action due on {{task.due_date}}. Is it complete, or should we agree a revised plan?

Please share any blocker so we can help move things forward.`,"Update the action","minimal"],["meeting","Invitation","A clear meeting confirmation","Confirmed: {{meeting.date}} at {{meeting.time}}",`Hi {{name}},

Our meeting is planned for {{meeting.date}} at {{meeting.time}}. We will focus on your priorities, the decisions needed and an agreed next step.

Please check the invitation for the joining details and tell us if anything needs to change.`,"Review the invitation","spotlight"],["meeting","Follow-up","The decisions, captured","Thank you for our conversation",`Hi {{name}},

Thank you for meeting with us on {{meeting.date}}. We will confirm the decisions, owners and target dates in this thread.

Please reply with any correction before the team acts on the recap.`,"Confirm the recap","formal"],["call","Notification","We tried to reach you","A convenient time for a callback",`Hi {{name}},

We tried to reach you and would like to arrange a convenient callback. Please reply with your preferred time and timezone.

If email is easier, we can continue the conversation here.`,"Choose a callback time","minimal"],["call","Follow-up","After our conversation","The next step we discussed",`Hi {{name}},

Thank you for the call. Let’s confirm the outcome and next action in writing so everyone has the same understanding.

Reply with any correction, and we will update the plan before moving forward.`,"Confirm the next action","formal"],["campaign","Invitation","An invitation for your whole team","Join us for a practical conversation",`Hello {{name}},

We are hosting a focused session for teams exploring better ways to work with customers. Expect practical examples and time for questions.

When: {{meeting.date}} at {{meeting.time}}. Share the invitation with colleagues who would find it useful.`,"Explore the event","spotlight"],["campaign","Product Promotion","A product update worth your time","Explore the latest in {{product}}",`Hello {{name}},

Take a look at the latest improvements to {{product}}. We have grouped the updates around common team challenges so you can find what matters to {{company}}.

Ask us for a walkthrough if you want to explore any change in context.`,"Explore the improvements","digest"],["ticket","Notification","Your request is with our team","We’re reviewing {{ticket.subject}}",`Hi {{name}},

Thank you for raising your request. Our team is reviewing the details and will confirm the next step.

If you can add a reproducible example or explain the impact, reply here. Please avoid sending passwords or other sensitive credentials.`,"Add useful context","minimal"],["ticket","Follow-up","Let’s check the resolution together","Does the proposed resolution work?",`Hi {{name}},

We have a proposed resolution for {{ticket.subject}}. Please try the agreed steps and let us know whether the result meets your needs.

If the issue continues, reply with what you observed so we can keep working on it.`,"Review the resolution","formal"]],d=[["lead","Leads"],["contact","Contacts"],["account","Accounts"],["deal","Deals"],["quotation","Quotations"],["task","Tasks"],["meeting","Meetings"],["call","Calls"],["campaign","Campaigns"],["ticket","Support tickets"]],p={lead:[["Connect","A useful first conversation","A quick question for {{company}}",`Hi {{name}},

What is the one business challenge your team most wants to solve this quarter? Share a little context and we will suggest a practical starting point.

A short reply is all we need.`,"Reply with your priority"],["Qualify","Discovery without the homework","Let’s focus on what matters",`Hi {{name}},

Before we talk, it would help to understand your desired outcome, current approach and target timeline.

We can work through these together—there is no need to prepare a presentation.`,"Choose a discovery time"],["Reconnect","Permission to reconnect","Is this still a priority?",`Hi {{name}},

We previously discussed a possible next step for {{company}}. Has the priority or timing changed?

If now is not a good time, just let us know and we will pause our follow-up.`,"Share an update"]],contact:[["Onboard","Your first week, made clear","Welcome—here is your next step",`Hi {{name}},

Welcome aboard. Let’s keep your first week simple: confirm your main point of contact, agree on the first milestone and tell us what a successful start looks like.

Your team can reply here whenever you need help.`,"Plan your kickoff"],["Review","A conversation about progress","How is everything working for you?",`Hi {{name}},

We would like to check what is working well and what could be easier for your team at {{company}}.

Share one success and one obstacle. We will use your feedback to make our next conversation useful.`,"Share your feedback"],["Appreciate","A thoughtful thank-you","Thank you for the partnership",`Hi {{name}},

Thank you for the time and trust you have invested in working with us. Your feedback helps us improve.

If there is a colleague we should recognize for making this work possible, we would love to hear about them.`,"Recognize your team"]],account:[["Review","A focused account review","A progress review for {{company}}",`Hello {{name}},

Let’s review the outcomes we agreed on, the progress your team has seen and the areas that need attention.

Please bring any changes in priorities so we can align the next phase with your plans.`,"Schedule the review"],["Renew","Plan the next chapter","Planning ahead with {{company}}",`Hello {{name}},

As we plan the next phase of our partnership, we would like to understand your expected usage, team changes and priorities.

Let’s review the options together before you make a decision.`,"Discuss your options"],["Coordinate","Keep the right people aligned","Who should join our next update?",`Hello {{name}},

We want updates for {{company}} to reach the people who need them. Please confirm the contacts for operational questions, billing and decisions.

A reply with any changes will help us keep things running smoothly.`,"Confirm your contacts"]],deal:[["Progress","A shared plan to move forward","Our next steps together",`Hi {{name}},

Following our discussion, let’s confirm the outcome, the next action and who owns it on each side.

Please reply with any remaining questions or dependencies so we can agree on a realistic plan.`,"Confirm the next step"],["Decide","Make the decision easier","What would help your decision?",`Hi {{name}},

Is there any information your team at {{company}} still needs to evaluate the proposal?

We can walk through the scope, implementation approach or commercial assumptions with the right stakeholders.`,"Discuss open questions"],["Handoff","From agreement to delivery","Let’s introduce your delivery team",`Hi {{name}},

We are ready to connect your stakeholders with the team who will coordinate delivery.

At kickoff, we will confirm scope, responsibilities, milestones and the best way to raise questions.`,"Plan the handoff"]],quotation:[["Propose","A proposal with a clear next step","Your proposal is ready to review",`Hi {{name}},

Your proposal is ready for review. Please check the scope, quantities, assumptions and commercial terms against your requirements.

We can review it together and clarify any changes before you decide.`,"Review the proposal"],["Clarify","Resolve proposal questions","Any questions about your quotation?",`Hi {{name}},

We are checking whether the quotation gives your team at {{company}} everything needed to evaluate the offer.

Let us know what needs clarification or revision.`,"Request clarification"],["Revise","Explain what changed","Your revised proposal",`Hi {{name}},

We have prepared a revised proposal following your feedback. Please review the updated scope and terms alongside the previous version.

We will be happy to explain each change before the next step.`,"Review the revision"]],task:[["Coordinate","A clear action request","Can we confirm the next action?",`Hi {{name}},

To keep work moving, please confirm the owner, expected result and target date for our next action.

If a dependency is blocking progress, tell us what support is needed.`,"Confirm the action"],["Unblock","Ask for help early","A quick check on the outstanding action",`Hi {{name}},

We are following up on an outstanding action. Has anything changed in the timing or requirements?

Please share any blocker so we can adjust the plan together.`,"Share a blocker"],["Complete","Close the loop","The action is ready for your review",`Hi {{name}},

The agreed action is ready for review. Please check the result against your expectations and tell us if anything needs attention.

We will confirm closure after your feedback.`,"Review the result"]],meeting:[["Prepare","A meeting with a purpose","Let’s make our meeting useful",`Hi {{name}},

For our upcoming meeting, we suggest focusing on your current priorities, the decisions needed and the next steps.

Please reply with any topic you want to add, or anyone else who should attend.`,"Confirm the agenda"],["Recap","Decisions into action","Our meeting recap and next steps",`Hi {{name}},

Thank you for meeting with us. We will use this thread to confirm the decisions made, action owners and agreed dates.

Please flag anything we should correct before we proceed.`,"Confirm the recap"],["Reschedule","Make a new time easy","Shall we find another time?",`Hi {{name}},

It looks like we need a different time to connect. Please share a couple of convenient options and your timezone.

We will confirm the new invitation once we have agreed a time.`,"Suggest a time"]],call:[["Connect","A respectful callback","When would a short call work?",`Hi {{name}},

We tried to reach you about the next step for {{company}}. When would a brief call be convenient?

If email works better, we are happy to continue here.`,"Choose how to connect"],["Recap","Capture the conversation","Following up on our call",`Hi {{name}},

Thank you for speaking with us. Let’s confirm the outcome of our conversation and the next action before we move forward.

Please reply with any correction or question.`,"Confirm the next action"],["Prepare","A useful call agenda","Before we speak",`Hi {{name}},

On our call, we would like to understand your immediate priorities and answer your most important questions.

What would make the conversation worthwhile for you?`,"Share your questions"]],campaign:[["Invite","An invitation with context","An invitation for your team",`Hello {{name}},

We are bringing together teams to discuss practical approaches to a shared business challenge.

If this is relevant to {{company}}, explore the details and decide whether you would like to join us.`,"Explore the event"],["Educate","Something useful to share","A resource for your next step",`Hello {{name}},

We have put together a practical resource to help teams evaluate their next steps.

Take a look when convenient, and tell us which topic would be most helpful to explore next.`,"Explore the resource"],["Follow up","Continue the conversation","What would you like to explore next?",`Hello {{name}},

Thank you for your interest in our recent update. Which part is most relevant to your team at {{company}}?

We can share more detail or connect you with someone who can answer your questions.`,"Tell us your interest"]],ticket:[["Acknowledge","Set a helpful expectation","We have received your request",`Hi {{name}},

Thank you for contacting us. We are reviewing your request and will confirm the next step.

If the impact changes or you have more context, please reply here so the team has the latest information.`,"Add more context"],["Update","A clear progress update","An update on your request",`Hi {{name}},

We are continuing to work on your request. We will explain the current finding, the next action and when you can expect another update.

Please let us know if your circumstances have changed.`,"Continue the conversation"],["Resolve","Confirm the fix worked","Does this resolve your request?",`Hi {{name}},

We have a proposed resolution ready for your review. Please try the recommended steps and let us know whether the issue is resolved.

If you still need help, reply here and we will continue investigating.`,"Confirm the outcome"]]},f=["#6554c0","#147d73","#aa602c"],g=["minimal","editorial","formal"],w=d.flatMap(([e])=>p[e].map(([n,t,s,a,l],i)=>({id:`${e}-${i}`,module:e,goal:n,title:t,subject:s,message:a,action:l,color:f[i],collection:n==="Invite"?"Invitation":n==="Educate"?"Product Promotion":["Reconnect","Renew","Unblock","Follow up"].includes(n)?"Follow-up":"Notification",layout:g[i]}))),x=[...w,...m.map(([e,n,t,s,a,l,i],u)=>({id:`collection-${e}-${u}`,module:e,goal:n,collection:n,layout:i,title:t,subject:s,message:a,action:l,color:["#6554c0","#147d73","#a45d2c","#244e7b","#9b4272"][u%5]}))],W=["Basic","Celebration","Invitation","Follow-up","Product Promotion","Notification"],H=[{key:"minimal",label:"Minimal"},{key:"spotlight",label:"Spotlight"},{key:"editorial",label:"Editorial"},{key:"digest",label:"Two-column digest"},{key:"formal",label:"Formal letter"}];function A(e){const n=r("email","email",e.title,e.message);if(n.module=e.module,n.subject=e.subject,n.folder=d.find(([t])=>t===e.module)[1],n.design.accent=e.color,n.design.blocks=n.design.blocks.map(t=>t.type==="heading"?{...t,text:e.title}:t.type==="button"?{...t,text:e.action,url:""}:t),e.layout==="spotlight")n.design.blocks=n.design.blocks.map(t=>({...t,align:"center",padding:t.type==="heading"?26:16})),n.design.background="#faf8ff";else if(e.layout==="editorial")n.design.font="Georgia",n.design.blocks=n.design.blocks.map(t=>t.type==="heading"?{...t,size:40,color:e.color}:{...t,padding:16});else if(e.layout==="digest"){const t={...o("columns",`A clear next step
Review the details with your team.
---
Support when you need it
Reply with your questions.`),columns:2};n.design.blocks.splice(n.design.blocks.findIndex(s=>s.type==="button"),0,t)}else e.layout==="formal"&&(n.design.font="Georgia",n.design.blocks=n.design.blocks.filter(t=>t.type!=="button"),n.design.blocks.push(o("signature",`{{sender}}
{{sender_title}}
{{organization.name}}`)));return n}export{A as a,W as b,H as c,y as d,v as e,c as f,x as g,k as h,o as i,b as p,r as s,d as t};

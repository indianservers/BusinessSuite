import { block, starter, type Template } from './template-presets';
import {scenarios, type Collection, type Layout} from './crm-scenarios';

export const templateModules = [
  ['lead', 'Leads'], ['contact', 'Contacts'], ['account', 'Accounts'], ['deal', 'Deals'],
  ['quotation', 'Quotations'], ['task', 'Tasks'], ['meeting', 'Meetings'], ['call', 'Calls'],
  ['campaign', 'Campaigns'], ['ticket', 'Support tickets'],
] as const;
export type GalleryModule = typeof templateModules[number][0];
export type GalleryEntry = { id: string; module: GalleryModule; goal: string; title: string; subject: string; message: string; action: string; color: string; collection: Collection; layout: Layout };
type Brief = [string, string, string, string, string];
const briefs: Record<GalleryModule, Brief[]> = {
  lead: [
    ['Connect', 'A useful first conversation', 'A quick question for {{company}}', 'Hi {{name}},\n\nWhat is the one business challenge your team most wants to solve this quarter? Share a little context and we will suggest a practical starting point.\n\nA short reply is all we need.', 'Reply with your priority'],
    ['Qualify', 'Discovery without the homework', 'Let’s focus on what matters', 'Hi {{name}},\n\nBefore we talk, it would help to understand your desired outcome, current approach and target timeline.\n\nWe can work through these together—there is no need to prepare a presentation.', 'Choose a discovery time'],
    ['Reconnect', 'Permission to reconnect', 'Is this still a priority?', 'Hi {{name}},\n\nWe previously discussed a possible next step for {{company}}. Has the priority or timing changed?\n\nIf now is not a good time, just let us know and we will pause our follow-up.', 'Share an update'],
  ],
  contact: [
    ['Onboard', 'Your first week, made clear', 'Welcome—here is your next step', 'Hi {{name}},\n\nWelcome aboard. Let’s keep your first week simple: confirm your main point of contact, agree on the first milestone and tell us what a successful start looks like.\n\nYour team can reply here whenever you need help.', 'Plan your kickoff'],
    ['Review', 'A conversation about progress', 'How is everything working for you?', 'Hi {{name}},\n\nWe would like to check what is working well and what could be easier for your team at {{company}}.\n\nShare one success and one obstacle. We will use your feedback to make our next conversation useful.', 'Share your feedback'],
    ['Appreciate', 'A thoughtful thank-you', 'Thank you for the partnership', 'Hi {{name}},\n\nThank you for the time and trust you have invested in working with us. Your feedback helps us improve.\n\nIf there is a colleague we should recognize for making this work possible, we would love to hear about them.', 'Recognize your team'],
  ],
  account: [
    ['Review', 'A focused account review', 'A progress review for {{company}}', 'Hello {{name}},\n\nLet’s review the outcomes we agreed on, the progress your team has seen and the areas that need attention.\n\nPlease bring any changes in priorities so we can align the next phase with your plans.', 'Schedule the review'],
    ['Renew', 'Plan the next chapter', 'Planning ahead with {{company}}', 'Hello {{name}},\n\nAs we plan the next phase of our partnership, we would like to understand your expected usage, team changes and priorities.\n\nLet’s review the options together before you make a decision.', 'Discuss your options'],
    ['Coordinate', 'Keep the right people aligned', 'Who should join our next update?', 'Hello {{name}},\n\nWe want updates for {{company}} to reach the people who need them. Please confirm the contacts for operational questions, billing and decisions.\n\nA reply with any changes will help us keep things running smoothly.', 'Confirm your contacts'],
  ],
  deal: [
    ['Progress', 'A shared plan to move forward', 'Our next steps together', 'Hi {{name}},\n\nFollowing our discussion, let’s confirm the outcome, the next action and who owns it on each side.\n\nPlease reply with any remaining questions or dependencies so we can agree on a realistic plan.', 'Confirm the next step'],
    ['Decide', 'Make the decision easier', 'What would help your decision?', 'Hi {{name}},\n\nIs there any information your team at {{company}} still needs to evaluate the proposal?\n\nWe can walk through the scope, implementation approach or commercial assumptions with the right stakeholders.', 'Discuss open questions'],
    ['Handoff', 'From agreement to delivery', 'Let’s introduce your delivery team', 'Hi {{name}},\n\nWe are ready to connect your stakeholders with the team who will coordinate delivery.\n\nAt kickoff, we will confirm scope, responsibilities, milestones and the best way to raise questions.', 'Plan the handoff'],
  ],
  quotation: [
    ['Propose', 'A proposal with a clear next step', 'Your proposal is ready to review', 'Hi {{name}},\n\nYour proposal is ready for review. Please check the scope, quantities, assumptions and commercial terms against your requirements.\n\nWe can review it together and clarify any changes before you decide.', 'Review the proposal'],
    ['Clarify', 'Resolve proposal questions', 'Any questions about your quotation?', 'Hi {{name}},\n\nWe are checking whether the quotation gives your team at {{company}} everything needed to evaluate the offer.\n\nLet us know what needs clarification or revision.', 'Request clarification'],
    ['Revise', 'Explain what changed', 'Your revised proposal', 'Hi {{name}},\n\nWe have prepared a revised proposal following your feedback. Please review the updated scope and terms alongside the previous version.\n\nWe will be happy to explain each change before the next step.', 'Review the revision'],
  ],
  task: [
    ['Coordinate', 'A clear action request', 'Can we confirm the next action?', 'Hi {{name}},\n\nTo keep work moving, please confirm the owner, expected result and target date for our next action.\n\nIf a dependency is blocking progress, tell us what support is needed.', 'Confirm the action'],
    ['Unblock', 'Ask for help early', 'A quick check on the outstanding action', 'Hi {{name}},\n\nWe are following up on an outstanding action. Has anything changed in the timing or requirements?\n\nPlease share any blocker so we can adjust the plan together.', 'Share a blocker'],
    ['Complete', 'Close the loop', 'The action is ready for your review', 'Hi {{name}},\n\nThe agreed action is ready for review. Please check the result against your expectations and tell us if anything needs attention.\n\nWe will confirm closure after your feedback.', 'Review the result'],
  ],
  meeting: [
    ['Prepare', 'A meeting with a purpose', 'Let’s make our meeting useful', 'Hi {{name}},\n\nFor our upcoming meeting, we suggest focusing on your current priorities, the decisions needed and the next steps.\n\nPlease reply with any topic you want to add, or anyone else who should attend.', 'Confirm the agenda'],
    ['Recap', 'Decisions into action', 'Our meeting recap and next steps', 'Hi {{name}},\n\nThank you for meeting with us. We will use this thread to confirm the decisions made, action owners and agreed dates.\n\nPlease flag anything we should correct before we proceed.', 'Confirm the recap'],
    ['Reschedule', 'Make a new time easy', 'Shall we find another time?', 'Hi {{name}},\n\nIt looks like we need a different time to connect. Please share a couple of convenient options and your timezone.\n\nWe will confirm the new invitation once we have agreed a time.', 'Suggest a time'],
  ],
  call: [
    ['Connect', 'A respectful callback', 'When would a short call work?', 'Hi {{name}},\n\nWe tried to reach you about the next step for {{company}}. When would a brief call be convenient?\n\nIf email works better, we are happy to continue here.', 'Choose how to connect'],
    ['Recap', 'Capture the conversation', 'Following up on our call', 'Hi {{name}},\n\nThank you for speaking with us. Let’s confirm the outcome of our conversation and the next action before we move forward.\n\nPlease reply with any correction or question.', 'Confirm the next action'],
    ['Prepare', 'A useful call agenda', 'Before we speak', 'Hi {{name}},\n\nOn our call, we would like to understand your immediate priorities and answer your most important questions.\n\nWhat would make the conversation worthwhile for you?', 'Share your questions'],
  ],
  campaign: [
    ['Invite', 'An invitation with context', 'An invitation for your team', 'Hello {{name}},\n\nWe are bringing together teams to discuss practical approaches to a shared business challenge.\n\nIf this is relevant to {{company}}, explore the details and decide whether you would like to join us.', 'Explore the event'],
    ['Educate', 'Something useful to share', 'A resource for your next step', 'Hello {{name}},\n\nWe have put together a practical resource to help teams evaluate their next steps.\n\nTake a look when convenient, and tell us which topic would be most helpful to explore next.', 'Explore the resource'],
    ['Follow up', 'Continue the conversation', 'What would you like to explore next?', 'Hello {{name}},\n\nThank you for your interest in our recent update. Which part is most relevant to your team at {{company}}?\n\nWe can share more detail or connect you with someone who can answer your questions.', 'Tell us your interest'],
  ],
  ticket: [
    ['Acknowledge', 'Set a helpful expectation', 'We have received your request', 'Hi {{name}},\n\nThank you for contacting us. We are reviewing your request and will confirm the next step.\n\nIf the impact changes or you have more context, please reply here so the team has the latest information.', 'Add more context'],
    ['Update', 'A clear progress update', 'An update on your request', 'Hi {{name}},\n\nWe are continuing to work on your request. We will explain the current finding, the next action and when you can expect another update.\n\nPlease let us know if your circumstances have changed.', 'Continue the conversation'],
    ['Resolve', 'Confirm the fix worked', 'Does this resolve your request?', 'Hi {{name}},\n\nWe have a proposed resolution ready for your review. Please try the recommended steps and let us know whether the issue is resolved.\n\nIf you still need help, reply here and we will continue investigating.', 'Confirm the outcome'],
  ],
};
const colors = ['#6554c0', '#147d73', '#aa602c'];
const layouts: Layout[] = ['minimal', 'editorial', 'formal'];
const existingEntries: GalleryEntry[] = templateModules.flatMap(([module]) => briefs[module].map(([goal, title, subject, message, action], index) => ({ id: `${module}-${index}`, module, goal, title, subject, message, action, color: colors[index], collection: goal === 'Invite' ? 'Invitation' : goal === 'Educate' ? 'Product Promotion' : ['Reconnect', 'Renew', 'Unblock', 'Follow up'].includes(goal) ? 'Follow-up' : 'Notification', layout: layouts[index] })));
export const galleryCatalog: GalleryEntry[] = [...existingEntries, ...scenarios.map(([module, collection, title, subject, message, action, layout], index) => ({id: `collection-${module}-${index}`, module: module as GalleryModule, goal: collection, collection, layout, title, subject, message, action, color: ['#6554c0','#147d73','#a45d2c','#244e7b','#9b4272'][index % 5]}))];
export const galleryCollections: Collection[] = ['Basic', 'Celebration', 'Invitation', 'Follow-up', 'Product Promotion', 'Notification'];
export const galleryLayouts: {key: Layout; label: string}[] = [{key:'minimal',label:'Minimal'},{key:'spotlight',label:'Spotlight'},{key:'editorial',label:'Editorial'},{key:'digest',label:'Two-column digest'},{key:'formal',label:'Formal letter'}];
export function galleryTemplate(entry: GalleryEntry): Template {
  const t = starter('email', 'email', entry.title, entry.message);
  t.module = entry.module; t.subject = entry.subject; t.folder = templateModules.find(([key]) => key === entry.module)![1];
  t.design.accent = entry.color;
  t.design.blocks = t.design.blocks.map(b => b.type === 'heading' ? {...b, text: entry.title} : b.type === 'button' ? {...b, text: entry.action, url: ''} : b);
  if (entry.layout === 'spotlight') {
    t.design.blocks = t.design.blocks.map(b => ({...b, align: 'center', padding: b.type === 'heading' ? 26 : 16}));
    t.design.background = '#faf8ff';
  } else if (entry.layout === 'editorial') {
    t.design.font = 'Georgia';
    t.design.blocks = t.design.blocks.map(b => b.type === 'heading' ? {...b, size:40, color:entry.color} : {...b, padding:16});
  } else if (entry.layout === 'digest') {
    const highlights = {...block('columns', 'A clear next step\nReview the details with your team.\n---\nSupport when you need it\nReply with your questions.'), columns:2 as const};
    t.design.blocks.splice(t.design.blocks.findIndex(b => b.type === 'button'),0,highlights);
  } else if (entry.layout === 'formal') {
    t.design.font = 'Georgia';
    t.design.blocks = t.design.blocks.filter(b => b.type !== 'button');
    t.design.blocks.push(block('signature', '{{sender}}\n{{sender_title}}\n{{organization.name}}'));
  }
  return t;
}

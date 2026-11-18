export type Knowledge = { id: string; title: string; content: string; kind: 'service' | 'price' | 'policy' | 'document' | 'faq'; source_url: string; source_reference: string; interface: 'public' | 'company' | 'both'; language: 'en' | 'te' | 'hi'; approved: boolean; expires_at: string; approved_at?: string | null; approved_by_user_id?: number | null };
export type Question = { key: string; label: string; translations: Partial<Record<'te' | 'hi', string>>; type: 'text' | 'choice' | 'number' | 'date' | 'location' | 'document'; required: boolean; choices: string[]; minimum?: number | null; maximum?: number | null; accepted_mime_types: ('application/pdf' | 'image/jpeg' | 'image/png' | 'text/plain')[] };
export type Workflow = { id: string; name: string; industry: string; interface: 'public' | 'company' | 'both'; enabled: boolean; questions: Question[]; urgency_rules: { field: string; operator: 'equals' | 'contains' | 'less_than' | 'greater_than'; value: string; priority: 'Normal' | 'High' | 'Urgent'; reason: string }[]; required_skills: string[]; result: 'lead_and_task' | 'task' | 'handoff' | 'appointment_request'; approval_user_ids: number[]; stages: { key: string; label: string; requires_approval: boolean; next_stages: string[] }[] };
export type RoutingAgent = { user_id: number; branch_id: number; skills: string[]; languages: ('en' | 'te' | 'hi')[]; available: boolean; capacity: number; timezone: string; weekdays: number[]; opens: string; closes: string };
export type BookingService = { service_id: number; label: string; resource_ids: number[]; duration_minutes: number };
export type Experience = { revision: number; knowledge: Knowledge[]; workflows: Workflow[]; lead_workflow_id: string | null; routing_agents: RoutingAgent[]; booking_services: BookingService[]; handoff_minutes: number; urgent_handoff_minutes: number; escalation_user_ids: number[] };
export type ExperienceOptions = { branch_id: number; owner_user_id: number; employees: { id: number; user_id: number; name: string; employee_code: string }[]; services: { id: number; name: string }[]; resources: { id: number; name: string; type: string }[]; booking_error?: string | null };

export const emptyExperience: Experience = { revision: 0, knowledge: [], workflows: [], lead_workflow_id: null, routing_agents: [], booking_services: [], handoff_minutes: 15, urgent_handoff_minutes: 5, escalation_user_ids: [] };
export const question = (key: string, label: string, type: Question['type'] = 'text'): Question => ({ key, label, type, translations: {}, required: true, choices: [], accepted_mime_types: [] });
export function leadWorkflow(): Workflow {
  return { id: `flow-${crypto.randomUUID()}`, name: 'Qualified sales enquiry', industry: 'General services', interface: 'public', enabled: true,
    questions: [
      { ...question('full_name', 'What is your name?'), translations: { te: 'మీ పేరు ఏమిటి?', hi: 'आपका नाम क्या है?' } },
      { ...question('service', 'Which service do you need?'), translations: { te: 'మీకు ఏ సేవ కావాలి?', hi: 'आपको कौन सी सेवा चाहिए?' } },
      { ...question('location', 'Share your service location.', 'location'), translations: { te: 'మీ సేవా స్థానాన్ని పంచుకోండి.', hi: 'अपना सेवा स्थान साझा करें।' } },
      { ...question('urgency', 'How urgent is your request?', 'choice'), choices: ['Routine', 'Urgent', 'Emergency'], translations: { te: 'మీ అభ్యర్థన ఎంత అత్యవసరం?', hi: 'आपका अनुरोध कितना ज़रूरी है?' } },
      { ...question('budget', 'What is your estimated budget?', 'number'), minimum: 0, translations: { te: 'మీ అంచనా బడ్జెట్ ఎంత?', hi: 'आपका अनुमानित बजट कितना है?' } },
      { ...question('preferred_contact_time', 'When would you prefer us to contact you?'), translations: { te: 'మిమ్మల్ని ఎప్పుడు సంప్రదించాలి?', hi: 'हम आपसे कब संपर्क करें?' } },
    ], urgency_rules: [{ field: 'urgency', operator: 'equals', value: 'Emergency', priority: 'Urgent', reason: 'The customer reported an emergency.' }], required_skills: [], result: 'lead_and_task', approval_user_ids: [],
    stages: [{ key: 'received', label: 'Received', requires_approval: false, next_stages: ['completed'] }, { key: 'completed', label: 'Completed', requires_approval: false, next_stages: [] }] };
}

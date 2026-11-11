"""Additive local writing skills. Does not invalidate the action intent model."""
VERSION = 'local-writing-v1'
# IDs are also the direct page-button contract. Examples train local retrieval;
# business facts are supplied at inference time, never memorized in the corpus.
SKILLS = {
 'client_email': ('Draft client email', ['write an email to the client', 'compose a customer email', 'draft client email']),
 'reply': ('Draft reply', ['write a reply to this message', 'draft a client response', 'draft reply']),
 'follow_up': ('Draft follow-up', ['write a customer follow up', 'draft follow-up', 'prepare a client followup email']),
 'meeting_invitation': ('Draft meeting invitation', ['write an invitation for the client meeting', 'draft meeting invitation', 'write a meeting invite']),
 'whatsapp': ('Draft WhatsApp message', ['write a whatsapp message', 'draft WhatsApp message', 'compose short customer outreach']),
 'client_summary': ('Summarize client history', ['summarize client history', 'summarise customer interactions', 'prepare a client history summary']),
 'proposal': ('Draft proposal', ['draft proposal', 'write a customer proposal', 'prepare a sales proposal']),
 'talking_points': ('Prepare talking points', ['prepare talking points', 'suggest client meeting questions', 'prepare sales meeting discussion points']),
 'task_description': ('Write task description', ['write task description', 'turn rough notes into a task description', 'write an expanded task brief']),
 'subtasks': ('Suggest subtasks', ['suggest subtasks', 'break this task into smaller steps', 'draft a task checklist']),
 'project_summary': ('Summarize progress', ['summarize project progress', 'summarise project status', 'summarize progress']),
 'status_update': ('Draft client status update', ['draft client status update', 'write a project update for the customer', 'prepare a progress email']),
 'invoice_email': ('Draft invoice email', ['draft invoice email', 'write an invoice covering email', 'prepare invoice message']),
 'payment_reminder': ('Draft payment reminder', ['draft payment reminder', 'write a payment follow up', 'prepare a collection reminder']),
 'overdue_reminder': ('Draft overdue follow-up', ['draft overdue follow-up', 'write an overdue invoice reminder', 'compose late payment followup']),
 'meeting_summary': ('Summarize meeting', ['summarize meeting notes', 'summarise the meeting', 'summarize meeting']),
 'action_items': ('Extract action items', ['extract action items', 'identify decisions and next steps', 'extract meeting actions']),
 'meeting_follow_up': ('Draft meeting follow-up', ['draft meeting follow-up', 'write a post meeting email', 'draft a meeting recap']),
 'ticket_summary': ('Summarize ticket', ['summarize ticket', 'summarise support conversation', 'prepare a helpdesk issue summary']),
 'support_reply': ('Draft support reply', ['draft support reply', 'write a helpdesk response', 'prepare a support ticket answer']),
 'job_description': ('Draft job description', ['draft job description', 'write a job posting', 'prepare a recruitment role description']),
 'interview_questions': ('Suggest interview questions', ['suggest interview questions', 'prepare candidate interview questions', 'write hiring questions']),
 'onboarding': ('Draft onboarding message', ['draft onboarding message', 'write a welcome message for a new employee', 'prepare a new joiner welcome']),
 'announcement': ('Draft announcement', ['draft announcement', 'write a staff announcement', 'prepare an employee communication']),
 'policy_explanation': ('Explain policy', ['explain policy', 'simplify this HR policy', 'write a plain language policy explanation']),
 'supplier_enquiry': ('Draft supplier enquiry', ['draft supplier enquiry', 'write a vendor enquiry', 'prepare a supplier inquiry']),
 'quotation_request': ('Draft quotation request', ['draft quotation request', 'write a request for quotation', 'prepare an RFQ']),
 'purchase_order_email': ('Draft purchase-order email', ['draft purchase-order email', 'write a purchase order covering message', 'prepare a PO email']),
 'stock_delay': ('Draft stock-delay update', ['draft stock-delay update', 'write a stock delay notification', 'prepare an inventory delay message']),
 'improve': ('Improve wording', ['improve wording', 'polish this text', 'rewrite this more clearly']),
 'shorten': ('Shorten text', ['shorten text', 'rewrite this concisely', 'condense this document']),
 'tone': ('Change tone', ['change tone', 'rewrite in a professional tone', 'rewrite politely']),
 'translate': ('Translate text', ['translate text', 'translate this document', 'translate this message to another language']),
 'extract': ('Extract key details', ['extract key details', 'identify important document facts', 'pull out essential information']),
}


def examples():
    return [{'text': phrase, 'intent': key} for key, (_, phrases) in SKILLS.items() for phrase in phrases]

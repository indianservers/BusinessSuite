"""Local extractive writing built on the action agent's TF-IDF features.

This is a bounded, offline drafting skill, not a generative language model.
Source text is data; it never triggers tools, sends messages or saves records.
"""
import json
import math
import re
from functools import lru_cache
from pathlib import Path

from app.ai_operator.local_features import features, fit_rows
from app.ai_operator.writing_corpus import SKILLS, VERSION, examples

ARTIFACT = Path(__file__).parent / 'assets' / 'local-writing-v1.json'


def normalize(command):
    command = re.sub(r'\bsummarise\b', 'summarize', command, flags=re.I)
    return re.sub(r'\b(?:these|this|the)\b', '', command, flags=re.I)


def train():
    rows = examples()
    idf, vectors = fit_rows([{**row, 'text': normalize(row['text'])} for row in rows])
    return {'version': VERSION, 'method': 'action-agent-tfidf-nearest-example',
            'examples': rows, 'idf': idf, 'vectors': vectors}


@lru_cache(maxsize=1)
def model():
    if ARTIFACT.exists():
        candidate = json.loads(ARTIFACT.read_text(encoding='utf-8'))
        if candidate.get('version') == VERSION and candidate.get('examples') == examples():
            return candidate
    return train()


def classify(text):
    """Only writing verbs enter this additive classifier; no task mutations."""
    command = text.partition(':')[0].strip()
    command = normalize(command)
    if not re.match(r'^(?:please\s+)?(?:draft|write|compose|prepare|summari[sz]e|suggest|extract|improve|polish|rewrite|shorten|condense|change|translate|explain|simplify|identify|pull|turn|break)\b', command, re.I):
        return None
    # Explicitly naming a new record belongs to the action planner, even when
    # its wording resembles a follow-up email in the writing corpus.
    from app.ai_operator.conversational_actions import clean, VERB, OBJECT
    if re.match(r'^'+VERB+r'\s+'+OBJECT+r'\s+(?:called|named|titled)\b', clean(command), re.I):
        return None
    bundle = model()
    counts = features(command)
    raw = {k: (1 + math.log(n)) * bundle['idf'][k] for k, n in counts.items() if k in bundle['idf']}
    norm = math.sqrt(sum(v*v for v in raw.values())) or 1
    vector = {k: v/norm for k, v in raw.items()}
    scores = [(sum(v * other.get(k, 0) for k, v in vector.items()), row['intent'])
              for row, other in zip(bundle['examples'], bundle['vectors'])]
    score, skill = max(scores, default=(0, None))
    # Mutation-like requests must continue through the original action planner.
    if re.search(r'\b(?:create|delete|assign|approve|send|save|schedule)\b', command, re.I):
        return None
    if re.search(r'\binvoice\b', command, re.I) and not re.search(r'\b(?:email|message|covering|reminder|follow.up)\b', command, re.I):
        return None
    return skill if score >= .70 else None


def sentences(text):
    text = re.sub(r'<[^>]*>', ' ', text)
    return [re.sub(r'\s+', ' ', line).strip(' •-\t') for line in re.split(r'\n+|(?<=[.!?])\s+', text)
            if line.strip(' •-\t')]


def summary(text, limit=6):
    lines = sentences(text)
    if not lines:
        return ''
    counts = features(' '.join(lines))
    # Prefer specific dates, amounts, owners and status over repeated prose.
    ranked = sorted(range(len(lines)), key=lambda i: sum(counts.get(w, 0) for w in features(lines[i])) / max(1, len(features(lines[i])))
                    + 2 * bool(re.search(r'\d|blocked|pending|decision|agreed|due|delay', lines[i], re.I)), reverse=True)[:limit]
    return '\n'.join('• ' + lines[i] for i in sorted(ranked))


def draft(skill, text='', *, title='', recipient='', tone='professional', language='English'):
    if skill not in SKILLS:
        raise ValueError('Unknown writing skill')
    text = text.strip()
    title = title.strip()[:200]
    greeting = f'Hello {recipient.strip()[:120]},' if recipient.strip() else 'Hello [recipient name],'
    facts = summary(text)
    missing = []
    if not text:
        missing.append('Add source notes or select a record to personalize this draft.')
    if not recipient and skill in {'client_email','reply','follow_up','meeting_invitation','whatsapp','status_update','invoice_email','payment_reminder','overdue_reminder','meeting_follow_up','support_reply','onboarding','supplier_enquiry','quotation_request','purchase_order_email','stock_delay'}:
        missing.append('Fill the recipient name before sending.')
    source = facts or '[Add the relevant details]'
    subject = title or SKILLS[skill][0].removeprefix('Draft ').capitalize()
    closing = 'Thank you,\n[your name]' if tone != 'friendly' else 'Thanks!\n[your name]'
    bodies = {
      'client_email': f'I am writing about {title or "[topic]"}.\n\n{source}\n\nPlease let me know if you have any questions.',
      'reply': f'Thank you for your message.\n\nRegarding the points you raised:\n{source}\n\n[Add your response or the confirmed next step.]',
      'follow_up': f'I am following up on {title or "[our previous discussion]"}.\n\n{source}\n\nCould you share an update and let us know the next step?',
      'meeting_invitation': f'Could we arrange a meeting to discuss {title or "[topic]"}?\n\nProposed agenda:\n{source}\n\nPlease confirm a suitable date and time: [date, time, timezone].',
      'whatsapp': f'{greeting} A quick update on {title or "[topic]"}:\n{summary(text, 3) or "[Add details]"}\nPlease let me know your thoughts.',
      'proposal': f'Proposal: {title or "[engagement]"}\n\nRequirements supplied\n{source}\n\nProposed scope\n[Confirm deliverables and exclusions]\n\nTimeline\n[Confirm milestones and dates]\n\nCommercial terms\n[Confirm pricing, currency, tax and payment terms]\n\nNext step\nPlease review the proposed scope so we can agree the details.',
      'talking_points': f'Discussion context\n{source}\n\nQuestions to discuss\n• Which outcome matters most?\n• Are there open questions or blockers?\n• Who owns the next step, and by when?',
      'task_description': f'{title or "Task brief"}\n\nContext\n{source}\n\nExpected outcome\n[Describe the result to deliver]\n\nAcceptance criteria\n• The result addresses the source requirements.\n• Validation is recorded and the relevant reviewer has checked it.\n\n[Confirm owner and deadline.]',
      'subtasks': f'Suggested checklist for {title or "this task"}\n• Confirm requirements and acceptance criteria.\n• Review the supplied context:\n{source}\n• Carry out the agreed work.\n• Validate the result against the requirements.\n• Document the outcome and request review.',
      'status_update': f'Here is the current update for {title or "[project]"}.\n\nReported progress\n{source}\n\nNext steps\n[Confirm owners and dates for outstanding items.]\n\nPlease let us know if priorities have changed.',
      'invoice_email': f'Please review invoice {title or "[invoice number]"}.\n\nInvoice details\n{source}\n\n[Attach the verified invoice and confirm the due date.]\nPlease contact us if you need any clarification.',
      'payment_reminder': f'This is a reminder regarding {title or "[invoice reference]"}.\n\nRecorded details\n{source}\n\nPlease confirm the payment status or expected payment date. If payment has already been made, please share the reference so we can reconcile it.',
      'overdue_reminder': f'We are following up on the payment status of {title or "[invoice reference]"}.\n\nRecorded details\n{source}\n\n[Verify that a balance remains overdue before sending.]\nCould you confirm when payment can be expected? If already paid, please share the payment reference.',
      'meeting_follow_up': f'Thank you for the discussion about {title or "[meeting topic]"}.\n\nRecap from the notes\n{source}\n\nNext steps\n{actions(text)}\n\nPlease let us know if anything needs correcting.',
      'support_reply': f'Thank you for contacting us about {title or "[issue]"}.\n\nMy understanding of the reported issue\n{source}\n\n[Add verified troubleshooting steps or a relevant knowledge article.]\nPlease share any additional details that would help us investigate.',
      'job_description': f'{title or "[Role title]"}\n\nRole context\n{source}\n\nResponsibilities\n[Confirm role-specific responsibilities]\n\nRequired skills\n[Confirm essential qualifications and experience]\n\nLocation and working arrangement\n[Confirm location, hours and employment type]\n\nHow to apply\n[Add the approved application process]',
      'interview_questions': f'Interview context\n{source}\n\nSuggested questions\n• Tell us about relevant work you have delivered.\n• How would you approach the responsibilities described above?\n• Describe a difficult problem and how you resolved it.\n• How do you communicate progress and blockers?\n• What would you like to learn about this role?',
      'onboarding': f'Welcome to the team!\n\nJoining information\n{source}\n\n[Confirm start date, reporting contact and first-day arrangements.]\nPlease let us know if you need help preparing for your first day.',
      'announcement': f'{title or "Team announcement"}\n\nHello team,\n\n{source}\n\n[Confirm the effective date, any action required and the contact for questions.]',
      'policy_explanation': f'Policy points from the supplied text\n{source}\n\nCheck the full approved policy for eligibility, exceptions and the applicable process. [Confirm any points not covered in the source.]',
      'supplier_enquiry': f'We would like information about {title or "[product or service]"}.\n\nRequirements\n{source}\n\nPlease confirm availability, specifications, lead time and applicable terms.',
      'quotation_request': f'Please provide a quotation for {title or "[required items]"}.\n\nRequirements\n{source}\n\nPlease specify unit prices, currency, taxes, delivery lead time, quotation validity and payment terms. [Confirm quantities and delivery location.]',
      'purchase_order_email': f'Please review purchase order {title or "[PO reference]"}.\n\nOrder details\n{source}\n\n[Attach the approved purchase order.]\nPlease acknowledge the order and confirm the delivery schedule.',
      'stock_delay': f'We would like to update you on {title or "[item or order]"}.\n\nCurrent information\n{source}\n\n[Confirm the delay, revised availability and any alternatives.]\nWe will share further information once the schedule is confirmed.',
    }
    if skill in {'client_summary','project_summary','meeting_summary','ticket_summary','extract'}:
        body = source
    elif skill == 'action_items':
        body = actions(text)
    elif skill == 'shorten':
        body = summary(text, 3) or '[Add text to shorten]'
    elif skill in {'improve','tone'}:
        # Preserve factual content. This offline skill cleans phrasing and adds
        # polite framing; it does not pretend to be a generative rewrite model.
        body = '\n\n'.join(sentences(text)) or '[Add text to improve]'
        body = re.sub(r'\bASAP\b', 'as soon as possible', body, flags=re.I)
        if skill == 'tone':
            body = ('Hi,\n\n' if tone == 'friendly' else 'Hello,\n\n') + body + '\n\n' + closing
    elif skill == 'translate':
        if language.casefold() != 'english':
            body = text
            missing.append(f'Translation to {language} is unavailable in the installed local writing model. Source retained; no translation was produced.')
        else:
            body = text
            missing.append('The offline model cannot detect or translate arbitrary languages. Source retained unchanged.')
    else:
        body = bodies[skill]
        if skill not in {'proposal','talking_points','task_description','subtasks','job_description','interview_questions','announcement','policy_explanation','whatsapp'}:
            body = f'{greeting}\n\n{body}\n\n{closing}'
    return {'action': skill, 'title': SKILLS[skill][0], 'subject': subject, 'text': body[:14000],
            'missing_details': missing, 'engine': VERSION, 'method': 'local-extractive-drafting',
            'cloud_calls': 0, 'source_characters': len(text)}


def actions(text):
    selected = [line for line in sentences(text) if re.search(r'\b(?:will|must|should|todo|to do|action|agreed|decision|follow.up|owner|due|next|send|review|confirm|prepare|deliver)\b', line, re.I)]
    return '\n'.join('• ' + line for line in selected[:10]) or '[No explicit decisions or action items found. Confirm the next steps, owners and dates.]'


def chat_plan(text):
    command, separator, source = text.partition(':')
    # A live project reference without supplied notes belongs to native reads.
    # Explicit source text after a colon remains an extractive writing request.
    if not separator and re.match(r'^\s*(?:please\s+)?summari[sz]e\s+(?:this|our|my|the current)\s+project\b',command,re.I):
        return None
    skill = classify(command)
    if not skill:
        return None
    if not separator or not source.strip():
        return {'summary': 'Local writing skill selected.', 'question': 'Add the source details after a colon, for example: Draft client email: Renewal review is due Friday.', 'steps': []}
    result = draft(skill, source)
    return {'summary': (result['text'] + ('\n\n' + ' '.join(result['missing_details']) if result['missing_details'] else ''))[:2000], 'steps': []}

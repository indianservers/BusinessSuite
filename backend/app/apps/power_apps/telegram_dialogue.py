"""Server-owned multilingual menus, durable memory and typed industry intake."""
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from app.apps.power_apps.telegram_experience import configuration, IndustryWorkflow, qualify

TEXT = {
    'en': {'choose': 'Choose a service or request.', 'cancel': 'Request cancelled. Your saved preferences are unchanged.', 'invalid': 'Please provide a valid answer.', 'location': 'Share location', 'document': 'Please attach the required document.', 'saved': 'Your request has been received.', 'language': 'Language saved.', 'forgot': 'Your saved conversation preferences have been cleared.', 'empty_memory': 'No saved preferences yet.', 'human': 'Talk to a person', 'sales': 'Sales', 'support': 'Support', 'order': 'Order status', 'services': 'Services', 'book': 'Book appointment'},
    'te': {'choose': 'సేవ లేదా అభ్యర్థనను ఎంచుకోండి.', 'cancel': 'అభ్యర్థన రద్దయింది. సేవ్ చేసిన ప్రాధాన్యతలు మారలేదు.', 'invalid': 'దయచేసి సరైన సమాధానం ఇవ్వండి.', 'location': 'స్థానాన్ని పంచుకోండి', 'document': 'దయచేసి అవసరమైన పత్రాన్ని జత చేయండి.', 'saved': 'మీ అభ్యర్థన అందింది.', 'language': 'భాష సేవ్ చేయబడింది.', 'forgot': 'సేవ్ చేసిన సంభాషణ ప్రాధాన్యతలు తొలగించబడ్డాయి.', 'empty_memory': 'ఇంకా సేవ్ చేసిన ప్రాధాన్యతలు లేవు.', 'human': 'సిబ్బందితో మాట్లాడండి', 'sales': 'కొనుగోలు', 'support': 'సహాయం', 'order': 'ఆర్డర్ స్థితి', 'services': 'సేవలు', 'book': 'అపాయింట్‌మెంట్ బుక్ చేయండి'},
    'hi': {'choose': 'सेवा या अनुरोध चुनें।', 'cancel': 'अनुरोध रद्द कर दिया गया। सहेजी गई प्राथमिकताएँ नहीं बदली हैं।', 'invalid': 'कृपया सही उत्तर दें।', 'location': 'स्थान साझा करें', 'document': 'कृपया आवश्यक दस्तावेज़ संलग्न करें।', 'saved': 'आपका अनुरोध प्राप्त हो गया है।', 'language': 'भाषा सहेज दी गई।', 'forgot': 'आपकी सहेजी गई बातचीत की प्राथमिकताएँ हटा दी गई हैं।', 'empty_memory': 'अभी कोई प्राथमिकता सहेजी नहीं गई है।', 'human': 'कर्मचारी से बात करें', 'sales': 'खरीदारी', 'support': 'सहायता', 'order': 'ऑर्डर की स्थिति', 'services': 'सेवाएँ', 'book': 'अपॉइंटमेंट बुक करें'},
}


def validate_markup(value):
    from app.apps.power_apps.integrations.contracts import IntegrationFailure
    try:
        markup = json.loads(value)
        if not isinstance(markup, dict) or set(markup) - {'inline_keyboard', 'keyboard', 'resize_keyboard', 'one_time_keyboard', 'remove_keyboard'}:
            raise ValueError('Unsupported keyboard shape')
        if sum(key in markup for key in ['inline_keyboard', 'keyboard', 'remove_keyboard']) != 1:
            raise ValueError('Choose one keyboard type')
        for flag in ['resize_keyboard', 'one_time_keyboard', 'remove_keyboard']:
            if flag in markup and type(markup[flag]) is not bool:
                raise ValueError('Keyboard flags must be boolean')
        rows = markup.get('inline_keyboard', markup.get('keyboard', []))
        if not isinstance(rows, list) or len(rows) > 30:
            raise ValueError('Too many keyboard rows')
        for row in rows:
            if not isinstance(row, list) or not 1 <= len(row) <= 8:
                raise ValueError('Invalid keyboard row')
            for button in row:
                if not isinstance(button, dict) or set(button) - {'text', 'callback_data', 'request_location'} or not isinstance(button.get('text'), str) or not 1 <= len(button['text']) <= 120:
                    raise ValueError('Invalid keyboard button')
                if 'callback_data' in button and (not isinstance(button['callback_data'], str) or not 1 <= len(button['callback_data'].encode()) <= 64):
                    raise ValueError('Callback data exceeds Telegram limits')
                if 'request_location' in button and type(button['request_location']) is not bool:
                    raise ValueError('Invalid location request')
        return markup
    except (ValueError, TypeError):
        raise IntegrationFailure('schema', 'Invalid Telegram keyboard') from None


def language(thread, text=''):
    current = (thread.context or {}).get('language')
    if current in TEXT:
        return current
    return 'te' if re.search(r'[\u0c00-\u0c7f]', text) else 'hi' if re.search(r'[\u0900-\u097f]', text) else 'en'


def canonical(text, collecting=False):
    if collecting:
        return text
    choices = {'sales': 'Sales', 'support': 'Support', 'order': 'Order status', 'human': '/human', 'services': '/services', 'book': '/book'}
    for messages in TEXT.values():
        for key, command in choices.items():
            if text.strip().casefold() == messages[key].casefold():
                return command
    return text


def localize(reply, thread):
    """Translate server-owned prompts; never translate customer values or sourced facts."""
    lang = language(thread)
    if lang == 'en':
        return reply
    prompts = {
        'Welcome! Choose Sales, Support, or Order status. Send /cancel to reset.': ('స్వాగతం! కొనుగోలు, సహాయం లేదా ఆర్డర్ స్థితిని ఎంచుకోండి. మళ్లీ ప్రారంభించడానికి /cancel పంపండి.', 'स्वागत है! खरीदारी, सहायता या ऑर्डर की स्थिति चुनें। फिर से शुरू करने के लिए /cancel भेजें।'),
        'Please enter your name (up to 180 characters).': ('దయచేసి మీ పేరు రాయండి (180 అక్షరాల వరకు).', 'कृपया अपना नाम लिखें (अधिकतम 180 अक्षर)।'),
        'Please describe your requirement.': ('దయచేసి మీ అవసరాన్ని వివరించండి.', 'कृपया अपनी आवश्यकता बताएं।'),
        'Please enter your order number and question.': ('దయచేసి మీ ఆర్డర్ నంబర్ మరియు ప్రశ్న రాయండి.', 'कृपया अपना ऑर्डर नंबर और प्रश्न लिखें।'),
        'Thanks! We’ve received your enquiry. Our team will follow up. Send /start for another enquiry.': ('ధన్యవాదాలు! మీ అభ్యర్థన అందింది. మా బృందం మిమ్మల్ని సంప్రదిస్తుంది. మరో అభ్యర్థన కోసం /start పంపండి.', 'धन्यवाद! आपका अनुरोध प्राप्त हुआ। हमारी टीम संपर्क करेगी। दूसरे अनुरोध के लिए /start भेजें।'),
        'Your conversation is in the human support queue. You can continue sending messages here.': ('మీ సంభాషణ సిబ్బంది సహాయ క్యూలో ఉంది. మీరు ఇక్కడ సందేశాలు పంపవచ్చు.', 'आपकी बातचीत सहायता टीम की कतार में है। आप यहाँ संदेश भेज सकते हैं।'),
        'Describe your internal request. It will be recorded for your company administrator.': ('మీ అంతర్గత అభ్యర్థనను వివరించండి. అది మీ కంపెనీ నిర్వాహకుని కోసం నమోదు అవుతుంది.', 'अपना आंतरिक अनुरोध बताएं। यह आपकी कंपनी के व्यवस्थापक के लिए दर्ज होगा।'),
        'Internal request recorded. Send /company to return to your workspace.': ('అంతర్గత అభ్యర్థన నమోదు అయింది. మీ కార్యస్థలానికి తిరిగి రావడానికి /company పంపండి.', 'आंतरिक अनुरोध दर्ज हुआ। कार्यस्थल पर लौटने के लिए /company भेजें।'),
    }
    if reply in prompts:
        return prompts[reply][0 if lang == 'te' else 1]
    for topic, key in [('Sales', 'sales'), ('Support', 'support'), ('Order status', 'order')]:
        if reply == f'{topic} enquiry: what is your name?':
            return TEXT[lang][key] + (': మీ పేరు ఏమిటి?' if lang == 'te' else ': आपका नाम क्या है?')
    return reply


def menu(trigger, interface, lang):
    labels = TEXT[lang]
    rows = [[{'text': labels['sales'], 'callback_data': 'menu:sales'}, {'text': labels['support'], 'callback_data': 'menu:support'}],
            [{'text': labels['order'], 'callback_data': 'menu:order'}, {'text': labels['human'], 'callback_data': 'menu:human'}],
            [{'text': 'English', 'callback_data': 'lang:en'}, {'text': 'తెలుగు', 'callback_data': 'lang:te'}, {'text': 'हिन्दी', 'callback_data': 'lang:hi'}]]
    for flow in configuration(trigger).workflows:
        if flow.enabled and flow.interface in {interface, 'both'}:
            rows.append([{'text': flow.name, 'callback_data': f'wf:{flow.id}'}])
    if configuration(trigger).booking_services:
        rows.append([{'text': labels['book'], 'callback_data': 'menu:book'}])
    return {'inline_keyboard': rows[:30]}


def callback_text(data):
    if data in {'lang:en', 'lang:te', 'lang:hi'}:
        return '/language ' + data[5:]
    menus = {'menu:sales': 'Sales', 'menu:support': 'Support', 'menu:order': 'Order status', 'menu:human': '/human', 'menu:book': '/book'}
    if data in menus:
        return menus[data]
    if re.fullmatch(r'wf:[a-z][a-z0-9_-]{0,63}', data):
        return '/request ' + data[3:]
    if re.fullmatch(r'(approve|reject):[a-f0-9]{32}', data):
        return '/' + data.replace(':', ' ', 1)
    if re.fullmatch(r'review:[a-f0-9]{32}:\d{1,2}', data):
        return '/' + data.replace(':', ' ')
    for prefix, command in [('book:', '/book '), ('slot:', '/slot '), ('customer:', '/bookcustomer ')]:
        if data.startswith(prefix) and data[len(prefix):].isdigit():
            return command + data[len(prefix):]
    return None


def prompt(question, lang):
    message = question.translations.get(lang) or question.label
    if question.type == 'document':
        message += '\n' + TEXT[lang]['document']
    if question.type == 'date':
        message += '\nYYYY-MM-DD'
    if question.type == 'choice':
        return message, {'keyboard': [[{'text': value}] for value in question.choices], 'resize_keyboard': True, 'one_time_keyboard': True}
    if question.type == 'location':
        return message, {'keyboard': [[{'text': TEXT[lang]['location'], 'request_location': True}]], 'resize_keyboard': True, 'one_time_keyboard': True}
    return message, {'remove_keyboard': True}


def answer(question, text, attachment=None):
    if text.strip().casefold() == '/skip' and not question.required:
        return None
    if question.type == 'location':
        if not attachment or attachment.get('type') != 'location':
            raise ValueError('Share a location using the location button')
        lat, lon = attachment.get('latitude'), attachment.get('longitude')
        if type(lat) not in {int, float} or type(lon) not in {int, float} or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError('Invalid location coordinates')
        return {'latitude': lat, 'longitude': lon}
    if question.type == 'document':
        if not attachment or attachment.get('type') != 'document' or not attachment.get('file_id'):
            raise ValueError('Attach the required document')
        if attachment.get('file_size', 0) > 20 * 1024 * 1024:
            raise ValueError('Document exceeds 20 MB')
        if question.accepted_mime_types and attachment.get('mime_type') not in question.accepted_mime_types:
            raise ValueError('Choose an accepted document format')
        return {key: attachment.get(key) for key in ['file_id', 'file_unique_id', 'file_name', 'mime_type', 'file_size']}
    if not text.strip() or len(text) > 2000:
        raise ValueError('Answer must contain 1–2000 characters')
    if question.type == 'choice' and text not in question.choices:
        raise ValueError('Choose one of the displayed options')
    if question.type == 'date':
        date.fromisoformat(text)
    if question.type == 'number':
        try:
            amount = Decimal(re.sub(r'^(?:₹|INR|Rs\.?|\$)\s*', '', text.strip(), flags=re.I).replace(',', ''))
        except InvalidOperation:
            raise ValueError('Enter a valid number or amount')
        if not amount.is_finite() or question.minimum is not None and amount < Decimal(str(question.minimum)) or question.maximum is not None and amount > Decimal(str(question.maximum)):
            raise ValueError('Number is outside the allowed range')
        return {'text': text, 'value': str(amount)}
    return text  # Names, dates and mixed-language free text remain verbatim.


def handle(thread, trigger, text, state, attachment=None):
    """Return (handled, state, reply, keyboard); business writes remain in ingress."""
    lang = language(thread, text)
    thread.context = {**(thread.context or {}), 'language': lang}
    if text.startswith('/language '):
        choice = text.split(maxsplit=1)[1]
        if choice not in TEXT:
            return True, state, 'Choose /language en, /language te or /language hi.', None
        thread.context = {**thread.context, 'language': choice}
        return True, state, TEXT[choice]['language'], menu(trigger, thread.interface, choice)
    if text == '/memory':
        memory = thread.context.get('memory', {})
        requests = thread.context.get('requests', [])
        return True, state, json.dumps({'preferences': memory, 'unresolved_requests': [item for item in requests if item.get('status') != 'completed']}, ensure_ascii=False)[:3800] if memory or requests else TEXT[lang]['empty_memory'], None
    if text == '/forget':
        thread.context = {key: value for key, value in thread.context.items() if key not in {'memory', 'last_answers'}}
        return True, state, TEXT[lang]['forgot'], None
    if text == '/cancel' and state.get('stage') == 'workflow':
        return True, {'stage': 'menu', 'interface': thread.interface}, TEXT[lang]['cancel'], menu(trigger, thread.interface, lang)
    if text == '/services':
        return True, state, TEXT[lang]['choose'], menu(trigger, thread.interface, lang)
    settings = configuration(trigger)
    if text == 'Sales' and settings.lead_workflow_id:
        text = '/request ' + settings.lead_workflow_id
    if text.startswith('/request '):
        ident = text.split(maxsplit=1)[1]
        flow = next((item for item in settings.workflows if item.id == ident and item.enabled and item.interface in {thread.interface, 'both'}), None)
        if not flow:
            return True, state, 'This service workflow is unavailable.', None
        next_state = {'stage': 'workflow', 'interface': thread.interface, 'workflow_id': flow.id, 'workflow_revision': settings.revision, 'question_index': 0, 'answers': {}}
        message, keyboard = prompt(flow.questions[0], lang)
        return True, next_state, message, keyboard
    if state.get('stage') != 'workflow':
        return False, state, None, None
    flow = next((item for item in settings.workflows if item.id == state.get('workflow_id') and item.enabled and item.interface in {thread.interface, 'both'}), None)
    if not flow or state.get('workflow_revision') != settings.revision:
        return True, {'stage': 'menu', 'interface': thread.interface}, 'This workflow changed. Choose the service again to use the current questions.', menu(trigger, thread.interface, lang)
    index = state['question_index']
    question = flow.questions[index]
    try:
        value = answer(question, text, attachment)
    except (ValueError, TypeError) as error:
        message, keyboard = prompt(question, lang)
        return True, state, TEXT[lang]['invalid'] + '\n' + str(error) + '\n' + message, keyboard
    answers = {**state['answers'], question.key: value}
    if index + 1 < len(flow.questions):
        message, keyboard = prompt(flow.questions[index + 1], lang)
        return True, {**state, 'answers': answers, 'question_index': index + 1}, message, keyboard
    result = qualify(flow, answers)
    memory = {**thread.context.get('memory', {}), **{key: value for key, value in answers.items() if key in {'full_name', 'name', 'service', 'location', 'preferred_contact_time'}}}
    thread.context = {**thread.context, 'memory': memory, 'last_answers': {**thread.context.get('last_answers', {}), flow.id: answers}, 'qualification': result,
        'workflow_id': flow.id, 'workflow_revision': settings.revision, 'service_stage': flow.stages[0].key, 'required_skills': flow.required_skills}
    next_state = {**state, 'stage': 'complete', 'answers': answers, 'qualification': result,
        'topic': 'Sales' if flow.result == 'lead_and_task' else 'Support',
        'name': answers.get('full_name') or answers.get('name') or memory.get('full_name') or 'Telegram enquiry',
        'requirement': '\n'.join(f'{item.label}: {json.dumps(answers[item.key], ensure_ascii=False) if isinstance(answers.get(item.key), dict) else answers.get(item.key)}' for item in flow.questions)[:4000],
        'workflow_result': flow.result, 'requires_stage_approval': flow.stages[0].requires_approval}
    return True, next_state, TEXT[lang]['saved'] + '\n' + '\n'.join(result['reasons']), {'remove_keyboard': True}

"""Server-issued evidence and bounded local intents shared by the suite assistant."""
import re
from fastapi import HTTPException


def records(value):
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        for key in ('items', 'data'):
            if isinstance(value.get(key), list):
                return records(value[key])
        if type(value.get('id')) is int:
            return [value]
    return []


def source_link(tool, row, project_id=None):
    ident = row.get('id')
    if tool.startswith('pms.'):
        if tool == 'pms.tasks' and type(ident) is int:
            return f'/pms/tasks/{ident}'
        project = project_id if tool == 'pms.tasks' else ident
        return f'/pms/projects/{project}' if type(project) is int else '/pms/projects'
    if tool.startswith('crm.'):
        entity = tool.split('.')[1]
        entity = {'task': 'tasks', 'deal': 'deals', 'lead': 'leads'}.get(entity, entity)
        return f'/crm/{entity}'
    return '/leave' if tool == 'hrms.my_leave' else '/helpdesk'


def issue_sources(context, retrieved_at):
    result = []
    for index, packet in enumerate(context, 1):
        for row in records(packet['records']):
            ident = row.get('id')
            if type(ident) is not int or ident <= 0:
                continue
            result.append({
                'id': f's{index}:{ident}', 'tool': packet['tool'], 'record_id': ident,
                'label': str(row.get('title') or row.get('name') or row.get('subject') or f'Record {ident}')[:220],
                'href': source_link(packet['tool'], row, packet.get('record_id')),
                'retrieved_at': retrieved_at,
            })
    return result


def select_sources(ids, available):
    by_id = {source['id']: source for source in available}
    if any(ident not in by_id for ident in ids):
        raise HTTPException(422, 'Answer contains an unknown evidence reference')
    return [by_id[ident] for ident in dict.fromkeys(ids)]


def local_reply(text, context, sources, *, project_id=None, request_key='', summary_only=False):
    """No model/network fallback. Only explicit task commands or sampled summaries."""
    match = re.fullmatch(r'\s*create\s+(CRM|PMS)\s+task\s*:\s*(.{1,220})\s*', text, re.I)
    if match and not summary_only:
        module, title = match.groups()
        if module.upper() == 'PMS' and not project_id:
            return {'summary': 'Select a project before preparing this task.', 'question': 'Which project should contain this task?', 'steps': []}
        step = {'tool': f'{module.lower()}.create_task', 'payload': {'title': title.strip()}}
        if module.upper() == 'PMS':
            step.update(record_id=project_id)
            step['payload']['task_key'] = 'AI-' + re.sub(r'[^a-zA-Z0-9]', '', request_key)[:16]
        return {'summary': 'Review this new task. Nothing has been created yet.', 'steps': [step]}
    if summary_only or re.search(r'\b(summary|summarize|priorities|brief|report|risk)\b', text, re.I):
        counts = ', '.join(f"{p['tool']}: {len(records(p['records']))} sampled records" for p in context)
        return {'summary': f'Authorized source snapshot: {counts or "no sources selected"}. Open the daily briefing for deterministic deadline and blocker signals. These are bounded samples, not company-wide totals.', 'steps': [], 'source_ids': [s['id'] for s in sources][:50]}
    return {'summary': 'Local mode supports source summaries and explicit task drafts.', 'question': 'Use “Create CRM task: title”, “Create PMS task: title” with a project selected, or ask for a summary. Choose OpenAI or Gemini for broader requests.', 'steps': []}

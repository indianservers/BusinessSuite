"""Grounded dashboard questions using pinned, freshly authorized source reads."""
import json
import re
from fastapi import HTTPException
from pydantic import Field,StrictInt,field_validator
from app.ai_operator.suite_tools import Strict


class PanelRead(Strict):
    artifact_id:StrictInt=Field(gt=0)
    position:StrictInt=Field(ge=1,le=6)
    dashboard_revision:StrictInt|None=Field(default=None,ge=1,le=100)
    category_query:str=Field(default='',max_length=100)

    @field_validator('category_query')
    @classmethod
    def safe_category(cls,value):
        if re.search(r'[\x00-\x1f\ud800-\udfff\ufffe\uffff]',value):raise ValueError('Category filters cannot contain unsupported control characters')
        return value


def read(db,user,module,workspace_id,query,agent_id=None):
    from app.ai_operator import artifacts,artifact_charts as charts
    from app.ai_operator.artifact_dashboards import resolve
    from app.ai_agents.security import limits,company
    row=artifacts.owned(db,user,query.artifact_id)
    if row.references['module']!=module or row.workspace_id!=workspace_id:raise HTTPException(403,'Select the dashboard in its original module/workspace')
    dashboard=artifacts.public(db,user,row,query.dashboard_revision)
    if dashboard['kind']!='dashboard' or query.position>len(dashboard['panels']):raise HTTPException(404,'Dashboard panel not found')
    panel=dashboard['panels'][query.position-1];source=resolve(db,user,workspace_id,panel)
    if agent_id:
        from app.ai_operator import saved_agents
        agent=saved_agents.owned(db,user,agent_id);saved_agents.runtime_access(db,user,agent)
        if source['module'] not in saved_agents.public(agent)['modules']:raise HTTPException(403,'The pinned source module is outside this agent scope')
    text=source['content']
    if source['kind']=='presentation':text='\n'.join(s['title']+'\n'+'\n'.join(s['bullets']) for s in source['slides'])
    result={'id':source['id'],'title':source['title'],'module':source['module'],'kind':source['kind'],'revision':source['revision'],
        'current_revision':source['current_revision'],'dashboard_id':dashboard['id'],'dashboard_revision':dashboard['revision'],
        'panel_position':query.position,'panel_label':panel['label'],'category_query':query.category_query,
        'excerpt':text[:600],'excerpt_truncated':len(text)>600,'source_citation':charts.evidence(source),
        'coverage':'One authorized pinned artifact snapshot; supplied/generated assertions, not verified live ERP facts.'}
    cap=limits(db,company(user))['max_result_bytes']
    if source['kind']=='table':
        budget=cap-len(json.dumps(result,ensure_ascii=False).encode())-32
        if budget<1000:raise HTTPException(422,'Panel analysis exceeds the disclosure budget; narrow the source or ask about one smaller panel')
        result['analysis']=charts.bounded(charts.analyze(source,category_query=query.category_query),budget)
    elif query.category_query:raise HTTPException(422,'Category filters require a table panel')
    if len(json.dumps(result,ensure_ascii=False).encode())>cap:raise HTTPException(422,'Panel answer exceeds the disclosure budget')
    return result


def intent(text,parent=None):
    """Return only explicit read questions; document/task text remains inert."""
    text=text.strip().rstrip('?.! ')
    text=re.sub(r'(?i),?\s+please$','',text)
    verb=r'(?:analy[sz]e|summari[sz]e|read|show(?: me)?|explain|review|tell me about|give me (?:a |the )?summary of|what(?: is|\x27s) in)'
    prefix=rf'(?:please\s+)?{verb}\s+(?:(?:this|the|my)\s+)?'
    prior=(parent.result or {}).get('dashboard_query') if parent else None
    ordinal=re.fullmatch(rf'(?i)(?:{prefix})?(?:the\s+)?(first|second|third|fourth|fifth|sixth|[1-6](?:st|nd|rd|th))\s+panel',text)
    one=re.fullmatch(r'(?i)(?:what about|show|read|summari[sz]e|analy[sz]e) (?:the )?(first|second|third|fourth|fifth|sixth) one',text) if prior else None
    if ordinal or one:
        value=(ordinal or one)[1].lower();position=['first','second','third','fourth','fifth','sixth'].index(value)+1 if value.isalpha() else int(value[0])
        text=f'Show panel {position}'
    selected=re.fullmatch(rf'(?i){prefix}panel\s+(\d+)\s+(?:of|in)\s+(?:the\s+)?dashboard\s*#?\s*(\d+)',text)
    if selected:return {'artifact_id':int(selected[2]),'positions':[int(selected[1])],'category_query':''}
    explicit=re.fullmatch(rf'(?i){prefix}dashboard(?:\s*#?\s*(\d+))?',text)
    panel=re.fullmatch(rf'(?i)(?:{prefix})?panel\s+(\d+)',text)
    named=re.fullmatch(rf'(?is){prefix}panel\s+(?:called|named)\s+(.{{1,100}})',text)
    totals=re.fullmatch(r'(?i)(?:(?:what (?:are|is)|show(?: me)?|calculate)\s+)?(?:the\s+)?(?:totals?|statistics|summary)(?:\s+(?:for|in|of)\s+panel\s+(\d+))?',text)
    only=re.fullmatch(r'(?is)(?:only|filter(?: (?:the )?category)?(?: to)?|show only)\s*:?\s*(.{1,100})',text)
    clear=re.fullmatch(r'(?i)(?:clear|remove|reset) (?:the )?(?:category )?filter|show all categories',text)
    if explicit:return {'artifact_id':int(explicit[1]) if explicit[1] else None,'positions':None,'category_query':''}
    if named:return {'artifact_id':prior['artifact_id'] if prior else None,'dashboard_revision':prior['dashboard_revision'] if prior else None,
        'positions':None,'panel_label':named[1].strip().strip('"\x27'),'category_query':''}
    if panel or totals:
        selected=(panel or totals)[1]
        return {'artifact_id':prior['artifact_id'] if prior else None,'dashboard_revision':prior['dashboard_revision'] if prior else None,
            'positions':[int(selected)] if selected else None,'generic':not panel and not selected and not prior,
            'category_query':prior.get('category_query','') if prior and selected and (prior.get('positions')==[int(selected)] or parent.status=='needs_clarification') else ''}
    if prior and (only or clear):return {**{k:prior[k] for k in ('artifact_id','dashboard_revision','positions')},'category_query':only[1].strip() if only else ''}
    return None


def focus(db,user,data,selection,history):
    if not selection:return
    if selection.get('artifact_id'):
        if data.artifact_id and data.artifact_id!=selection['artifact_id']:raise HTTPException(409,'Select one dashboard target for this question')
        data.artifact_id=selection['artifact_id'];return
    if data.artifact_id:return
    from app.ai_operator import artifacts
    for run in reversed(history):
        receipts=[r for r in run.receipts or [] if r.get('artifact_id')]
        if receipts:
            if receipts[-1].get('artifact_kind') not in (None,'dashboard'):break
            row=artifacts.owned(db,user,receipts[-1]['artifact_id'])
            if row.references['kind']=='dashboard':data.artifact_id=row.id
            break
        if run.receipts:break


def prepare(data,parent,context,selection):
    from app.ai_operator.suite import Plan,Step
    if not selection:return None,None
    if selection.get('generic') and (not context or context['kind']!='dashboard'):return None,None
    if parent and parent.status in ('awaiting_approval','needs_clarification') and not (parent.result or {}).get('dashboard_query'):
        raise HTTPException(409,'Finish or cancel the pending draft before asking a new dashboard question')
    if not context or context['kind']!='dashboard':
        return Plan(summary='Choose a saved dashboard before asking about its panels.',question='Use Analyze dashboard #ID. Saved dashboard IDs are listed under Artifacts.',steps=[]),None
    positions=selection['positions'] or list(range(1,len(context['panels'])+1))
    if selection.get('panel_label'):
        positions=[i for i,p in enumerate(context['panels'],1) if p['label'].casefold()==selection['panel_label'].casefold()]
        if len(positions)!=1:
            return Plan(summary='The panel label is missing or ambiguous.',question='Choose an exact panel number from this dashboard.',steps=[]),{
                'artifact_id':context['id'],'dashboard_revision':context['revision'],'positions':None,'category_query':''}
    if any(not 1<=position<=len(context['panels']) for position in positions):
        return Plan(summary='Choose an existing dashboard panel.',question=f'This dashboard has {len(context["panels"])} panels. Which panel number should I read?',steps=[]),{
            'artifact_id':context['id'],'dashboard_revision':context['revision'],'positions':None,'category_query':''}
    packet={'artifact_id':context['id'],'dashboard_revision':context['revision'],'positions':positions,'category_query':selection['category_query']}
    if selection['category_query'] and len(positions)>1:
        return Plan(summary='Choose one table panel for this category filter.',question='Which panel number should use this filter? The dashboard and its source pins are unchanged.',steps=[]),packet
    data.context=[Step(tool=data.module.lower()+'.dashboard_panel',payload={'artifact_id':context['id'],'position':position,
        'dashboard_revision':context['revision'],'category_query':selection['category_query']}) for position in positions]
    return Plan(summary='Read the authorized pinned dashboard sources and compute their snapshot statistics.',steps=[]),packet


def answer(context,packet):
    values=[p['records'] for p in context if p['tool'].endswith('.dashboard_panel')]
    if len(values)!=len(packet['positions']):raise HTTPException(422,'Not all requested dashboard panels were read')
    lines=[f"Dashboard #{packet['artifact_id']} version {packet['dashboard_revision']}: pinned source snapshots, not live ERP totals."]
    if packet['category_query']:lines.append(f"Category contains {packet['category_query']!r}. This filter does not edit the saved dashboard.")
    sources=[]
    for value in values:
        if not value.get('source_citation'):raise HTTPException(422,'Panel result exceeded the disclosure budget; ask about a smaller source')
        sources.append(value['source_citation']['id'])
        lines.append(f"Panel {value['panel_position']} / {value['panel_label'] or value['title']} / {value['module']} artifact #{value['id']} v{value['revision']}:")
        if value['current_revision']>value['revision']:lines.append('A newer source version exists; this answer retains the dashboard pin.')
        analysis=value.get('analysis')
        if analysis:
            lines.append(f"{analysis['row_count']} source rows; {analysis['valid_rows']} matching valid rows.")
            if not analysis['panels']:lines.append('No grouped metric is configured or no matching numeric rows remain. Configure the source chart to calculate grouped totals.')
            for panel in analysis['panels']:
                stats=panel['statistics'];lines.append(f"{panel['unit'] or 'Unit not specified'} / {panel['value_label']}: count {stats['count']}, sum {stats['sum']}, mean {stats['mean']}, min {stats['min']}, max {stats['max']}.")
            lines.append(f"Excluded metric values: {analysis['blank_numeric_rows']} blank, {analysis['invalid_numeric_rows']} invalid. Means round to six decimals.")
            if analysis['omitted_units']:lines.append(f"{analysis['omitted_units']} additional unit groups are outside this view.")
        else:lines.append(value['excerpt']+(' [Excerpt only; open the source for the full text.]' if value['excerpt_truncated'] else ''))
    summary='\n'.join(lines)
    if len(summary)>2000:return {'summary':'This dashboard answer exceeds one response. Ask about one panel at a time; no source totals have been combined.','question':'Which panel number should I analyze?','steps':[],'source_ids':[]}
    return {'summary':summary,'steps':[],'source_ids':list(dict.fromkeys(sources))}

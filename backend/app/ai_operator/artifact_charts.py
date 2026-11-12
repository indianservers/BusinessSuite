"""Bounded Decimal analysis of inert table snapshots. No formulas or code run."""
import json
import re
from collections import defaultdict
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
from typing import Literal
from pydantic import Field,model_validator
from fastapi import HTTPException
from app.ai_operator.suite_tools import Strict
from app.ai_operator.service import digest


class Chart(Strict):
    kind:Literal['bar','line','pie']='bar'
    category_column:int=Field(default=0,ge=0,le=11)
    value_column:int|None=Field(default=None,ge=0,le=11)
    series_column:int|None=Field(default=None,ge=0,le=11)
    unit_column:int|None=Field(default=None,ge=0,le=11)
    aggregation:Literal['sum','count','mean','min','max']='sum'
    monetary:bool=True
    category_limit:int=Field(default=20,ge=1,le=50)
    series_limit:int=Field(default=6,ge=1,le=8)
    unit_limit:int=Field(default=6,ge=1,le=8)
    order:Literal['input','category','value_desc']='input'

    @model_validator(mode='after')
    def valid(self):
        if self.aggregation!='count' and self.value_column is None:raise ValueError('Select a numeric value column or count rows')
        if self.aggregation=='count' and self.value_column is not None:raise ValueError('Row counts do not use a value column')
        if self.kind=='pie' and self.series_column is not None:raise ValueError('Pie charts use one series per unit; remove the series split or use bars/lines')
        return self


NUMBER=re.compile(r'^[+-]?(?:(?:\d+|\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})+,\d{3})(?:\.\d{0,6})?|\.\d{1,6})$',re.ASCII)


def number(text):
    text=text.strip()
    if len(text)>40 or not NUMBER.fullmatch(text):return None
    try:value=Decimal(text.replace(',',''))
    except InvalidOperation:return None
    return value if value.is_finite() and abs(value)<=Decimal('1e15') else None


def formatted(value):
    if value is None:return None
    rounded=value.quantize(Decimal('.000001'),rounding=ROUND_HALF_UP)
    if not rounded:return '0'
    text=format(rounded,'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def statistics(values):
    if not values:return {'count':0,'sum':None,'mean':None,'min':None,'max':None}
    total=sum(values,Decimal(0))
    return {'count':len(values),'sum':formatted(total),'mean':formatted(total/len(values)),
        'min':formatted(min(values)),'max':formatted(max(values))}


def validate_columns(spec,columns):
    for index in (spec.category_column,spec.value_column,spec.series_column,spec.unit_column):
        if index is not None and index>=len(columns):raise ValueError('Chart columns must refer to existing table column positions')
    currencies=[]
    for i,name in enumerate(columns):
        key=re.sub(r'[\s_-]+','',name.casefold())
        if key in ('ccy','currencysymbol') or key.endswith(('currency','currencycode')):currencies.append(i)
    if spec.aggregation=='count':return spec.unit_column
    if not spec.monetary:return spec.unit_column
    if len(currencies)>1 and spec.unit_column not in currencies:raise ValueError('Select the currency column for this metric explicitly')
    if currencies and spec.unit_column is not None and spec.unit_column not in currencies:raise ValueError('Partition this metric by its currency column; currencies cannot be combined')
    return spec.unit_column if spec.unit_column is not None else currencies[0] if currencies else None


def analyze(body,*,category_query='',series_key=None,order=None,limit=None,chart_kind=None):
    columns,rows=body['columns'],body['rows']
    profiles=[]
    for i,name in enumerate(columns):
        numeric=sum(number(row[i]) is not None for row in rows);blank=sum(not row[i].strip() for row in rows)
        profiles.append({'index':i,'name':name,'numeric':numeric,'blank':blank,'nonnumeric':len(rows)-numeric-blank,'distinct':len({row[i] for row in rows})})
    result={'row_count':len(rows),'profiles':profiles,'panels':[],'invalid_numeric_rows':0,'blank_numeric_rows':0,
        'filtered_rows':0,'valid_rows':0,'omitted_units':0,'available_series':[],
        'method':'Server Decimal aggregation of the selected table snapshot. No formulas are evaluated. Blank, nonnumeric and out-of-range values are excluded; means round to six decimal places.',
        'coverage':'This artifact table only; no live ERP records or external accounts were searched.'}
    if not body.get('chart'):return result
    spec=Chart.model_validate(body['chart']);unit_col=validate_columns(spec,columns)
    kind=chart_kind or spec.kind
    if kind=='pie' and spec.series_column is not None:raise ValueError('Pie charts need one series per unit; use a single-series chart configuration')
    grouped=defaultdict(list);unit_values=defaultdict(list);categories={};series={};all_series={}
    for row in rows:
        category=row[spec.category_column].strip()
        if category_query.casefold() not in category.casefold():result['filtered_rows']+=1;continue
        value=Decimal(1) if spec.aggregation=='count' else number(row[spec.value_column])
        if value is None:
            result['blank_numeric_rows' if not row[spec.value_column].strip() else 'invalid_numeric_rows']+=1;continue
        unit=row[unit_col].strip() if unit_col is not None else ''
        label=row[spec.series_column].strip() if spec.series_column is not None else columns[spec.value_column] if spec.value_column is not None else 'Rows'
        key=digest([unit,label]);all_series[key]={'key':key,'label':label or '(blank)','unit':unit}
        if series_key and key!=series_key:result['filtered_rows']+=1;continue
        result['valid_rows']+=1;unit_values[unit].append(value)
        categories.setdefault(unit,{}).setdefault(category,None);series.setdefault(unit,{}).setdefault(key,label)
        grouped[(unit,key,category)].append(value)
    result['available_series']=list(all_series.values())[:64]
    result['omitted_series_choices']=max(0,len(all_series)-64)
    units=list(unit_values);result['omitted_units']=max(0,len(units)-spec.unit_limit)
    for unit in units[:spec.unit_limit]:
        keys=list(series[unit])[:spec.series_limit];labels=list(categories[unit])
        def aggregate(values):
            if not values:return None
            return {'sum':lambda:sum(values,Decimal(0)),'count':lambda:Decimal(len(values)),
                'mean':lambda:sum(values,Decimal(0))/len(values),'min':lambda:min(values),'max':lambda:max(values)}[spec.aggregation]()
        values={(key,label):aggregate(grouped.get((unit,key,label),[])) for key in keys for label in labels}
        if (order or spec.order)=='category':labels.sort(key=str.casefold)
        elif (order or spec.order)=='value_desc':labels.sort(key=lambda label:(values.get((keys[0],label)) is None,-(values.get((keys[0],label)) or Decimal(0))))
        count=min(limit or spec.category_limit,len(labels));selected=labels[:count]
        if kind=='pie' and len(labels)>count:raise ValueError('A pie must include all matching categories. Increase its limit, filter the data or use bars/lines.')
        plotted=[{'key':key,'label':series[unit][key] or '(blank)',
            'values':[formatted(values[(key,label)]) for label in selected],
            'counts':[len(grouped.get((unit,key,label),[])) for label in selected]} for key in keys]
        if kind=='pie' and any(v<0 for v in values.values() if v is not None):raise ValueError('Pie charts require nonnegative aggregates; use bars or lines for negative values')
        result['panels'].append({'unit':unit,'unit_label':columns[unit_col] if unit_col is not None else 'Unit','kind':kind,'aggregation':spec.aggregation,
            'category_label':columns[spec.category_column],'value_label':'Rows' if spec.aggregation=='count' else columns[spec.value_column],
            'categories':[label or '(blank)' for label in selected],'series':plotted,
            'statistics':statistics(unit_values[unit]),'statistics_scope':'All matching valid rows in this unit, before plot limits.',
            'omitted_categories':len(labels)-count,'omitted_series':len(series[unit])-len(keys),
            'rows_plotted':sum(sum(data['counts']) for data in plotted)})
    return result


def bounded(result,cap):
    result['disclosure_limited']=False;result['omitted_profiles']=0
    while len(json.dumps(result,ensure_ascii=False,default=str).encode())>cap:
        result['disclosure_limited']=True
        candidates=[panel for panel in result['panels'] if panel['kind']!='pie' and len(panel['categories'])>1]
        if candidates:
            panel=max(candidates,key=lambda p:len(p['categories']));panel['categories'].pop();panel['omitted_categories']+=1
            for data in panel['series']:
                data['values'].pop();panel['rows_plotted']-=data['counts'].pop()
        elif len(result['panels'])>1:result['panels'].pop();result['omitted_units']+=1
        elif len(result['available_series'])>1:result['available_series'].pop();result['omitted_series_choices']+=1
        elif result['profiles']:result['profiles'].pop();result['omitted_profiles']+=1
        else:raise HTTPException(422,'Analysis exceeds the response budget. Use shorter labels or a smaller table.')
    return result


def summary(body,revision=None):
    result=analyze(body);lines=[f"Computed from {'saved artifact version '+str(revision) if revision else 'the unsaved table draft'}: {result['row_count']} rows.",result['coverage']]
    if not body.get('chart'):
        lines.extend(f"{p['name']}: {p['numeric']} numeric, {p['blank']} blank, {p['nonnumeric']} nonnumeric values." for p in result['profiles'])
        lines.append('Select a chart metric and category to calculate grouped statistics.')
    else:
        for panel in result['panels']:
            stats=panel['statistics'];lines.append(f"{panel['unit'] or 'Unit not specified'} / {panel['value_label']}: count {stats['count']}, sum {stats['sum']}, mean {stats['mean']}, min {stats['min']}, max {stats['max']}.")
        lines.append(f"Excluded numeric values: {result['blank_numeric_rows']} blank, {result['invalid_numeric_rows']} nonnumeric or out of range. Means round to six decimals.")
        if result['omitted_units']:lines.append(f"{result['omitted_units']} additional unit groups are outside the displayed limit.")
    return '\n'.join(lines)[:2000]


def edit(body,operation):
    from copy import deepcopy
    value=deepcopy(body)
    def column(name):
        found=[i for i,label in enumerate(value['columns']) if label.strip().casefold()==name.strip().casefold()]
        if len(found)!=1:raise HTTPException(422,'Choose an exact, unique column name for the chart')
        return found[0]
    if re.fullmatch(r'(?i)(?:remove|disable) (?:the )?chart',operation):value['chart']=None;return value
    match=re.fullmatch(r'(?is)chart (sum|mean|average|min|max) of (.+?) by (.+?)(?: split by (.+))?',operation)
    count=re.fullmatch(r'(?is)chart count by (.+)',operation)
    if match or count:
        value['chart']=Chart(category_column=column(match[3] if match else count[1]),
            value_column=column(match[2]) if match else None,series_column=column(match[4]) if match and match[4] else None,
            aggregation={'average':'mean'}.get(match[1].lower(),match[1].lower()) if match else 'count').model_dump()
        return value
    match=re.fullmatch(r'(?i)(?:set|change) (?:the )?chart(?: type)? (?:to )?(bar|line|pie)',operation)
    if match:
        existing=value.get('chart') or Chart(category_column=0,value_column=1 if len(value['columns'])>1 else None,aggregation='sum' if len(value['columns'])>1 else 'count').model_dump()
        value['chart']=Chart.model_validate({**existing,'kind':match[1].lower()}).model_dump();return value
    import csv
    match=re.fullmatch(r'(?is)(replace|remove) row (\d+)(?:\s*:\s*(.*))?',operation)
    if match:
        index=int(match[2])-1
        if not 0<=index<len(value['rows']):raise HTTPException(422,'Choose an existing table row number')
        if match[1].lower()=='remove' and match[3] is None:del value['rows'][index]
        elif match[1].lower()=='replace' and match[3] is not None:value['rows'][index]=next(csv.reader([match[3].strip()],skipinitialspace=True))
        else:return None
        return value
    return None


def evidence(item):
    return {'id':f'artifact:{item["id"]}:v{item["revision"]}','tool':'suite.artifact','record_id':item['id'],
        'artifact_revision':item['revision'],'label':f'{item["title"]} (artifact version {item["revision"]})',
        'href':f'#bot-artifact-{item["id"]}','coverage':'Saved user/generated artifact snapshot, not verified live ERP facts.'}


def enforce_sources(db,user,run):
    from app.ai_operator import artifacts
    for source in (run.result or {}).get('citations',[]):
        match=re.fullmatch(r'artifact:(\d+):v(\d+)',str(source.get('id','')))
        if match:artifacts.public(db,user,artifacts.owned(db,user,int(match[1])),int(match[2]))

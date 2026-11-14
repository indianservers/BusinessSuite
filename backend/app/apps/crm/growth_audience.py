"""SQL projections for the product/service audience; existing CRM/catalog remain authoritative."""
import json
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import Integer, and_, case, cast, func, literal, or_, select, true, union
from sqlalchemy.dialects.postgresql import JSONB
from app.apps.srm.models import SRMProduct
from app.shared.catalog_models import CatalogDetails, CatalogLink
from .models import CRMDeal, CRMDealContact, CRMDealProduct, CRMLead


def parse_offerings(raw):
    if not raw: return []
    try:
        values=json.loads(raw)
        if not isinstance(values,list) or len(values)>50: raise ValueError()
        result=[]
        for value in values:
            if not isinstance(value,dict) or set(value)!={'kind','id'} or value['kind'] not in ('product','service') or type(value['id']) is not int or not 0<value['id']<=9223372036854775807: raise ValueError()
            pair=(value['kind'],value['id'])
            if pair not in result: result.append(pair)
        return result
    except (ValueError,TypeError,KeyError): raise HTTPException(422,'Select at most 50 valid products/services')


def offering_relations(db,user,scope):
    from . import growth as g
    from app.shared import catalog
    org=g.crm()._organization_id(db,user)
    kinds=[]
    for kind in ('product','service'):
        try: catalog.authorize(user,'crm',kind,db=db); kinds.append(kind)
        except HTTPException as exc:
            if exc.status_code!=403: raise
    product_kind=case((SRMProduct.product_type=='service','service'),else_='product')
    catalog_query=db.query(SRMProduct).filter(func.coalesce(SRMProduct.organization_id,1)==org,SRMProduct.deleted_at.is_(None),product_kind.in_(kinds),catalog.availability_clause(SRMProduct,catalog.selected_branch(user)))
    catalog_query=catalog.restrict_workspaces(catalog_query,SRMProduct,db,user)
    catalog_query=g.crm()._apply_record_visibility(catalog_query,catalog.catalog_resource(),user,db)
    visible=catalog_query.with_entities(SRMProduct.id.label('item_id'),product_kind.label('kind'),SRMProduct.item_name.label('name')).subquery('audience_catalog')
    target=case((CatalogLink.target_type=='lead','leads'),(CatalogLink.target_type=='contact','contacts'),(CatalogLink.target_type.in_(['account','customer']),'companies'),else_='deals')
    direct=select(target.label('entity'),CatalogLink.target_id.label('record_id'),case((CatalogLink.product_id.isnot(None),'product'),else_='service').label('kind'),func.coalesce(CatalogLink.product_id,CatalogLink.service_id).label('item_id')).where(CatalogLink.organization_id==org,CatalogLink.target_type.in_(['lead','contact','account','customer','deal']))
    parts=[direct]
    if g.sales.allowed(user,'deals','view'):
        deals=g.sales.rows(db,user,'deals',scope).with_entities(CRMDeal.id).subquery('audience_visible_deals')
        if db.bind.dialect.name=='postgresql':
            entries=func.jsonb_array_elements(func.coalesce(cast(CRMDeal.catalog_items,JSONB),cast(literal('[]'),JSONB))).table_valued('value').lateral('audience_items')
            kind=entries.c.value.op('->>')('kind'); item_id=cast(entries.c.value.op('->>')('item_id'),Integer)
        else:
            entries=func.json_each(CRMDeal.catalog_items).table_valued('key','value').alias('audience_items')
            kind=func.json_extract(entries.c.value,'$.kind'); item_id=cast(func.json_extract(entries.c.value,'$.item_id'),Integer)
        modern=select(CRMDeal.id.label('deal_id'),kind.label('kind'),item_id.label('item_id')).select_from(CRMDeal).join(entries,true()).where(CRMDeal.id.in_(select(deals.c.id)))
        legacy=select(CRMDealProduct.deal_id,case((SRMProduct.product_type=='service','service'),else_='product').label('kind'),CRMDealProduct.product_id.label('item_id')).join(SRMProduct,SRMProduct.id==CRMDealProduct.product_id).join(CRMDeal,CRMDeal.id==CRMDealProduct.deal_id).where(CRMDeal.id.in_(select(deals.c.id)),CRMDeal.catalog_items.is_(None))
        deal_lines=union(modern,legacy).cte('audience_deal_lines')
        parts.append(select(literal('deals').label('entity'),deal_lines.c.deal_id.label('record_id'),deal_lines.c.kind,deal_lines.c.item_id))
        for entity,field in [('contacts',CRMDeal.contact_id),('companies',CRMDeal.company_id)]:
            parts.append(select(literal(entity).label('entity'),field.label('record_id'),deal_lines.c.kind,deal_lines.c.item_id).join(CRMDeal,CRMDeal.id==deal_lines.c.deal_id).where(field.isnot(None)))
        parts.append(select(literal('contacts').label('entity'),CRMDealContact.contact_id.label('record_id'),deal_lines.c.kind,deal_lines.c.item_id).join(CRMDealContact,CRMDealContact.deal_id==deal_lines.c.deal_id).where(CRMDealContact.organization_id==org))
        parts.append(select(literal('leads').label('entity'),CRMLead.id.label('record_id'),deal_lines.c.kind,deal_lines.c.item_id).join(CRMLead,CRMLead.converted_deal_id==deal_lines.c.deal_id).where(CRMLead.organization_id==org))
    raw=union(*parts).subquery('audience_relationship_links') if len(parts)>1 else direct.subquery('audience_relationship_links')
    return select(raw.c.entity,raw.c.record_id,raw.c.kind,raw.c.item_id,visible.c.name).join(visible,and_(visible.c.item_id==raw.c.item_id,visible.c.kind==raw.c.kind)).distinct().cte('audience_offerings')


def apply_audience(q,model,entity,relations,offerings,match,search='',workspace_id=None):
    common=[relations.c.entity==entity,relations.c.record_id==model.id]
    tests=[select(1).select_from(relations).where(*common,relations.c.kind==kind,relations.c.item_id==ident).correlate(model).exists() for kind,ident in offerings]
    if tests: q=q.filter(and_(*tests) if match=='all' else or_(*tests))
    if search:
        normal=[getattr(model,key).icontains(search, autoescape=True) for key in ('full_name','name','email','phone','company_name') if hasattr(model,key)]
        product=select(1).select_from(relations).where(*common,relations.c.name.icontains(search, autoescape=True)).correlate(model).exists()
        q=q.filter(or_(*normal,product))
    if workspace_id:
        ids=select(func.coalesce(CatalogDetails.product_id,CatalogDetails.service_id)).where(CatalogDetails.workspace_id==workspace_id)
        q=q.filter(select(1).select_from(relations).where(*common,relations.c.item_id.in_(ids)).correlate(model).exists())
    return q


def enrich(db,items,relations):
    if not items:return
    wanted=or_(*(and_(relations.c.entity==entity,relations.c.record_id.in_([row['id'] for row in items if row['entity']==entity])) for entity in {r['entity'] for r in items}))
    found={}
    for row in db.execute(select(relations).where(wanted)).mappings():
        found.setdefault((row['entity'],row['record_id']),[]).append({'kind':row['kind'],'id':row['item_id'],'name':row['name']})
    for item in items: item['offerings']=found.get((item['entity'],item['id']),[])


def analytics(db,selection,relations,days,interval):
    s=selection.c
    counts={row.entity:row.n for row in db.execute(select(s.entity,func.count().label('n')).group_by(s.entity))}
    converted=db.scalar(select(func.count()).select_from(selection).where(s.entity=='leads',s.converted==1)) or 0
    leads=counts.get('leads',0)
    customers=db.scalar(select(func.count()).select_from(selection).where(s.customer==1)) or 0
    customers_companies=db.scalar(select(func.count()).select_from(selection).where(or_(s.entity=='companies',s.customer==1))) or 0
    active=db.scalar(select(func.count()).select_from(selection).where(s.entity=='deals',func.lower(func.coalesce(s.status,'' )).notin_(['won','lost','closed','cancelled']))) or 0
    currencies=[{'currency':row.currency,'value':str(row.amount or 0)} for row in db.execute(select(s.currency,func.sum(s.amount).label('amount')).where(s.entity=='deals',func.lower(func.coalesce(s.status,'')).notin_(['won','lost','closed','cancelled'])).group_by(s.currency))]
    joined=select(s.entity,s.id,s.amount,s.currency,s.status,s.customer,s.converted,relations.c.kind,relations.c.item_id,relations.c.name).join(relations,and_(s.entity==relations.c.entity,s.id==relations.c.record_id)).distinct().subquery('audience_top')
    t=joined.c
    top=[]
    for row in db.execute(select(t.kind,t.item_id,t.name,func.count().label('relationships'),func.sum(case((t.entity=='leads',1),else_=0)).label('leads'),func.sum(t.customer).label('customers'),func.sum(case((t.entity=='deals',1),else_=0)).label('deals'),func.sum(case((t.entity=='leads',t.converted),else_=0)).label('converted')).group_by(t.kind,t.item_id,t.name).order_by(func.count().desc(),t.name).limit(6)):
        values=[{'currency':v.currency,'value':str(v.amount or 0)} for v in db.execute(select(t.currency,func.sum(t.amount).label('amount')).where(t.kind==row.kind,t.item_id==row.item_id,t.entity=='deals',func.lower(func.coalesce(t.status,'')).notin_(['won','lost','closed','cancelled'])).group_by(t.currency))]
        top.append({'kind':row.kind,'id':row.item_id,'name':row.name,'relationships':row.relationships,'leads':row.leads or 0,'customers':row.customers or 0,'deals':row.deals or 0,'pipeline_values':values,'conversion_rate':round(100*row.converted/row.leads,1) if row.leads else None})
    start=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=days-1)
    end=start+timedelta(days=days)
    events={}
    def bucket(day):
        if interval=='weekly':day=day-timedelta(days=day.weekday())
        elif interval=='monthly':day=day.replace(day=1)
        return day.isoformat()
    for i in range(days): events.setdefault(bucket((start+timedelta(days=i)).date()),{'leads':0,'converted':0,'closed':0})
    for name,field,condition in [('leads',s.created_at,s.entity=='leads'),('converted',s.converted_at,s.entity=='leads'),('closed',s.closed_at,s.entity=='deals')]:
        day_field=func.date(func.timezone('UTC',field)) if db.bind.dialect.name=='postgresql' else func.date(field)
        for row in db.execute(select(day_field.label('day'),func.count().label('n')).where(condition,field>=start,field<end).group_by(day_field)):
            day=datetime.fromisoformat(str(row.day)).date();events[bucket(day)][name]+=row.n
    unassigned=db.scalar(select(func.count()).select_from(selection).where(~select(1).select_from(relations).where(relations.c.entity==s.entity,relations.c.record_id==s.id).exists())) or 0
    return {'counts':counts,'customers':customers,'customers_companies':customers_companies,'active_deals':active,'converted_leads':converted,'conversion_rate':round(converted*100/leads,1) if leads else None,'conversion_denominator':leads,'pipeline_values':currencies,'top_offerings':top,'unassigned':unassigned,'trends':[{'date':key,**value} for key,value in events.items()],'trend_timezone':'UTC'}

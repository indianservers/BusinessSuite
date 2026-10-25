"""Inventory concrete form definitions, schemas, models and contact consumers."""
import ast,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
phones={'phone','phone_number','mobile','mobile_number','alternate_phone','whatsapp_number','contact_phone','contact_number','emergency_contact_number','business_phone_number','primary_phone','secondary_phone'}
models=[];schemas=[];forms=[];consumers=[]
for path in (ROOT/'backend/app').rglob('*.py'):
    try:tree=ast.parse(path.read_text(encoding='utf-8-sig'))
    except (SyntaxError,UnicodeError):continue
    for node in ast.walk(tree):
        if isinstance(node,ast.ClassDef):
            fields=[];table=None
            for statement in node.body:
                if isinstance(statement,ast.Assign) and len(statement.targets)==1 and isinstance(statement.targets[0],ast.Name):
                    key=statement.targets[0].id
                    if key=='__tablename__' and isinstance(statement.value,ast.Constant):table=statement.value.value
                    if key in phones and isinstance(statement.value,ast.Call) and isinstance(statement.value.func,ast.Name) and statement.value.func.id=='Column':fields.append(key)
                if isinstance(statement,ast.AnnAssign) and isinstance(statement.target,ast.Name) and statement.target.id in phones:
                    schemas.append({'file':path.relative_to(ROOT).as_posix(),'class':node.name,'field':statement.target.id,'line':statement.lineno})
            if table and fields:models.append({'file':path.relative_to(ROOT).as_posix(),'class':node.name,'table':table,'phones':fields})
    text=path.read_text(encoding='utf-8-sig')
    if any(term in text.lower() for term in ('whatsapp','sms','export','import')) and re.search(r'phone|mobile',text):consumers.append(path.relative_to(ROOT).as_posix())
for root in ('frontend/src','frontend/interns-hub/src'):
    for path in (ROOT/root).rglob('*.tsx'):
        text=path.read_text(encoding='utf-8',errors='replace')
        if re.search(r'<form\b|useForm[<(]|<Dialog|<FormModal|<Input\b|<input\b|<textarea\b|<select\b',text):
            forms.append({'file':path.relative_to(ROOT).as_posix(),'phone_related':bool(re.search(r'phone|mobile|emergency_contact',text,re.I)),'email_related':bool(re.search('email',text,re.I)),'verification':'Inventoried; runtime verification tracked separately'})
target=ROOT/'docs/qa/validation';target.mkdir(parents=True,exist_ok=True)
(target/'inventory.json').write_text(json.dumps({'models':models,'schemas':schemas,'forms':forms,'contact_consumers':consumers},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'phone_models':len(models),'phone_columns':sum(len(row['phones']) for row in models),'schema_phone_fields':len(schemas),'form_files':len(forms),'phone_form_files':sum(row['phone_related'] for row in forms),'contact_consumer_files':len(consumers)}))

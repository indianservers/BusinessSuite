"""Version-pinned private dashboard references over existing artifact storage."""
import io
import math
import re
from copy import deepcopy
from typing import Literal
from fastapi import HTTPException
from pydantic import Field,StrictInt,model_validator
from app.ai_operator.suite_tools import Strict


class Panel(Strict):
    artifact_id:StrictInt=Field(gt=0)
    revision:StrictInt=Field(ge=1,le=100)
    display:Literal['auto','chart','table','summary']='auto'
    label:str=Field(default='',max_length=100)
    wide:bool=False

    @model_validator(mode='after')
    def valid(self):
        if re.search(r'[\x00-\x1f\ud800-\udfff\ufffe\uffff]',self.label):raise ValueError('Panel label contains unsupported characters')
        return self


def resolve(db,user,workspace_id,panel,export=False):
    from app.ai_operator import artifacts
    # A typed plan can omit optional panel defaults. Use the same canonical
    # shape for preflight and saved-version reads instead of indexing raw input.
    try:panel=Panel.model_validate(panel).model_dump()
    except ValueError:raise HTTPException(422,'Choose a valid pinned dashboard panel') from None
    item=artifacts.public(db,user,artifacts.owned(db,user,panel['artifact_id']),panel['revision'])
    if item['workspace_id']!=workspace_id:raise HTTPException(403,'Dashboard sources must belong to its workspace')
    if item['kind']=='dashboard':raise HTTPException(422,'Choose a document, checklist, table or presentation; dashboards cannot contain other dashboards')
    if panel['display'] in ('chart','table') and item['kind']!='table':raise HTTPException(422,'Chart and table panels require a table artifact')
    if panel['display']=='chart' and not item.get('chart'):raise HTTPException(422,'Save a chart configuration on the source table first')
    if export:
        from app.access.service import check_background_access
        from app.ai_operator.suite import MODULES
        check_background_access(db,user,MODULES[item['module']],'export')
    return item


def validate(db,user,workspace_id,body):
    if body.get('kind')=='dashboard':
        for panel in body['panels']:resolve(db,user,workspace_id,panel)


def edit(body,operation):
    """Small explicit local edit grammar; all source revisions must be supplied."""
    result=deepcopy(body)
    add=re.fullmatch(r'(?is)add panel(?:\s*:\s*|\s+)(?:artifact\s*)?#?(\d+)\s+(?:v|version\s*)(\d+)(?:\s+as\s+(chart|table|summary|auto))?',operation)
    remove=re.fullmatch(r'(?i)remove panel\s+(\d+)',operation)
    move=re.fullmatch(r'(?i)move panel\s+(\d+)\s+to\s+(\d+)',operation)
    refresh=re.fullmatch(r'(?i)(?:refresh|update) panel\s+(\d+)\s+to\s+(?:v|version\s*)(\d+)',operation)
    label=re.fullmatch(r'(?is)rename panel\s+(\d+)\s+to\s+(.+)',operation)
    layout=re.fullmatch(r'(?i)make panel\s+(\d+)\s+(wide|compact)',operation)
    if add:result['panels'].append(Panel(artifact_id=int(add[1]),revision=int(add[2]),display=add[3] or 'auto').model_dump())
    elif remove or move or refresh or label or layout:
        match=remove or move or refresh or label or layout;index=int(match[1])-1
        if not 0<=index<len(result['panels']):raise ValueError('Select a panel number in this dashboard')
        if remove:result['panels'].pop(index)
        elif move:
            target=int(move[2])-1
            if not 0<=target<len(result['panels']):raise ValueError('Select a destination panel number in this dashboard')
            result['panels'].insert(target,result['panels'].pop(index))
        elif refresh:result['panels'][index]['revision']=int(refresh[2])
        elif label:result['panels'][index]['label']=label[2].strip()
        elif layout:result['panels'][index]['wide']=layout[2].lower()=='wide'
    else:return None
    return result


def text(item,sources):
    parts=['# '+item['title'],item['content'],'Version-pinned artifact snapshots. Interactive filters do not change this export.']
    for panel,source in zip(item['panels'],sources):
        parts.extend(['## '+(panel['label'] or source['title']),f"Source artifact #{source['id']} / {source['module']} / version {source['revision']}",source['content']])
        if source['kind']=='table':
            parts.extend(' | '.join(v.replace('|','\\|').replace('\n',' ') for v in row) for row in [source['columns'],*source['rows']])
            if source.get('chart'):
                from app.ai_operator.artifact_charts import summary
                parts.append(summary(source,source['revision']))
        elif source['kind']=='presentation':
            parts.extend(slide['title']+'\n'+'\n'.join('- '+p for p in slide['bullets']) for slide in source['slides'])
    return '\n\n'.join(p for p in parts if p)


def image_media(sources,media):
    """Require every exact source's pixels; never silently export a caption alone."""
    from app.ai_operator.artifact_images import validate
    result={}
    for position,source in enumerate(sources,1):
        if source['kind']=='image':result[position]=validate((media or {}).get(position),source.get('image'))
    unique={sources[position-1]['image']['sha256']:value for position,value in result.items()}
    if sum(map(len,unique.values()))>8_000_000:raise HTTPException(413,'Dashboard image export exceeds 8 MB; split its panels')
    manifests={s['image']['sha256']:s['image'] for s in sources if s['kind']=='image'}
    if sum(v['width']*v['height'] for v in manifests.values())>24_000_000:raise HTTPException(413,'Dashboard image export exceeds its pixel budget; split its panels')
    return result


def export_pdf(item,sources,media=None):
    from pypdf import PdfReader,PdfWriter
    from app.ai_operator.artifact_exports import pdf,MAX_PAGES
    cover={**item,'kind':'document','content':item['content']+'\n\nVersion-pinned snapshots. Interactive filters are not applied to exports.\n\n'+'\n'.join(
        f"{i}. {panel['label'] or source['title']} — {source['module']} / artifact #{source['id']} / version {source['revision']}"
        for i,(panel,source) in enumerate(zip(item['panels'],sources),1))}
    writer=PdfWriter()
    for position,source in enumerate([cover,*sources]):
        reader=PdfReader(io.BytesIO(pdf(source,media_content=(media or {}).get(position))))
        if len(writer.pages)+len(reader.pages)>MAX_PAGES:raise HTTPException(422,'Dashboard exceeds 100 pages; split it into smaller dashboards')
        writer.append(reader)
    stream=io.BytesIO();writer.write(stream);return stream.getvalue()


def export_excel(item,sources,media=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment,Font,PatternFill
    from app.ai_operator.artifact_chart_exports import excel
    book=Workbook();index=book.active;index.title='Dashboard'
    def literal(sheet,row,col,value):
        cell=sheet.cell(row,col,str(value));cell.data_type='s';cell.alignment=Alignment(wrap_text=True,vertical='top')
    literal(index,1,1,item['title']);index['A1'].font=Font(size=17,bold=True,color='15243B')
    index.merge_cells('A1:D1');index.row_dimensions[1].height=45
    introduction=item['content'][:300]+(' (Full introduction on Dashboard notes.)' if len(item['content'])>300 else '')
    literal(index,2,1,introduction);index.merge_cells('A2:D2');index.row_dimensions[2].height=75
    literal(index,3,1,'Pinned snapshots. Interactive filters do not change exports. Each source and chart uses its saved version.')
    index.merge_cells('A3:D3');index.row_dimensions[3].height=45
    for col,value in enumerate(('Panel','Source','Module','Version'),1):literal(index,5,col,value)
    for position,(panel,source) in enumerate(zip(item['panels'],sources),1):
        sheet=book.create_sheet(f'Source {position}')
        for col,value in enumerate((panel['label'] or source['title'],f"Artifact #{source['id']}",source['module'],source['revision']),1):literal(index,position+5,col,value)
        chunks=[source['content'][i:i+800] for i in range(0,len(source['content']),800)] or ['']
        rows=[['Title',source['title']],['Source',f"Artifact #{source['id']} / {source['module']} / version {source['revision']}"],
            *[['Content' if i==0 else 'Content continued',chunk] for i,chunk in enumerate(chunks)]]
        header=len(rows)+1
        if source['kind']=='table':rows.extend([source['columns'],*source['rows']])
        elif source['kind']=='presentation':rows.extend([[s['title'],*s['bullets']] for s in source['slides']])
        for r,values in enumerate(rows,1):
            for col,value in enumerate(values,1):literal(sheet,r,col,value)
            sheet.row_dimensions[r].height=min(400,max(32,max((math.ceil(len(str(value))/30)+str(value).count('\n'))*15 for value in values)))
        for col in range(1,max(len(v) for v in rows)+1):sheet.column_dimensions[__import__('openpyxl').utils.get_column_letter(col)].width=32
        sheet.freeze_panes=f'A{header+1}';sheet.sheet_view.showGridLines=False
        if source['kind']=='table' and source.get('chart'):excel(book,source,sheet.title)
        if source['kind']=='image':
            from openpyxl.drawing.image import Image
            picture=Image(io.BytesIO((media or {})[position]));scale=min(640/picture.width,480/picture.height,1)
            picture.width*=scale;picture.height*=scale;sheet.add_image(picture,f'A{len(rows)+2}')
    for cell in index[5]:cell.fill=PatternFill('solid',fgColor='15243B');cell.font=Font(color='FFFFFF',bold=True)
    for col,width in (('A',44),('B',24),('C',16),('D',12)):index.column_dimensions[col].width=width
    for row in range(6,len(sources)+6):index.row_dimensions[row].height=60
    if len(item['content'])>300:
        notes=book.create_sheet('Dashboard notes');notes.column_dimensions['A'].width=96
        for row,start in enumerate(range(0,len(item['content']),800),1):
            literal(notes,row,1,item['content'][start:start+800]);notes.row_dimensions[row].height=180
    for sheet in book.worksheets:
        sheet.sheet_properties.pageSetUpPr.fitToPage=True
        sheet.page_setup.fitToWidth=1;sheet.page_setup.fitToHeight=0
        if not sheet.title.startswith('Chart analysis'):
            sheet.page_setup.orientation='landscape';sheet.page_setup.paperSize=sheet.PAPERSIZE_A4
    index.sheet_view.showGridLines=False;index.freeze_panes='A6'
    book.active=book.sheetnames.index('Dashboard')
    stream=io.BytesIO();book.save(stream);return stream.getvalue()


def word(document,item,sources,media=None):
    from docx.shared import Inches
    if item['content']:document.add_paragraph(item['content'])
    document.add_paragraph('Version-pinned snapshots. Interactive filters are not applied to exports.')
    for position,(panel,source) in enumerate(zip(item['panels'],sources),1):
        document.add_heading(panel['label'] or source['title'],1)
        document.add_paragraph(f"Source artifact #{source['id']} / {source['module']} / version {source['revision']}")
        if source['content']:document.add_paragraph(source['content'])
        if source['kind']=='image':
            image=source['image'];scale=min(6/image['width'],6/image['height'])
            document.add_picture(io.BytesIO((media or {})[position]),width=Inches(image['width']*scale),height=Inches(image['height']*scale))
        elif source['kind']=='table':
            table=document.add_table(rows=1,cols=len(source['columns']));table.style='Table Grid'
            for cell,value in zip(table.rows[0].cells,source['columns']):cell.text=value
            for row in source['rows']:
                for cell,value in zip(table.add_row().cells,row):cell.text=value
            if source.get('chart'):
                from app.ai_operator.artifact_charts import summary
                document.add_paragraph(summary(source,source['revision']))
        elif source['kind']=='presentation':
            for slide in source['slides']:
                document.add_heading(slide['title'],2)
                for point in slide['bullets']:document.add_paragraph(point,style='List Bullet')

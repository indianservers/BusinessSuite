"""Whole filtered report exports with metadata, currency totals and safe cells."""
from __future__ import annotations
import csv
import hashlib
import io
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from fastapi import HTTPException
from . import reporting

MAX_ROWS=10000
MONEY_COLUMNS=frozenset({'gross','discount','discounts','tax','total','paid','balance','amount','allocated','unallocated',
    'invoiced','invoice_paid','outstanding','returns','net_billed','collections','refund','value','stock_value',
    'billed_ex_tax','recorded_issue_cost','gross_profit','gross_margin','cash_margin','confirmed_allocations',
    'allocation_difference','balance_difference','delivery_cost'})


def collect(db,user,report,filters,columns=None):
    first=reporting.run(db,user,report,filters,1,200)
    if first['total']>MAX_ROWS:
        raise HTTPException(422,f'This export contains {first["total"]:,} rows. Narrow the date range or filters to {MAX_ROWS:,} rows or fewer; no records were truncated.')
    rows=list(first['items'])
    for page in range(2,(first['total']+199)//200+1):
        rows.extend(reporting.run(db,user,report,filters,page,200)['items'])
    if len(rows)!=first['total']:
        raise HTTPException(409,'Report changed while exporting. Prepare a fresh export.')
    selected=columns or first['columns']
    if not selected or len(set(selected))!=len(selected) or any(name not in first['columns'] for name in selected):
        raise HTTPException(422,'Choose visible report columns')
    totals={}
    for row in rows:
        currency=str(row.get('currency') or 'UNKNOWN')
        subtotal=totals.setdefault(currency,{})
        for column in selected:
            if column in MONEY_COLUMNS and row.get(column) is not None:
                subtotal[column]=subtotal.get(column,Decimal(0))+Decimal(str(row[column]))
    return {**first,'items':rows,'columns':selected,'currency_totals':{key:{k:reporting.money(v) for k,v in values.items()} for key,values in totals.items()}}


def fingerprint(data):
    # Exclude volatile timestamps. A download must still match today's authorized
    # rows, not merely the permissions that existed when the job was queued.
    value={key:data[key] for key in ('report','filters','columns','items','currency_totals')}
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()


def display(value):
    if value is None:return ''
    if isinstance(value,bool):return 'Yes' if value else 'No'
    if isinstance(value,(date,datetime)):return value.isoformat()
    if isinstance(value,(list,dict)):return json.dumps(value,ensure_ascii=False,default=str)
    return str(value)


def safe_text(value):
    text=display(value)
    return "'"+text if text.lstrip().startswith(('=','+','-','@','\t','\r')) else text


def label(name):return name.replace('_',' ').title()


def metadata(data):
    return [('Report',data['title']),('Company',str(data['context']['organization_id'])),
        ('From',data['filters']['start']),('To',data['filters']['end']),
        ('Timezone',data['context']['timezone']),('Generated at',data['context']['as_of']),
        ('Include test data','Yes' if data['filters']['include_test'] else 'No'),
        ('Filters',json.dumps(data['filters'],sort_keys=True,default=str)),
        ('Currency policy',data['definitions']['currency']),('Date basis',data['definitions']['dates']),
        ('Document filters',data['definitions']['document_filters']),('Rows',str(len(data['items'])))]


def render_csv(data):
    stream=io.StringIO(newline='');writer=csv.writer(stream)
    for key,value in metadata(data):writer.writerow([key,safe_text(value)])
    writer.writerow([]);writer.writerow([label(k) for k in data['columns']])
    for row in data['items']:
        writer.writerow([display(row.get(k)) if k in MONEY_COLUMNS else safe_text(row.get(k)) for k in data['columns']])
    writer.writerow([]);writer.writerow(['Totals by currency — no currency conversion'])
    for currency,values in sorted(data['currency_totals'].items()):
        for key,value in values.items():writer.writerow([safe_text(currency),label(key),value])
    return stream.getvalue().encode('utf-8-sig')


def render_xlsx(data):
    # Runtime server export: reuse the application's existing openpyxl dependency.
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    workbook=Workbook(write_only=True)
    sheet=workbook.create_sheet('Report');sheet.freeze_panes='A2'
    for index,column in enumerate(data['columns'],1):sheet.column_dimensions[get_column_letter(index)].width=24 if column not in MONEY_COLUMNS else 18
    header=[]
    for column in data['columns']:
        cell=WriteOnlyCell(sheet,value=label(column));cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='5B36B4');cell.alignment=Alignment(wrap_text=True);header.append(cell)
    sheet.append(header)
    for row in data['items']:
        cells=[]
        for column in data['columns']:
            value=row.get(column)
            cell=WriteOnlyCell(sheet)
            if column in MONEY_COLUMNS and value is not None:
                cell.value=float(Decimal(str(value)));cell.number_format='#,##0.00;[Red](#,##0.00)'
            elif isinstance(value,(int,float,bool)):cell.value=value
            else:cell.value=display(value);cell.data_type='s'
            cell.alignment=Alignment(vertical='top',wrap_text=True);cells.append(cell)
        sheet.append(cells)
    sheet.auto_filter.ref=f'A1:{get_column_letter(len(data["columns"]))}{len(data["items"])+1}'
    info=workbook.create_sheet('Report context');info.column_dimensions['A'].width=24;info.column_dimensions['B'].width=100
    for key,value in metadata(data):
        cells=[WriteOnlyCell(info,value=key),WriteOnlyCell(info,value=display(value))]
        cells[1].data_type='s';cells[1].alignment=Alignment(wrap_text=True);info.append(cells)
    totals=workbook.create_sheet('Currency totals');totals.append(['Currency','Metric','Amount'])
    for currency,values in sorted(data['currency_totals'].items()):
        for key,value in values.items():
            code=WriteOnlyCell(totals,value=currency);code.data_type='s'
            totals.append([code,label(key),float(Decimal(value))])
    output=io.BytesIO();workbook.save(output);return output.getvalue()


def render_pdf(data):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4,landscape
    from reportlab.lib.utils import simpleSplit
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    font='Helvetica'
    for path in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','C:/Windows/Fonts/arial.ttf'):
        if Path(path).is_file():
            if 'SuiteReport' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('SuiteReport',path))
            font='SuiteReport';break
    output=io.BytesIO();pdf=canvas.Canvas(output,pagesize=landscape(A4));width,height=landscape(A4)
    columns=data['columns'];panels=[columns[i:i+6] for i in range(0,len(columns),6)]
    page_number=0;y=0
    def new_page(panel):
        nonlocal y,page_number
        if page_number:pdf.showPage()
        page_number+=1;pdf.setFont(font,14);pdf.drawString(28,height-30,data['title'])
        pdf.setFont(font,8);pdf.drawString(28,height-47,f'Company {data["context"]["organization_id"]} | {data["filters"]["start"]} to {data["filters"]["end"]} | {data["context"]["timezone"]} | Test data: {"included" if data["filters"]["include_test"] else "excluded"}')
        pdf.drawString(28,height-60,'Document filters select complete documents. Currency totals are separate. All selected columns continue in numbered sections.')
        pdf.drawString(28,18,f'Generated {data["context"]["as_of"]} | Page {page_number}')
        y=height-80;cell_width=(width-56)/len(panel)
        pdf.setFillColorRGB(.93,.91,.98);pdf.rect(28,y-22,width-56,24,fill=1,stroke=0);pdf.setFillColorRGB(.12,.10,.20);pdf.setFont(font,8)
        for i,key in enumerate(panel):pdf.drawString(32+i*cell_width,y-12,label(key))
        y-=30
    for index,panel in enumerate(panels):
        # Repeat the document/item identity alongside subsequent column panels.
        if index and columns[0] not in panel:panel=[columns[0],*panel]
        new_page(panel);cell_width=(width-56)/len(panel)
        for row in data['items']:
            lines=[simpleSplit(display(row.get(key)),font,8,cell_width-10) or [''] for key in panel]
            remaining=max(len(part) for part in lines)
            offset=0
            while remaining:
                available=int((y-52)//11)
                if available<1:new_page(panel);available=int((y-52)//11)
                count=min(remaining,available);pdf.setFont(font,8)
                for i,part in enumerate(lines):
                    for index,text in enumerate(part[offset:offset+count]):pdf.drawString(32+i*cell_width,y-10-index*11,text)
                y-=count*11+10;offset+=count;remaining-=count
                if remaining:new_page(panel)
            pdf.setStrokeColorRGB(.88,.88,.91);pdf.line(28,y,width-28,y)
    new_page(['currency','metric','amount'])
    for currency,values in sorted(data['currency_totals'].items()):
        for key,value in values.items():
            if y<55:new_page(['currency','metric','amount'])
            pdf.setFont(font,8);pdf.drawString(32,y-10,currency);pdf.drawString(width/3,y-10,label(key));pdf.drawRightString(width-40,y-10,value);y-=19
    new_page(['Report context'])
    for key,value in metadata(data):
        for text in simpleSplit(f'{key}: {display(value)}',font,8,width-66):
            if y<55:new_page(['Report context (continued)'])
            pdf.setFont(font,8);pdf.drawString(32,y-10,text);y-=13
        y-=5
    pdf.save();return output.getvalue()


def render(data,format):
    if format=='csv':return render_csv(data)
    if format=='xlsx':return render_xlsx(data)
    if format=='pdf':return render_pdf(data)
    raise HTTPException(422,'Choose CSV, Excel or PDF')

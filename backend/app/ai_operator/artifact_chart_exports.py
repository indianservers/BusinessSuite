"""Native PDF drawings and Excel charts from the shared server analysis."""
import math
from decimal import Decimal
from app.ai_operator.artifact_charts import analyze

COLORS=['#176b87','#e58b35','#7a56a3','#2e8463','#bf5368','#596d91','#9b7d33','#587e91']


def drawing(panel,width,height=265):
    from reportlab.graphics.shapes import Drawing,Rect,Line,Circle,String,Wedge
    from reportlab.lib.colors import HexColor
    from app.ai_operator.artifact_exports import fonts
    normal,bold=fonts();result=Drawing(width,height);data=panel['series'];labels=panel['categories']
    def text(x,y,value,size=8,color='#344155',**options):result.add(String(x,y,value,fontName=normal,fontSize=size,fillColor=HexColor(color),**options))
    if not labels or not data:text(30,120,'No matching numeric data.');return result
    if panel['kind']=='pie':
        values=data[0]['values'];total=sum(float(v) for v in values if v is not None)
        if not total:text(30,120,'All displayed values are zero.');return result
        angle=0
        for i,(label,value) in enumerate(zip(labels,values)):
            if value is None:continue
            end=angle+360*float(value)/total
            if end>angle:result.add(Wedge(width*.26,height*.52,min(height*.37,width*.22),angle,end,fillColor=HexColor(COLORS[i%len(COLORS)]),strokeColor=HexColor('#ffffff'),strokeWidth=1))
            angle=end
            if i<12:
                result.add(Rect(width*.53,height-30-i*17,8,8,fillColor=HexColor(COLORS[i%len(COLORS)]),strokeWidth=0))
                text(width*.53+14,height-29-i*17,f'{label[:28]}: {value}')
        if len(labels)>12:text(width*.53,25,'Complete categories and values follow below.')
        return result
    left,right,bottom,top=48,width-14,66,height-24
    numbers=[float(v) for series in data for v in series['values'] if v is not None]
    low=min([0,*numbers]);high=max([0,*numbers]);high=high if high>low else low+1
    def y(value):return bottom+(float(value)-low)/(high-low)*(top-bottom)
    for i in range(5):
        tick=low+(high-low)*i/4;level=y(tick)
        result.add(Line(left,level,right,level,strokeColor=HexColor('#d9e0e8'),strokeWidth=.5))
        text(left-5,level-3,f'{tick:.4g}',textAnchor='end')
    result.add(Line(left,y(0),right,y(0),strokeColor=HexColor('#64748b'),strokeWidth=.8))
    step=(right-left)/max(1,len(labels))
    for i,label in enumerate(labels):
        x=left+step*(i+.5)
        if i%max(1,math.ceil(len(labels)/12))==0:text(x,bottom-12,label[:18],7,angle=40,textAnchor='end')
    for s,series in enumerate(data):
        color=HexColor(COLORS[s%len(COLORS)]);previous=None
        for i,value in enumerate(series['values']):
            if value is None:previous=None;continue
            x=left+step*(i+.5);level=y(value)
            if panel['kind']=='bar':
                bar=step*.76/max(1,len(data));bx=left+step*i+step*.12+bar*s
                result.add(Rect(bx,min(y(0),level),max(.5,bar-1),abs(level-y(0)),fillColor=color,strokeWidth=0))
            else:
                if previous:result.add(Line(previous[0],previous[1],x,level,strokeColor=color,strokeWidth=1.5))
                result.add(Circle(x,level,2,fillColor=color,strokeWidth=0));previous=(x,level)
        text(left+s*(width-left)/max(1,len(data)),height-10,f'{s+1}. {series["label"][:22]}',8,COLORS[s%len(COLORS)])
    return result


def pdf_flowables(item,width,paragraph,cell,head):
    from reportlab.platypus import Spacer,LongTable,TableStyle
    from reportlab.lib import colors
    result=analyze(item);story=[]
    story.append(paragraph(f"Chart analysis: {result['valid_rows']} valid rows; {result['blank_numeric_rows']} blank and {result['invalid_numeric_rows']} nonnumeric/out-of-range metric values excluded."))
    story.append(paragraph('Computed from this table snapshot. Units/currencies remain separate. Means round to six decimals.'))
    for panel in result['panels']:
        stats=panel['statistics']
        story.append(paragraph(f"{panel['unit'] or 'Unit not specified'} / {panel['aggregation']} of {panel['value_label']} by {panel['category_label']}"))
        story.append(drawing(panel,width))
        story.append(paragraph(f"All matching valid rows in this unit: count {stats['count']}; sum {stats['sum']}; mean {stats['mean']}; minimum {stats['min']}; maximum {stats['max']}."))
        if panel['omitted_categories'] or panel['omitted_series']:story.append(paragraph(f"Plot limits omit {panel['omitted_categories']} categories and {panel['omitted_series']} series. Statistics include all matching valid rows in this unit."))
        rows=[[panel['category_label'],*[s['label'] for s in panel['series']]],
            *[[label,*[s['values'][i] if s['values'][i] is not None else 'No data' for s in panel['series']]] for i,label in enumerate(panel['categories'])]]
        table=LongTable([[paragraph(v,head if n==0 else cell) for v in row] for n,row in enumerate(rows)],repeatRows=1,
            colWidths=[width/len(rows[0])]*len(rows[0]),splitInRow=1)
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#15243b')),('VALIGN',(0,0),(-1,-1),'TOP'),
            ('GRID',(0,0),(-1,-1),.4,colors.HexColor('#ccd3de')),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        story.extend([table,Spacer(1,15)])
    if result['omitted_units']:story.append(paragraph(f"{result['omitted_units']} additional unit groups are outside the configured plot limit."))
    story.append(paragraph('Original table snapshot'))
    return story


def excel(book,item):
    from openpyxl.chart import BarChart,LineChart,PieChart,Reference
    from openpyxl.styles import Font,PatternFill,Alignment
    result=analyze(item);sheet=book.create_sheet('Chart analysis',0);sheet.sheet_view.showGridLines=False
    visible_columns=max([7,*[len(panel['series'])+1 for panel in result['panels']]])
    def text(row,col,value):
        cell=sheet.cell(row,col,str(value));cell.data_type='s';cell.alignment=Alignment(wrap_text=True,vertical='top');return cell
    def caption(row,value,height=32):
        text(row,1,value);sheet.merge_cells(start_row=row,start_column=1,end_row=row,end_column=visible_columns);sheet.row_dimensions[row].height=height
    text(1,1,item['title']);sheet['A1'].font=Font(size=17,bold=True,color='15243B')
    caption(2,'Computed snapshot. Separate units; means round to 6 decimals. Original values remain literal text on Artifact.')
    caption(3,f"Excluded metric values: {result['blank_numeric_rows']} blank, {result['invalid_numeric_rows']} nonnumeric/out of range.")
    row=5
    for panel in result['panels']:
        caption(row,f"{panel['unit'] or 'Unit not specified'} / {panel['aggregation']} of {panel['value_label']}",50);sheet.cell(row,1).font=Font(bold=True,color='15243B')
        stats=panel['statistics'];caption(row+1,f"All valid rows: {stats['count']}; sum {stats['sum']}; mean {stats['mean']}; min {stats['min']}; max {stats['max']}")
        caption(row+2,f"Plot omissions: {panel['omitted_categories']} categories, {panel['omitted_series']} series. Blank cells mean no data.")
        header=row+4;start=header+1;series=panel['series'];count=len(series)
        text(header,1,panel['category_label'])
        for j,values in enumerate(series,2):text(header,j,values['label'])
        for i,label in enumerate(panel['categories'],start):
            text(i,1,label)
            sheet.row_dimensions[i].height=min(400,max(20,math.ceil(len(label)/22)*14))
            for j,values in enumerate(series,2):
                value=values['values'][i-start]
                if value is not None:sheet.cell(i,j,Decimal(value))
        for cell in sheet[header][:1+count]:cell.fill=PatternFill('solid',fgColor='15243B');cell.font=Font(bold=True,color='FFFFFF');cell.alignment=Alignment(wrap_text=True)
        sheet.row_dimensions[header].height=min(400,max(32,max(math.ceil(len(str(c.value or ''))/22)*14 for c in sheet[header][:1+count])))
        if panel['categories'] and series:
            chart={'bar':BarChart,'line':LineChart,'pie':PieChart}[panel['kind']]()
            chart.title=f"{panel['aggregation']} / {panel['value_label'][:40]} ({panel['unit'][:24] or 'unit not specified'})"
            chart.add_data(Reference(sheet,min_col=2,max_col=count+1,min_row=header,max_row=start+len(panel['categories'])-1),titles_from_data=True)
            chart.set_categories(Reference(sheet,min_col=1,min_row=start,max_row=start+len(panel['categories'])-1))
            chart.width=23;chart.height=11;chart.display_blanks='gap';sheet.add_chart(chart,f'A{start+len(panel["categories"])+2}')
        exact=start+len(panel['categories'])+27
        caption(exact,'Exact computed values (text; preserves precision beyond Excel numeric charts)')
        text(exact+1,1,panel['category_label'])
        for j,values in enumerate(series,2):text(exact+1,j,values['label'])
        for i,label in enumerate(panel['categories'],exact+2):
            text(i,1,label);sheet.row_dimensions[i].height=min(400,max(20,math.ceil(len(label)/22)*14))
            for j,values in enumerate(series,2):text(i,j,values['values'][i-exact-2] if values['values'][i-exact-2] is not None else 'No data')
        row=exact+len(panel['categories'])+5
    if result['omitted_units']:text(row,1,f"{result['omitted_units']} additional unit groups are outside the configured plot limit.")
    for i in range(1,visible_columns+1):sheet.column_dimensions[__import__('openpyxl').utils.get_column_letter(i)].width=22
    sheet.freeze_panes='B10';sheet.sheet_properties.pageSetUpPr.fitToPage=True
    sheet.page_setup.orientation='landscape';sheet.page_setup.paperSize=sheet.PAPERSIZE_A3
    sheet.page_setup.fitToWidth=1;sheet.page_setup.fitToHeight=0
    book.active=0

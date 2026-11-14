"""In-memory server exports of reviewed inert artifact data. No URL fetching."""
import io
import math
import threading
from pathlib import Path
from xml.sax.saxutils import escape
from fastapi import HTTPException

_font_lock=threading.RLock()
WIDTH,HEIGHT=960,540
MARGIN=54
MAX_PAGES=100


def fonts():
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from app.core.config import settings
    folder=Path(reportlab.__file__).parent/'fonts'
    normal=Path(settings.AI_ARTIFACT_FONT_PATH) if settings.AI_ARTIFACT_FONT_PATH else folder/'Vera.ttf'
    bold=Path(settings.AI_ARTIFACT_BOLD_FONT_PATH) if settings.AI_ARTIFACT_BOLD_FONT_PATH else normal if settings.AI_ARTIFACT_FONT_PATH else folder/'VeraBd.ttf'
    with _font_lock:
        if not {'SuiteArtifact','SuiteArtifactBold'}<=set(pdfmetrics.getRegisteredFontNames()):
            try:
                pdfmetrics.registerFont(TTFont('SuiteArtifact',str(normal)))
                pdfmetrics.registerFont(TTFont('SuiteArtifactBold',str(bold)))
            except Exception:raise HTTPException(503,'The server artifact font could not be loaded') from None
    return 'SuiteArtifact','SuiteArtifactBold'


def references(item):
    result=[]
    for source in (item.get('provenance') or {}).get('citations',[])[:50]:
        result.append(' - '.join(str(source[k]) for k in ('label','id','href') if source.get(k)))
    return result


def texts(item):
    yield item['title'];yield item.get('content','')
    yield from item.get('columns',[])
    for row in item.get('rows',[]):yield from row
    for slide in item.get('slides',[]):yield slide['title'];yield from slide['bullets']
    yield from references(item)
    yield (item.get('provenance') or {}).get('note','')


def pdf_glyphs(item):
    from reportlab.pdfbase import pdfmetrics
    normal,bold=fonts();supported=pdfmetrics.getFont(normal).face.charToGlyph.keys()&pdfmetrics.getFont(bold).face.charToGlyph.keys()
    if any(ord(char) not in supported for text in texts(item) for char in text if not char.isspace()):
        raise HTTPException(422,'Some characters are unsupported by the server PDF font. Use Word/PowerPoint or ask your administrator to configure a suitable server PDF font.')


def wrap(text,width,size,font):
    """Explicit line breaks keep the same conservative layout in PDF and PPTX."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    lines=[];line=''
    for word in text.split():
        if line and stringWidth(line+' '+word,font,size)>width:
            lines.append(line);line=''
        # Break long tokens rather than clipping URLs or literal identifiers.
        for char in word:
            candidate=line+char
            if stringWidth(candidate,font,size)>width and line:lines.append(line);line=''
            line+=char
        line+=' '
    if line.strip():lines.append(line.rstrip())
    return lines or ['']


def slide_pages(item):
    normal,bold=fonts();slides=list(item['slides']);refs=references(item)
    if refs:
        for start in range(0,len(refs),6):slides.append({'title':'Source references at preparation time','bullets':refs[start:start+6]})
    pages=[]
    for slide in slides:
        paragraphs=[]
        for point in slide['bullets']:
            wrapped=wrap(point,(WIDTH-2*MARGIN-24)*.92,20,normal)
            paragraphs.append([('- ' if n==0 else '  ')+line for n,line in enumerate(wrapped)])
        part=0
        while paragraphs or part==0:
            title=slide['title']+(' (continued)' if part else '')
            heading=wrap(title,(WIDTH-2*MARGIN)*.92,28,bold)
            top=65+len(heading)*35+25
            capacity=max(1,math.floor((HEIGHT-48-top)/26))
            selected=[]
            while paragraphs:
                point=paragraphs[0];remaining=capacity-len(selected)-(1 if selected else 0)
                if len(point)<=remaining:
                    if selected:selected.append('')
                    selected.extend(paragraphs.pop(0))
                elif selected:break  # Keep a point together whenever it fits a page.
                else:
                    selected.extend(point[:remaining]);paragraphs[0]=point[remaining:];break
            pages.append({'title':heading,'lines':selected,'body_top':top})
            if len(pages)>MAX_PAGES:raise HTTPException(422,'Export exceeds 100 pages. Split the artifact or shorten its source references.')
            part+=1
    return pages


def pdf(item,*,media_content=None):
    pdf_glyphs(item)
    return slide_pdf(item) if item['kind']=='presentation' else document_pdf(item,media_content=media_content)


def slide_pdf(item):
    from reportlab.pdfgen import canvas
    normal,bold=fonts();stream=io.BytesIO();pages=slide_pages(item)
    c=canvas.Canvas(stream,pagesize=(WIDTH,HEIGHT));c.setTitle(item['title']);c.setAuthor('BusinessSuite')
    for number,page in enumerate(pages,1):
        c.setFillColorRGB(.08,.14,.25);c.rect(0,0,12,HEIGHT,fill=1,stroke=0)
        c.setFillColorRGB(.35,.42,.52);c.setFont(normal,10)
        for n,line in enumerate(wrap(item['title'],WIDTH-2*MARGIN,10,normal)):c.drawString(MARGIN,HEIGHT-25-n*12,line)
        c.setFillColorRGB(.08,.14,.25);c.setFont(bold,28)
        for n,line in enumerate(page['title']):c.drawString(MARGIN,HEIGHT-65-n*35-28,line)
        c.setFillColorRGB(.16,.21,.29);c.setFont(normal,20)
        for n,line in enumerate(page['lines']):c.drawString(MARGIN,HEIGHT-page['body_top']-n*26-20,line)
        c.setFont(normal,9);c.setFillColorRGB(.4,.45,.52)
        c.drawString(MARGIN,24,f"{item['module']} / version {item['revision']} / reviewed artifact")
        c.drawRightString(WIDTH-MARGIN,24,f'{number} / {len(pages)}');c.showPage()
    c.save();return stream.getvalue()


def document_pdf(item,*,media_content=None):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4,landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,LongTable,TableStyle
    normal,bold=fonts();stream=io.BytesIO()
    size=landscape(A4) if item['kind']=='table' and (len(item['columns'])>5 or item.get('chart')) else A4
    doc=SimpleDocTemplate(stream,pagesize=size,rightMargin=42,leftMargin=42,topMargin=48,bottomMargin=45,
        title=item['title'],author='BusinessSuite')
    body=ParagraphStyle('artifact-body',fontName=normal,fontSize=10,leading=15,spaceAfter=8,splitLongWords=True)
    title=ParagraphStyle('artifact-title',parent=body,fontName=bold,fontSize=20,leading=26,spaceAfter=18,textColor=colors.HexColor('#15243b'))
    small=ParagraphStyle('artifact-small',parent=body,fontSize=8,leading=11)
    cell=ParagraphStyle('artifact-cell',parent=body,fontSize=8,leading=11,spaceAfter=0)
    head=ParagraphStyle('artifact-header',parent=cell,fontName=bold,textColor=colors.white)
    def paragraph(text,style=body):return Paragraph(escape(text).replace('\n','<br/>').replace('\t','    '),style)
    story=[paragraph(item['title'],title),paragraph(f"{item['module']} / version {item['revision']} / reviewed artifact",small)]
    for block in item.get('content','').split('\n\n'):
        if block.strip():story.append(paragraph(block))
    if item['kind']=='image':
        from app.ai_operator.artifact_images import validate
        from reportlab.platypus import Image
        content=validate(media_content,item.get('image'));manifest=item['image']
        scale=min(doc.width/manifest['width'],480/manifest['height'],1)
        picture=Image(io.BytesIO(content),width=manifest['width']*scale,height=manifest['height']*scale)
        picture.hAlign='LEFT';story.extend([Spacer(1,8),picture,Spacer(1,12)])
    if item.get('chart'):
        from app.ai_operator.artifact_chart_exports import pdf_flowables
        story.extend(pdf_flowables(item,doc.width,paragraph,cell,head))
    if item['kind']=='table':
        table=LongTable([[paragraph(v,head) for v in item['columns']],
            *[[paragraph(v,cell) for v in row] for row in item['rows']]],
            colWidths=[doc.width/len(item['columns'])]*len(item['columns']),repeatRows=1,splitInRow=1)
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#15243b')),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#ccd3de')),
            ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
            ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]));story.extend([Spacer(1,8),table])
    note=(item.get('provenance') or {}).get('note')
    if note:story.extend([Spacer(1,12),paragraph(note,small)])
    refs=references(item)
    if refs:
        story.extend([Spacer(1,12),paragraph('Source references at preparation time',body)])
        story.extend(paragraph(ref,small) for ref in refs)
    def footer(c,doc):
        if doc.page>MAX_PAGES:raise HTTPException(422,'Export exceeds 100 pages. Split the artifact.')
        c.saveState();c.setFont(normal,8);c.setFillColor(colors.HexColor('#586579'))
        c.drawString(42,24,'BusinessSuite / private artifact');c.drawRightString(size[0]-42,24,str(doc.page));c.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()


def powerpoint(item):
    from pptx import Presentation
    from pptx.util import Inches,Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR
    pages=slide_pages(item);deck=Presentation();deck.slide_width=Inches(WIDTH/72);deck.slide_height=Inches(HEIGHT/72)
    deck.core_properties.title=item['title'];deck.core_properties.author='BusinessSuite'
    def box(slide,x,y,w,h,text,size,color,bold=False):
        shape=slide.shapes.add_textbox(Pt(x),Pt(y),Pt(w),Pt(h));tf=shape.text_frame
        tf.margin_left=tf.margin_right=tf.margin_top=tf.margin_bottom=0;tf.word_wrap=False;tf.vertical_anchor=MSO_ANCHOR.TOP
        for index,line in enumerate(text.split('\n')):
            p=tf.paragraphs[0] if index==0 else tf.add_paragraph();p.text=line
            p.font.name='Arial';p.font.size=Pt(size);p.font.bold=bold;p.font.color.rgb=RGBColor(*color)
            p.space_before=Pt(0);p.space_after=Pt(0);p.line_spacing=Pt(35 if size==28 else 26 if size==20 else 12)
        return shape
    for number,page in enumerate(pages,1):
        slide=deck.slides.add_slide(deck.slide_layouts[6])
        accent=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,0,0,Pt(12),Pt(HEIGHT));accent.fill.solid();accent.fill.fore_color.rgb=RGBColor(20,36,63);accent.line.fill.background()
        normal,_=fonts()
        box(slide,MARGIN,15,WIDTH-2*MARGIN,36,'\n'.join(wrap(item['title'],WIDTH-2*MARGIN,10,normal)),10,(90,105,125))
        box(slide,MARGIN,65,WIDTH-2*MARGIN,len(page['title'])*35+8,'\n'.join(page['title']),28,(20,36,63),True)
        box(slide,MARGIN,page['body_top'],WIDTH-2*MARGIN,HEIGHT-page['body_top']-42,'\n'.join(page['lines']),20,(41,54,74))
        box(slide,MARGIN,HEIGHT-33,WIDTH-2*MARGIN,18,f"{item['module']} / version {item['revision']} / reviewed artifact     {number} / {len(pages)}",9,(90,105,125))
    stream=io.BytesIO();deck.save(stream);return stream.getvalue()

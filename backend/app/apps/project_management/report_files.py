"""Report exports with actual spreadsheet and paginated PDF formats."""
from io import BytesIO
from numbers import Number
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED


def xlsx_bytes(headers, rows):
    def column(index):
        name = ""
        while index:
            index, digit = divmod(index - 1, 26)
            name = chr(65 + digit) + name
        return name

    data = []
    for number, row in enumerate([headers, *rows], 1):
        cells = []
        for index, value in enumerate(row, 1):
            ref = f"{column(index)}{number}"
            style = ' s="1"' if number == 1 else ""
            if isinstance(value, Number) and not isinstance(value, bool):
                cells.append(f'<c r="{ref}"{style}><v>{value}</v></c>')
            else:
                text = escape(str(value) if value is not None else "")
                text = "".join(c for c in text if c in "\t\n\r" or ord(c) >= 32)
                cells.append(f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">{text}</t></is></c>')
        data.append(f'<row r="{number}">{"".join(cells)}</row>')
    namespace = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    files = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        "_rels/.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": f'<workbook {namespace} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="PMS report" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        "xl/styles.xml": f'<styleSheet {namespace}><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf fontId="0"/><xf fontId="1" applyFont="1"/></cellXfs></styleSheet>',
        "xl/worksheets/sheet1.xml": f'<worksheet {namespace}><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="{len(headers)}" width="24" customWidth="1"/></cols><sheetData>{"".join(data)}</sheetData><autoFilter ref="A1:{column(len(headers))}{len(rows)+1}"/></worksheet>',
    }
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + content)
    return output.getvalue()


def pdf_bytes(title, headers, rows):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    output = BytesIO()
    styles = getSampleStyleSheet()
    page = landscape(A4)
    body = [[Paragraph(escape(str(value)) if value is not None else "", styles["BodyText"]) for value in row] for row in [headers, *rows]]
    table = Table(body, colWidths=[(page[0] - 60) / len(headers)] * len(headers), repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ede9fe")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), .4, colors.lightgrey), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    SimpleDocTemplate(output, pagesize=page, leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30).build([Paragraph(escape(title), styles["Title"]), Spacer(1, 12), table])
    return output.getvalue()

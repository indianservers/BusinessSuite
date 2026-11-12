"""Synthetic offline chart matrix for PDF and native Excel visual QA."""
import io
import json
from pathlib import Path
from openpyxl import Workbook
from pypdf import PdfReader,PdfWriter
from app.ai_operator.artifacts import Body
from app.ai_operator.artifact_exports import pdf
from app.ai_operator.artifact_chart_exports import excel


def main():
    folder=Path(__file__).resolve().parents[2]/'.local'/'artifact-charts-preview';folder.mkdir(parents=True,exist_ok=True)
    rows=[['North','100','USD'],['South','200','USD'],['North','50','INR'],['South','75','INR'],['West','=1+1','USD'],['East','','INR']]
    book=Workbook();source=book.active;source.title='Artifact'
    for values in [['Region','Amount','Currency'],*rows]:
        source.append(values)
        for cell in source[source.max_row]:cell.data_type='s'
    writer=PdfWriter()
    for kind in ('bar','line','pie'):
        item={'id':1,'module':'CRM','revision':1,'provenance':{'note':'Synthetic visual QA data; no actual customer records.','citations':[]},
            **Body(title=f'{kind.title()} chart / illustrative regional amounts',kind='table',columns=['Region','Amount','Currency'],rows=rows,
                chart={'kind':kind,'category_column':0,'value_column':1,'aggregation':'sum'}).model_dump()}
        writer.append(PdfReader(io.BytesIO(pdf(item))));excel(book,item)
    writer.write(folder/'charts.pdf');book.save(folder/'charts.xlsx')
    print(json.dumps({'folder':str(folder),'files':['charts.pdf','charts.xlsx'],'synthetic':True}))


if __name__=='__main__':main()

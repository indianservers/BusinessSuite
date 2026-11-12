"""Offline synthetic dashboard export matrix for visual verification."""
from pathlib import Path
from app.ai_operator.artifact_dashboards import export_pdf,export_excel


def main():
    folder=Path(__file__).resolve().parents[2]/'.local'/'artifact-dashboards-preview';folder.mkdir(parents=True,exist_ok=True)
    base={'module':'CRM','revision':1,'current_revision':1,'content':'Synthetic source snapshot.','columns':['Region','Amount','Currency'],
        'rows':[['North','100','USD'],['South','200','USD'],['North','50','INR']],
        'provenance':{'note':'Synthetic QA; no actual business records.','citations':[]}}
    sources=[{**base,'id':1,'kind':'table','title':'Regional amounts','chart':{'kind':'bar','category_column':0,'value_column':1,'aggregation':'sum'}},
        {**base,'id':2,'module':'HRMS','kind':'document','title':'Staffing review','columns':[],'rows':[],
        'content':'Synthetic staffing review. Confirm assignments with the responsible manager.'}]
    item={**base,'id':3,'kind':'dashboard','title':'Illustrative delivery dashboard','content':'Version-pinned source snapshots for internal verification.','columns':[],'rows':[],
        'panels':[{'artifact_id':1,'revision':1,'display':'chart','label':'Regional delivery'},{'artifact_id':2,'revision':1,'display':'summary','label':'Staffing'}]}
    (folder/'dashboard.pdf').write_bytes(export_pdf(item,sources));(folder/'dashboard.xlsx').write_bytes(export_excel(item,sources))
    print('Synthetic dashboard PDF and Excel generated',flush=True)


if __name__=='__main__':main()

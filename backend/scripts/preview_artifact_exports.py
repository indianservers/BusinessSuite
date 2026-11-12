"""Synthetic offline export fixtures for visual QA. No app data or model calls."""
import json
from pathlib import Path
from app.ai_operator.artifacts import Body
from app.ai_operator.artifact_exports import pdf,powerpoint


def main():
    folder=Path(__file__).resolve().parents[2]/'.local'/'artifact-exports-preview';folder.mkdir(parents=True,exist_ok=True)
    common={'id':1,'module':'CRM','revision':2,'provenance':{'note':'Synthetic QA content. Source references describe preparation time.',
        'citations':[{'id':'crm.tasks:42','label':'Illustrative delivery review','href':'/crm/tasks'}]}}
    deck={**common,**Body(title='Monthly delivery review',kind='presentation',slides=[
        {'title':'Delivery commitments need an owner and a confirmed date','bullets':['Illustrative test data only.','Confirm the scope before assigning recovery work.','Keep recommendations separate from verified delivery facts.']},
        {'title':'Next steps','bullets':['Review outstanding dependencies with the project owner.','Agree a revised delivery date with the customer.','Prepare follow-up actions for review.']},
        {'title':'Long text remains readable on continued pages','bullets':[('Review the delivery commitment and confirm the next owner. '*3)+f'Item {i+1}.' for i in range(6)]}
    ]).model_dump()}
    report={**common,**Body(title='Illustrative delivery tracker',kind='table',content='Synthetic export QA. Values are examples, not business results.',
        columns=['Project','Owner','Due date','Status','Next action','Evidence'],rows=[
            [f'Example project {i+1}','Project coordinator','2026-11-30','Review needed','Confirm dependencies and customer commitment.','Illustrative record'] for i in range(12)]).model_dump()}
    (folder/'presentation.pdf').write_bytes(pdf(deck));(folder/'presentation.pptx').write_bytes(powerpoint(deck))
    (folder/'report.pdf').write_bytes(pdf(report))
    print(json.dumps({'folder':str(folder),'files':['presentation.pdf','presentation.pptx','report.pdf'],'synthetic':True}))


if __name__=='__main__':main()

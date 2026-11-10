"""Render sample documents for visual QA without connecting to a database."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.asset_documents import pdf_document
folder=Path(__file__).resolve().parents[2]/'outputs/asset-lifecycle-qa'
folder.mkdir(parents=True,exist_ok=True)
facts=[('Employee','QA sample employee (EMP-001)'),('Assigned on','10 November 2026'),('Acknowledgment','Employee acknowledgment pending')]
(folder/'handover-sample.pdf').write_bytes(pdf_document('QA sample company','Asset handover receipt','HND-QA-SAMPLE',facts,['Asset / tag','Handover condition','Accessories','Expected return'],[[f'Company laptop with a long descriptive model name / AST-{i:03}', 'Good','Charger, protective bag and power adapter','10 December 2026'] for i in range(12)],['This receipt reflects recorded acknowledgment. It does not assert a handwritten or cryptographic signature.']))
(folder/'clearance-sample.pdf').write_bytes(pdf_document('QA sample company','Asset clearance certificate','ASSET-CLEARANCE-QA',facts,['Asset / tag','Returned','Inspection','Recovery'],[['Company laptop / AST-001','10 November 2026','Approved','None']],['Scope: COMPANY ASSETS ONLY. This certificate does not approve or complete company-wide offboarding, final settlement, or employment termination.','Department checks: IT completed; HR pending; Finance pending.']))
print(folder)

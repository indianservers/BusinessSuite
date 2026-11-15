from pathlib import Path
p=Path('backend/tests/test_crm_school_sales_process.py');s=p.read_text();p.write_text('from tests.rich_text_test_utils import organization_context\n'+s)
p=Path('backend/app/apps/crm/lead_management.py');s=p.read_text(encoding='utf-8').replace('\u00e2\u2020\u2019','\u2192');p.write_text(s,encoding='utf-8')

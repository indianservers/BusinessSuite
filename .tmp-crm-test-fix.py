from pathlib import Path
p=Path('backend/tests/test_crm_school_sales_process.py');s=p.read_text().replace("status='Scheduled')", "status='Scheduled',created_by_user_id=owner)");p.write_text(s)

from pathlib import Path
p=Path('backend/app/apps/crm/lead_management.py');s=p.read_text();start=s.index('def complete_lead_task(');a=s[:start];b=s[start:];b=b.replace('    if payload.responded:\n        data["lastResponseAt"] = now().isoformat()\n        data.pop("proposalReminder", None)\n','',1);p.write_text(a+b)

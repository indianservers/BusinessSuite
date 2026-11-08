from pathlib import Path
p=Path('frontend/src/apps/hrms/pages/employees/EmployeeDetailPage.tsx');s=p.read_text(encoding='utf-8').replace('    else setRouteParams(values);','    else setRouteParams({tab: activeTab, ...values});');p.write_text(s,encoding='utf-8')

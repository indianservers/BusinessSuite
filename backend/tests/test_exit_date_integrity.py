from datetime import date, timedelta
import pytest

from tests.rich_text_test_utils import organization_context
from tests.test_hrms_operational_foundations import _create_employee_user


def test_exit_edit_rejects_date_before_joining(client, superuser_headers):
    employee, _ = _create_employee_user(client, superuser_headers, 'EXITDATE001')
    result = client.post('/api/v1/exit/records', headers=superuser_headers,
        json={'employee_id': employee['id'], 'exit_type': 'Resignation',
              'last_working_date': date.today().isoformat()})
    assert result.status_code == 201, result.text
    record_id = result.json()['id']
    result = client.put(f'/api/v1/exit/records/{record_id}', headers=superuser_headers,
        json={'last_working_date': (date.today() - timedelta(days=1)).isoformat(),
              'reason': 'Must not save an invalid partial edit'})
    assert result.status_code == 422, result.text
    records = client.get('/api/v1/exit/records', headers=superuser_headers,
        params={'employee_id': employee['id']}).json()
    assert records[0]['last_working_date'] == date.today().isoformat()
    assert records[0]['reason'] is None
    valid = client.put(f'/api/v1/exit/records/{record_id}', headers=superuser_headers,
        json={'last_working_date': (date.today() + timedelta(days=1)).isoformat(), 'reason': 'Valid notice period'})
    assert valid.status_code == 200, valid.text
    assert valid.json()['reason'] == 'Valid notice period'


@pytest.mark.parametrize('changes', [{'status': 'Finished'}, {'status': None}, {'notice_waived': None}])
def test_exit_edit_rejects_invalid_required_values(client, superuser_headers, changes):
    employee, _ = _create_employee_user(client, superuser_headers, 'EXITSTATE001')
    result = client.post('/api/v1/exit/records', headers=superuser_headers,
        json={'employee_id': employee['id'], 'exit_type': 'Resignation'})
    assert result.status_code == 201, result.text
    record_id = result.json()['id']
    result = client.put(f'/api/v1/exit/records/{record_id}', headers=superuser_headers, json=changes)
    assert result.status_code == 422, result.text
    record = client.get('/api/v1/exit/records', headers=superuser_headers,
        params={'employee_id': employee['id']}).json()[0]
    assert record['status'] == 'Initiated'
    assert record['notice_waived'] is False

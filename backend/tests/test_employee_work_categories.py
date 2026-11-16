import pytest
from pydantic import ValidationError
from app.models.employee import Employee
from app.schemas.employee import EmployeeUpdate
from tests.test_employee_profile_records import profile_employee
from tests.rich_text_test_utils import organization_context


def test_categories_roundtrip_and_shared_directory(client, db, superuser_headers, profile_employee):
    ident, other = profile_employee
    response = client.put(f'/api/v1/employees/{ident}', headers=superuser_headers,
        json={'work_categories': [' Consultants ', 'Stylists', 'consultants']})
    assert response.status_code == 200, response.text
    assert response.json()['work_categories'] == ['Consultants', 'Stylists']
    db.expire_all()
    assert db.get(Employee, ident).work_categories == ['Consultants', 'Stylists']
    assert db.get(Employee, other).work_categories == []
    options = client.get('/api/v1/employees/work-category-options', headers=superuser_headers)
    assert options.status_code == 200, options.text
    assert 'Consultants' in options.json()['items']
    directory = client.get('/api/v1/employees/directory', headers=superuser_headers,
        params=[('employee_categories', 'stylists'), ('employee_categories', 'Unmatched')])
    assert directory.status_code == 200, directory.text
    assert {row['id'] for row in directory.json()['items']} == {ident}
    assert directory.json()['items'][0]['work_categories'] == ['Consultants', 'Stylists']
    assert client.put(f'/api/v1/employees/{ident}', headers=superuser_headers,
        json={'work_categories': []}).json()['work_categories'] == []


@pytest.mark.parametrize('values', [[''], ['x' * 81], ['x'] * 21])
def test_invalid_categories_rejected(values):
    with pytest.raises(ValidationError):
        EmployeeUpdate(work_categories=values)

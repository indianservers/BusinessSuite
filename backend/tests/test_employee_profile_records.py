from tests.rich_text_test_utils import organization_context
from datetime import date
import pytest
from sqlalchemy import select
from app.models.employee import Employee, EmployeeEducation, EmployeeExperience, EmployeeSkill, EmployeeCertification


@pytest.fixture
def profile_employee(db):
    employee = Employee(employee_id='PROFILE-QA', first_name='Profile', last_name='QA', date_of_joining=date(2026, 1, 1))
    other = Employee(employee_id='PROFILE-OTHER', first_name='Other', last_name='QA', date_of_joining=date(2026, 1, 1))
    db.add_all([employee, other])
    db.commit()
    return employee.id, other.id


@pytest.mark.parametrize('section,collection,model,payload,field,value', [
    ('education', 'educations', EmployeeEducation, {'degree':'B.Tech','board_university':'QA University','pass_year':2020,'percentage_cgpa':'8.75'}, 'degree', 'M.Tech'),
    ('experience', 'experiences', EmployeeExperience, {'company_name':'Previous Corp','designation':'Engineer','from_date':'2020-01-01','to_date':'2024-01-01'}, 'designation', 'Senior Engineer'),
    ('skills', 'skills', EmployeeSkill, {'skill_name':'Python','proficiency':'Advanced','years_experience':'3.5'}, 'proficiency', 'Expert'),
    ('certifications', 'certifications', EmployeeCertification, {'certification_name':'Cloud Architect','issuing_body':'Cloud Provider','certificate_number':'CERT-001','issue_date':'2025-01-01','expiry_date':'2028-01-01','is_renewable':True,'verification_url':'https://example.com/verify'}, 'certification_name', 'Cloud Professional'),
])
def test_profile_database_roundtrip(client, db, superuser_headers, profile_employee, section, collection, model, payload, field, value):
    employee_id, other_id = profile_employee
    url = f'/api/v1/employees/{employee_id}/{section}'
    response = client.post(url, json=payload, headers=superuser_headers)
    assert response.status_code == 201, response.text
    record_id = response.json()['id']
    db.expire_all()
    stored = db.scalar(select(model).where(model.id == record_id))
    for key, expected in payload.items():
        actual = getattr(stored, key)
        assert str(actual) == str(expected) or actual == expected
    payload[field] = value
    response = client.put(f'{url}/{record_id}', json=payload, headers=superuser_headers)
    assert response.status_code == 200, response.text
    db.expire_all()
    assert getattr(db.scalar(select(model).where(model.id == record_id)), field) == value
    response = client.get(f'/api/v1/employees/{employee_id}', headers=superuser_headers)
    assert response.status_code == 200, response.text
    assert response.json()[collection][0][field] == value
    for method in ('put', 'delete'):
        args = {'json':payload} if method == 'put' else {}
        wrong = getattr(client, method)(f'/api/v1/employees/{other_id}/{section}/{record_id}', headers=superuser_headers, **args)
        assert wrong.status_code == 404, wrong.text
    assert client.delete(f'{url}/{record_id}', headers=superuser_headers).status_code == 200
    db.expire_all()
    assert db.scalar(select(model).where(model.id == record_id)) is None
    assert client.get(f'/api/v1/employees/{employee_id}', headers=superuser_headers).json()[collection] == []


@pytest.mark.parametrize('section,payload', [
    ('skills',{'skill_name':'Python','years_experience':-1}),
    ('education',{'degree':'B.Tech','pass_year':2020.5}),
    ('experience',{'company_name':'Corp','from_date':'2024-01-01','to_date':'2020-01-01'}),
    ('certifications',{'certification_name':'  '}),
    ('certifications',{'certification_name':'License','issue_date':'2026-01-01','expiry_date':'2025-01-01'}),
])
def test_profile_validation(client, superuser_headers, profile_employee, section, payload):
    employee_id, _ = profile_employee
    response = client.post(f'/api/v1/employees/{employee_id}/{section}', json=payload, headers=superuser_headers)
    assert response.status_code == 422, response.text


@pytest.mark.skipif(__import__('os').environ.get('RUN_PROFILE_BROWSER') != '1', reason='Requires Vite on port 5198')
def test_profile_browser_database(client, db, superuser_headers, profile_employee):
    """Browser -> real API handlers -> SQL database; reload after every mutation."""
    import os
    import socket
    import subprocess
    import threading
    import time
    import uvicorn
    from pathlib import Path
    from app.main import app
    from app.models.company import Company, Branch, Department, Designation

    employee_id, _ = profile_employee
    employee = db.get(Employee, employee_id)
    branch = db.get(Branch, employee.branch_id)
    assert branch is not None
    company = db.get(Company, branch.company_id)
    department = Department(name='Profile QA Department', branch_id=branch.id)
    db.add(department); db.flush()
    designation = Designation(name='Profile QA Designation', department_id=department.id)
    db.add(designation); db.flush()
    employee = db.get(Employee, employee_id)
    employee.department_id = department.id
    db.commit()
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, lifespan='off', log_level='error'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(.05)
        assert server.started
        env = dict(os.environ, PROFILE_API=f'http://127.0.0.1:{port}', PROFILE_EMPLOYEE=str(employee_id),
                   PROFILE_DESIGNATION=str(designation.id), PROFILE_TOKEN=superuser_headers['Authorization'].split(' ', 1)[1],
                   PROFILE_COMPANY=str(company.id), PROFILE_BRANCH=str(branch.id))
        result = subprocess.run(['node', 'scripts/test-employee-profile-records.cjs'], cwd=Path(__file__).resolve().parents[2] / 'frontend', env=env, capture_output=True, text=True, timeout=420)
        assert result.returncode == 0, result.stdout + result.stderr
        print(result.stdout)
        db.expire_all()
        assert db.get(Employee, employee_id).designation_id == designation.id
        for model in (EmployeeEducation, EmployeeExperience, EmployeeSkill, EmployeeCertification):
            assert db.scalar(select(model).where(model.employee_id == employee_id)) is None
    finally:
        server.should_exit = True
        thread.join(timeout=10)

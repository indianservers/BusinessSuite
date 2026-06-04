from datetime import date, timedelta

from app.apps.project_management.access import get_project_for_action
from app.apps.project_management.api.router import (
    ProjectCloneRequest,
    add_project_member,
    archive_project,
    clone_project,
    create_project,
    create_task,
    create_task_dependency,
    create_task_time_log,
    list_project_templates,
    report_budget_vs_actual,
    report_client_profitability,
    report_dependency_delays,
    report_milestone_progress,
    report_overdue_tasks,
    report_planned_vs_actual,
    report_project_status_dashboard,
    report_resource_utilization,
    report_timesheet,
    TaskDependencyCreateRequest,
)
from app.apps.project_management.models import PMSActivity, PMSMilestone
from app.apps.project_management.schemas import PMSProjectCreate, PMSProjectMemberCreate, PMSTaskCreate, PMSTimeLogCreate
from app.models.company import Branch, Company, Department
from app.models.employee import Employee
from app.models.user import Permission, Role, User


def _user(db, email: str, permission_names: list[str] | None = None) -> User:
    role = Role(name=f"role_{email}", description="PMS readiness test role")
    db.add(role)
    db.flush()
    permissions = []
    for name in permission_names or []:
        permission = db.query(Permission).filter(Permission.name == name).first()
        if not permission:
            permission = Permission(name=name, description=name, module="project_management")
            db.add(permission)
            db.flush()
        permissions.append(permission)
    role.permissions = permissions
    user = User(email=email, hashed_password="not-used", is_active=True, role_id=role.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_pms_project_clone_archive_template_and_reports(db):
    manager = _user(db, "pms-readiness-manager@example.com", ["pms_manage_projects", "pms_manage_tasks", "pms_time_manage"])
    member = _user(db, "pms-readiness-member@example.com")
    today = date.today()

    project = create_project(
        PMSProjectCreate(
            name="Website Development Project",
            project_key="WEB",
            category="Website Development",
            status="Active",
            planned_start_date=today,
            planned_end_date=today + timedelta(days=20),
            estimated_hours=40,
            estimated_cost=40000,
            budget_amount=60000,
            billing_status="Partially Billed",
            manager_user_id=manager.id,
        ),
        db=db,
        current_user=manager,
    )
    add_project_member(project.id, PMSProjectMemberCreate(user_id=member.id, role="Team Member", allocation_percent=75), db=db, current_user=manager)
    milestone = PMSMilestone(project_id=project.id, name="UAT Sign-off", start_date=today, due_date=today + timedelta(days=15), status="In Progress")
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    blocker = create_task(project.id, PMSTaskCreate(task_key="WEB-1", title="Finalize design", status="In Progress", due_date=today + timedelta(days=7), estimated_hours=8, milestone_id=milestone.id), db=db, current_user=manager)
    task = create_task(project.id, PMSTaskCreate(task_key="WEB-2", title="Build website", status="To Do", start_date=today + timedelta(days=2), due_date=today - timedelta(days=1), assignee_user_id=member.id, estimated_hours=16, milestone_id=milestone.id, recurrence_rule="weekly"), db=db, current_user=manager)
    create_task_dependency(TaskDependencyCreateRequest(source_task_id=blocker.id, target_task_id=task.id, lag_days=1), db=db, current_user=manager)
    create_task_time_log(task.id, PMSTimeLogCreate(project_id=project.id, task_id=task.id, log_date=today, duration_minutes=180, is_billable=True), db=db, current_user=manager)

    cloned = clone_project(project.id, ProjectCloneRequest(name="Website Template", project_key="WEBT", as_template=True, include_team=True), db=db, current_user=manager)
    assert cloned.project_key == "WEBT"
    assert list_project_templates(db=db, current_user=manager)[0].id == cloned.id

    archived = archive_project(project.id, db=db, current_user=manager)
    assert archived.is_archived is True

    assert report_project_status_dashboard(projectId=None, db=db, current_user=manager)["total_projects"] >= 2
    assert report_overdue_tasks(projectId=project.id, assigneeId=None, db=db, current_user=manager)["count"] == 1
    assert report_milestone_progress(projectId=project.id, db=db, current_user=manager)["items"][0]["total_tasks"] == 2
    assert report_planned_vs_actual(projectId=project.id, db=db, current_user=manager)["items"][0]["actual_hours"] == 3.0
    assert report_timesheet(projectId=project.id, userId=None, from_=None, to=None, db=db, current_user=manager)["billable_hours"] == 3.0
    assert report_resource_utilization(projectId=project.id, from_=None, to=None, db=db, current_user=manager)["items"][0]["logged_hours"] == 3.0
    assert report_budget_vs_actual(projectId=project.id, db=db, current_user=manager)["items"][0]["actual_cost"] > 0
    assert report_client_profitability(projectId=project.id, db=db, current_user=manager)["projects"][0]["profitability_amount"] > 0
    assert report_dependency_delays(projectId=project.id, db=db, current_user=manager)["count"] == 1
    assert db.query(PMSActivity).filter(PMSActivity.project_id == project.id, PMSActivity.action == "project.archived").first()


def test_department_scoped_project_visibility(db):
    manager = _user(db, "pms-dept-manager@example.com", ["pms_manage_projects"])
    employee_user = _user(db, "pms-dept-member@example.com")
    company = Company(name="PMS Readiness Co")
    db.add(company)
    db.flush()
    branch = Branch(name="Hyderabad", code="HYD", company_id=company.id)
    db.add(branch)
    db.flush()
    department = Department(name="Projects", code="PRJ", branch_id=branch.id)
    db.add(department)
    db.flush()
    employee = Employee(
        employee_id="PMS-DEPT-001",
        user_id=employee_user.id,
        first_name="Dept",
        last_name="Member",
        date_of_joining=date.today(),
        department_id=department.id,
        branch_id=branch.id,
        status="Active",
    )
    db.add(employee)
    db.commit()
    db.refresh(employee_user)

    project = create_project(
        PMSProjectCreate(name="College Accreditation Project", project_key="CAP", department_id=department.id, branch_id=branch.id, status="Planned"),
        db=db,
        current_user=manager,
    )

    assert get_project_for_action(db, project.id, employee_user, "browse").id == project.id

from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from app.apps.project_management.access import can_access_project, get_project_for_action
from app.apps.project_management.api.router import (
    add_project_member,
    create_component,
    create_client,
    create_epic,
    create_project,
    create_release,
    create_risk,
    create_sprint,
    create_dev_integration,
    create_saved_view,
    create_saved_filter,
    create_file_metadata,
    start_sprint,
    complete_sprint,
    get_sprint_review,
    update_sprint_review,
    create_task,
    create_task_subtask,
    create_task_dependency,
    create_task_time_log,
    delete_task_dependency,
    get_backlog,
    get_gantt,
    get_roadmap,
    get_task,
    get_portfolio_projects,
    get_portfolio_summary,
    get_portfolio_health_trend,
    get_project_dashboard,
    report_cumulative_flow,
    report_cycle_time,
    report_project_health,
    report_task_distribution,
    report_team_performance,
    report_time_in_status,
    create_timesheet,
    list_timesheets,
    submit_timesheet,
    approve_timesheet,
    reject_timesheet,
    update_timesheet,
    get_workload_heatmap,
    get_project_velocity,
    get_project_workload,
    get_release_readiness,
    add_task_dependency,
    bulk_update_tasks,
    ChecklistReorderRequest,
    create_task_checklist_entry,
    create_tag,
    delete_checklist_entry,
    delete_attachment,
    delete_dev_integration,
    delete_risk,
    delete_saved_view,
    delete_task,
    delete_time_log,
    add_task_tag,
    list_task_checklist,
    list_task_attachments,
    list_task_time_logs,
    list_tags,
    list_project_activity,
    list_risks,
    list_dev_integrations,
    list_epic_tasks,
    list_task_dev_links,
    list_tasks,
    list_all_tasks,
    list_saved_views,
    list_task_subtasks,
    move_task_to_sprint,
    remove_task_from_sprint,
    remove_task_tag,
    reorder_backlog,
    reorder_task_checklist,
    reorder_sprint_tasks,
    TaskReorderListRequest,
    TaskSprintMoveRequest,
    SubtaskCreateRequest,
    TaskDependencyCreateRequest,
    EpicScheduleUpdateRequest,
    DevIntegrationCreateRequest,
    TaskScheduleUpdateRequest,
    update_epic_schedule,
    update_task_schedule,
    update_time_log,
    update_checklist_entry,
    update_saved_view,
    update_task,
    update_risk,
    _process_dev_payload,
)
from app.apps.project_management.models import PMSActivity, PMSDevIntegration, PMSProjectMember, PMSRisk, PMSUserCapacity  # noqa: F401 - ensure PMS tables are registered
from app.apps.project_management.schemas import (
    PMSChecklistItemCreate,
    PMSClientCreate,
    PMSChecklistItemUpdate,
    PMSComponentCreate,
    PMSEpicCreate,
    PMSProjectCreate,
    PMSProjectMemberCreate,
    PMSReleaseCreate,
    PMSRiskCreate,
    PMSRiskUpdate,
    PMSSavedFilterUpdate,
    PMSSavedFilterCreate,
    PMSFileAssetCreate,
    PMSSprintCreate,
    PMSTagCreate,
    PMSTaskDependencyCreate,
    PMSTimeLogCreate,
    PMSTimeLogUpdate,
    PMSTimesheetCreate,
    PMSTimesheetUpdate,
    PMSTimesheetEntryInput,
    PMSTimesheetRejectRequest,
    PMSTaskUpdate,
    SprintCompleteRequest,
    TaskBulkUpdateRequest,
    PMSTaskCreate,
)
from app.models.user import Permission, Role, User


def _user(db, email: str, permission_names: list[str] | None = None) -> User:
    role = Role(name=f"role_{email}", description="PMS test role")
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


def test_project_creator_becomes_manager_and_can_add_member(db):
    manager = _user(db, "pms-manager@example.com", ["pms_manage_projects"])
    viewer = _user(db, "pms-viewer@example.com")

    project = create_project(
        PMSProjectCreate(name="Client Launch", project_key="CL"),
        db=db,
        current_user=manager,
    )

    assert can_access_project(db, project, manager, "manage_members")

    member = add_project_member(
        project.id,
        PMSProjectMemberCreate(user_id=viewer.id, role="Viewer"),
        db=db,
        current_user=manager,
    )

    assert member.role == "Viewer"
    assert can_access_project(db, project, viewer, "browse")
    assert not can_access_project(db, project, viewer, "manage_tasks")


def test_non_member_cannot_view_or_create_project_tasks(db):
    manager = _user(db, "pms-task-manager@example.com", ["pms_manage_projects"])
    outsider = _user(db, "pms-outsider@example.com")

    project = create_project(
        PMSProjectCreate(name="Private Build", project_key="PB"),
        db=db,
        current_user=manager,
    )

    with pytest.raises(HTTPException) as denied:
        get_project_for_action(db, project.id, outsider, "browse")
    assert denied.value.status_code == 403

    with pytest.raises(HTTPException) as task_denied:
        create_task(
            project.id,
            PMSTaskCreate(title="Hidden task", task_key="PB-1"),
            db=db,
            current_user=outsider,
        )
    assert task_denied.value.status_code == 403


def test_task_attachments_are_project_scoped_and_log_activity(db):
    manager = _user(db, "pms-attachment-manager@example.com", ["pms_manage_projects"])
    outsider = _user(db, "pms-attachment-outsider@example.com")
    project = create_project(
        PMSProjectCreate(name="Attachment Project", project_key="AP"),
        db=db,
        current_user=manager,
    )
    task = create_task(
        project.id,
        PMSTaskCreate(title="Attach design spec", task_key="AP-1"),
        db=db,
        current_user=manager,
    )

    file_asset = create_file_metadata(
        PMSFileAssetCreate(
            project_id=project.id,
            task_id=task.id,
            file_name="design-spec.pdf",
            original_name="design-spec.pdf",
            mime_type="application/pdf",
            size_bytes=2048,
            storage_path="uploads/pms/tasks/test/design-spec.pdf",
            visibility="Internal",
        ),
        db=db,
        current_user=manager,
    )

    files = list_task_attachments(task.id, skip=0, limit=100, db=db, current_user=manager)
    assert len(files) == 1
    assert files[0]["original_name"] == "design-spec.pdf"
    assert files[0]["download_url"].endswith(f"/attachments/{file_asset['id']}/download")
    assert get_task(task.id, db=db, current_user=manager).attachment_count == 1

    with pytest.raises(HTTPException) as denied:
        list_task_attachments(task.id, skip=0, limit=100, db=db, current_user=outsider)
    assert denied.value.status_code == 403

    delete_attachment(file_asset["id"], db=db, current_user=manager)
    assert list_task_attachments(task.id, skip=0, limit=100, db=db, current_user=manager) == []
    assert get_task(task.id, db=db, current_user=manager).attachment_count == 0
    actions = {activity.action for activity in db.query(PMSActivity).filter(PMSActivity.task_id == task.id).all()}
    assert "attachment.added" in actions
    assert "attachment.deleted" in actions


def test_task_saved_views_store_filters_columns_and_permissions(db):
    manager = _user(db, "pms-saved-view-manager@example.com", ["pms_manage_projects"])
    teammate = _user(db, "pms-saved-view-teammate@example.com")
    outsider = _user(db, "pms-saved-view-outsider@example.com")
    project = create_project(
        PMSProjectCreate(name="Saved View Project", project_key="SVP"),
        db=db,
        current_user=manager,
    )
    add_project_member(
        project.id,
        PMSProjectMemberCreate(user_id=teammate.id, role="Member"),
        db=db,
        current_user=manager,
    )

    view = create_saved_view(
        PMSSavedFilterCreate(
            name="High priority open work",
            view_type="task_list",
            entity_type="task",
            filters={"projectId": str(project.id), "priority": "High", "status": "In Progress"},
            sort={"sortBy": "priority", "sortOrder": "desc"},
            columns={"task": True, "title": True, "priority": True, "updated_at": False},
            visibility="workspace",
            is_default=True,
        ),
        db=db,
        current_user=manager,
    )

    teammate_views = list_saved_views(entityType="task", db=db, current_user=teammate)
    assert [item["name"] for item in teammate_views] == ["High priority open work"]
    assert teammate_views[0]["filters"]["priority"] == "High"
    assert teammate_views[0]["columns"]["priority"] is True
    assert teammate_views[0]["is_default"] is True

    with pytest.raises(HTTPException) as denied_update:
        update_saved_view(
            view["id"],
            PMSSavedFilterUpdate(name="Nope"),
            db=db,
            current_user=outsider,
        )
    assert denied_update.value.status_code == 403

    updated = update_saved_view(
        view["id"],
        PMSSavedFilterUpdate(name="QA pending", visibility="private", filters={"status": "In Review"}),
        db=db,
        current_user=manager,
    )
    assert updated["name"] == "QA pending"
    assert updated["visibility"] == "private"
    assert updated["filters"]["status"] == "In Review"

    delete_saved_view(view["id"], db=db, current_user=manager)
    assert list_saved_views(entityType="task", db=db, current_user=manager) == []


def test_all_tasks_endpoint_scopes_by_accessible_organization(db):
    org_one_manager = _user(db, "pms-org-one-manager@example.com", ["pms_manage_projects"])
    org_two_manager = _user(db, "pms-org-two-manager@example.com", ["pms_manage_projects"])
    org_one_manager.organization_id = 101
    org_two_manager.organization_id = 202

    org_one_project = create_project(
        PMSProjectCreate(name="Org One Roadmap", project_key="OOR"),
        db=db,
        current_user=org_one_manager,
    )
    org_two_project = create_project(
        PMSProjectCreate(name="Org Two Roadmap", project_key="OTR"),
        db=db,
        current_user=org_two_manager,
    )
    create_task(
        org_one_project.id,
        PMSTaskCreate(title="Org one visible task", task_key="OOR-1", priority="High", story_points=5),
        db=db,
        current_user=org_one_manager,
    )
    create_task(
        org_two_project.id,
        PMSTaskCreate(title="Org two hidden task", task_key="OTR-1", priority="Low", story_points=2),
        db=db,
        current_user=org_two_manager,
    )

    result = list_all_tasks(
        projectId=None,
        sprintId=None,
        epicId=None,
        status=None,
        priority=None,
        assigneeId=None,
        tag=None,
        search=None,
        dueFrom=None,
        dueTo=None,
        sortBy="storyPoints",
        sortOrder="desc",
        page=1,
        pageSize=25,
        db=db,
        current_user=org_one_manager,
    )

    assert result["total"] == 1
    assert result["items"][0]["task_key"] == "OOR-1"
    assert result["items"][0]["project_name"] == "Org One Roadmap"
    assert result["filters"]["projects"][0]["project_key"] == "OOR"


def test_task_checklist_crud_reorder_and_activity_events(db):
    manager = _user(db, "pms-checklist-manager@example.com", ["pms_manage_projects"])
    manager.organization_id = 303
    project = create_project(
        PMSProjectCreate(name="Checklist Project", project_key="CHK"),
        db=db,
        current_user=manager,
    )
    task = create_task(
        project.id,
        PMSTaskCreate(title="Ship checklist support", task_key="CHK-1"),
        db=db,
        current_user=manager,
    )

    first = create_task_checklist_entry(
        task.id,
        PMSChecklistItemCreate(title="Write API"),
        db=db,
        current_user=manager,
    )
    second = create_task_checklist_entry(
        task.id,
        PMSChecklistItemCreate(title="Wire UI"),
        db=db,
        current_user=manager,
    )

    reordered = reorder_task_checklist(
        task.id,
        ChecklistReorderRequest(item_ids=[second.id, first.id]),
        db=db,
        current_user=manager,
    )
    assert [item.id for item in reordered] == [second.id, first.id]

    completed = update_checklist_entry(
        first.id,
        PMSChecklistItemUpdate(is_completed=True),
        db=db,
        current_user=manager,
    )
    assert completed.is_completed is True

    delete_checklist_entry(second.id, db=db, current_user=manager)
    remaining = list_task_checklist(task.id, db=db, current_user=manager)
    assert [item.id for item in remaining] == [first.id]

    actions = {row.action for row in db.query(PMSActivity).filter(PMSActivity.task_id == task.id).all()}
    assert "checklist.item_added" in actions
    assert "checklist.item_completed" in actions
    assert "checklist.item_deleted" in actions


def test_task_subtasks_crud_progress_and_cycle_guard(db):
    manager = _user(db, "pms-subtask-manager@example.com", ["pms_manage_projects"])
    manager.organization_id = 707
    project = create_project(
        PMSProjectCreate(name="Subtask Delivery", project_key="SUB"),
        db=db,
        current_user=manager,
    )
    parent = create_task(
        project.id,
        PMSTaskCreate(title="Build parent issue", task_key="SUB-1", priority="High"),
        db=db,
        current_user=manager,
    )

    subtask = create_task_subtask(
        parent.id,
        SubtaskCreateRequest(title="Wire child API", priority="Medium", story_points=2),
        db=db,
        current_user=manager,
    )

    assert subtask.parent_task_id == parent.id
    assert subtask.work_type == "Sub-task"
    assert subtask.project_id == parent.project_id
    assert list_task_subtasks(parent.id, db=db, current_user=manager)[0].id == subtask.id

    completed = update_task(subtask.id, PMSTaskUpdate(status="Done"), db=db, current_user=manager)
    assert completed.status == "Done"

    with pytest.raises(HTTPException) as circular:
        update_task(parent.id, PMSTaskUpdate(parent_task_id=subtask.id), db=db, current_user=manager)
    assert circular.value.status_code == 400

    delete_task(subtask.id, db=db, current_user=manager)
    assert list_task_subtasks(parent.id, db=db, current_user=manager) == []

    actions = {row.action for row in db.query(PMSActivity).all()}
    assert "subtask.created" in actions
    assert "subtask.completed" in actions
    assert "subtask.deleted" in actions


def test_task_story_points_and_tags_have_validation_and_activity(db):
    manager = _user(db, "pms-tags-manager@example.com", ["pms_manage_projects"])
    manager.organization_id = 404
    project = create_project(
        PMSProjectCreate(name="Tagged Planning", project_key="TAG"),
        db=db,
        current_user=manager,
    )
    task = create_task(
        project.id,
        PMSTaskCreate(title="Expose estimation fields", task_key="TAG-1", story_points=2),
        db=db,
        current_user=manager,
    )

    updated = update_task(task.id, PMSTaskUpdate(story_points=5), db=db, current_user=manager)
    assert updated.story_points == 5

    tag = create_tag(PMSTagCreate(name="Backend", color="#2563eb"), db=db, current_user=manager)
    assert tag in list_tags(q=None, db=db, current_user=manager)

    attached = add_task_tag(task.id, tag_in=None, name=None, tag_id=tag.id, db=db, current_user=manager)
    assert attached.id == tag.id
    remove_task_tag(task.id, tag.id, db=db, current_user=manager)

    actions = {row.action for row in db.query(PMSActivity).filter(PMSActivity.task_id == task.id).all()}
    assert "story_points.changed" in actions
    assert "task.updated" in actions
    assert "tag.added" in actions
    assert "tag.removed" in actions


def test_task_time_logs_crud_and_activity_events(db):
    manager = _user(db, "pms-time-manager@example.com", ["pms_manage_projects"])
    manager.organization_id = 505
    project = create_project(
        PMSProjectCreate(name="Time Tracking", project_key="TT"),
        db=db,
        current_user=manager,
    )
    task = create_task(
        project.id,
        PMSTaskCreate(title="Wire real time logs", task_key="TT-1"),
        db=db,
        current_user=manager,
    )

    log = create_task_time_log(
        task.id,
        PMSTimeLogCreate(
            project_id=project.id,
            task_id=task.id,
            log_date="2026-05-11",
            duration_minutes=90,
            description="Built task scoped form",
            is_billable=True,
        ),
        db=db,
        current_user=manager,
    )
    assert log.task_id == task.id
    assert log.duration_minutes == 90
    assert list_task_time_logs(task.id, skip=0, limit=100, db=db, current_user=manager)[0].id == log.id

    updated = update_time_log(
        log.id,
        PMSTimeLogUpdate(duration_minutes=120, is_billable=False),
        db=db,
        current_user=manager,
    )
    assert updated.duration_minutes == 120
    assert updated.is_billable is False

    delete_time_log(log.id, db=db, current_user=manager)
    assert list_task_time_logs(task.id, skip=0, limit=100, db=db, current_user=manager) == []

    actions = {row.action for row in db.query(PMSActivity).filter(PMSActivity.task_id == task.id).all()}
    assert "time.logged" in actions
    assert "time.updated" in actions
    assert "time.deleted" in actions


def test_pms_weekly_timesheet_submit_approve_reject_flow(db):
    manager = _user(db, "pms-timesheet-manager@example.com", ["pms_manage_projects"])
    manager.organization_id = 515
    member = _user(db, "pms-timesheet-member@example.com")
    member.organization_id = 515
    outsider = _user(db, "pms-timesheet-outsider@example.com")
    outsider.organization_id = 909
    project = create_project(
        PMSProjectCreate(name="Timesheet Project", project_key="TSH"),
        db=db,
        current_user=manager,
    )
    task = create_task(
        project.id,
        PMSTaskCreate(title="Timesheet work", task_key="TSH-1"),
        db=db,
        current_user=manager,
    )
    add_project_member(project.id, PMSProjectMemberCreate(user_id=member.id, role="Member"), db=db, current_user=manager)
    week_start = date(2026, 5, 11)

    sheet = create_timesheet(
        PMSTimesheetCreate(
            week_start_date=week_start,
            entries=[
                PMSTimesheetEntryInput(
                    project_id=project.id,
                    task_id=task.id,
                    log_date=week_start,
                    duration_minutes=180,
                    description="Implemented grid",
                    is_billable=True,
                )
            ],
        ),
        db=db,
        current_user=member,
    )
    assert sheet["status"] == "draft"
    assert sheet["total_minutes"] == 180
    assert sheet["daily_totals"][str(week_start)] == 180

    submitted = submit_timesheet(sheet["id"], db=db, current_user=member)
    assert submitted["status"] == "submitted"
    assert submitted["entries"][0]["approval_status"] == "Submitted"

    with pytest.raises(HTTPException):
        update_timesheet(
            sheet["id"],
            PMSTimesheetUpdate(entries=[PMSTimesheetEntryInput(project_id=project.id, task_id=task.id, log_date=week_start, duration_minutes=60)]),
            db=db,
            current_user=member,
        )

    manager_view = list_timesheets(weekStart=week_start, userId=member.id, status_filter="submitted", db=db, current_user=manager)
    assert manager_view[0]["id"] == sheet["id"]

    rejected = reject_timesheet(sheet["id"], PMSTimesheetRejectRequest(rejection_reason="Add more detail"), db=db, current_user=manager)
    assert rejected["status"] == "rejected"
    assert rejected["rejection_reason"] == "Add more detail"

    revised = update_timesheet(
        sheet["id"],
        PMSTimesheetUpdate(entries=[PMSTimesheetEntryInput(project_id=project.id, task_id=task.id, log_date=week_start, duration_minutes=240, description="Detailed work")]),
        db=db,
        current_user=member,
    )
    assert revised["status"] == "draft"
    assert revised["total_minutes"] == 240
    submit_timesheet(sheet["id"], db=db, current_user=member)
    approved = approve_timesheet(sheet["id"], db=db, current_user=manager)
    assert approved["status"] == "approved"
    assert approved["entries"][0]["approval_status"] == "Approved"

    with pytest.raises(HTTPException):
        list_timesheets(weekStart=week_start, userId=member.id, status_filter=None, db=db, current_user=outsider)


def test_backlog_move_to_sprint_and_reorder(db):
    manager = _user(db, "pms-backlog-manager@example.com", ["pms_manage_projects"])
    manager.organization_id = 606
    project = create_project(
        PMSProjectCreate(name="Backlog Planning", project_key="BL"),
        db=db,
        current_user=manager,
    )
    sprint = create_sprint(
        project.id,
        PMSSprintCreate(name="Sprint Backlog", start_date="2026-05-12", end_date="2026-05-26", status="Planned"),
        db=db,
        current_user=manager,
    )
    first = create_task(project.id, PMSTaskCreate(title="First backlog item", task_key="BL-1"), db=db, current_user=manager)
    second = create_task(project.id, PMSTaskCreate(title="Second backlog item", task_key="BL-2"), db=db, current_user=manager)

    backlog = get_backlog(projectId=project.id, search=None, sortBy="rank", db=db, current_user=manager)
    assert [item["task_key"] for item in backlog["backlog"]] == ["BL-1", "BL-2"]

    reordered = reorder_backlog(
        TaskReorderListRequest(task_ids=[second.id, first.id]),
        projectId=project.id,
        db=db,
        current_user=manager,
    )
    assert [task.id for task in reordered] == [second.id, first.id]

    moved = move_task_to_sprint(
        first.id,
        TaskSprintMoveRequest(sprint_id=sprint.id),
        db=db,
        current_user=manager,
    )
    assert moved.sprint_id == sprint.id

    sprint_tasks = reorder_sprint_tasks(
        sprint.id,
        TaskReorderListRequest(task_ids=[first.id]),
        db=db,
        current_user=manager,
    )
    assert [task.id for task in sprint_tasks] == [first.id]

    removed = remove_task_from_sprint(first.id, db=db, current_user=manager)
    assert removed.sprint_id is None

    actions = {row.action for row in db.query(PMSActivity).filter(PMSActivity.task_id == first.id).all()}
    assert "sprint.changed" in actions


def test_gantt_dependencies_schedule_and_cycle_validation(db):
    manager = _user(db, "pms-gantt-manager@example.com", ["pms_manage_projects"])
    manager.organization_id = 808
    project = create_project(
        PMSProjectCreate(name="Timeline Delivery", project_key="GAN"),
        db=db,
        current_user=manager,
    )
    source = create_task(
        project.id,
        PMSTaskCreate(title="Design foundation", task_key="GAN-1", start_date="2026-05-11", due_date="2026-05-14"),
        db=db,
        current_user=manager,
    )
    target = create_task(
        project.id,
        PMSTaskCreate(title="Build timeline", task_key="GAN-2", start_date="2026-05-15", due_date="2026-05-20"),
        db=db,
        current_user=manager,
    )

    dependency = create_task_dependency(
        TaskDependencyCreateRequest(source_task_id=source.id, target_task_id=target.id, dependency_type="Finish-to-start", lag_days=1),
        db=db,
        current_user=manager,
    )
    assert dependency["source_task_id"] == source.id
    assert dependency["target_task_id"] == target.id
    assert dependency["dependency_type"] == "Finish To Start"

    gantt = get_gantt(
        projectId=project.id,
        sprintId=None,
        assigneeId=None,
        epicId=None,
        status=None,
        from_date=None,
        to_date=None,
        db=db,
        current_user=manager,
    )
    assert [task["task_key"] for task in gantt["tasks"]] == ["GAN-1", "GAN-2"]
    assert gantt["dependencies"][0]["id"] == dependency["id"]

    scheduled = update_task_schedule(
        target.id,
        TaskScheduleUpdateRequest(start_date="2026-05-12", due_date="2026-05-18"),
        db=db,
        current_user=manager,
    )
    assert scheduled["task"].start_date.isoformat() == "2026-05-12"
    assert scheduled["warnings"]

    with pytest.raises(HTTPException) as circular:
        create_task_dependency(
            TaskDependencyCreateRequest(source_task_id=target.id, target_task_id=source.id, dependency_type="Start To Start"),
            db=db,
            current_user=manager,
        )
    assert circular.value.status_code == 400

    delete_task_dependency(dependency["id"], db=db, current_user=manager)
    assert get_gantt(projectId=project.id, sprintId=None, assigneeId=None, epicId=None, status=None, from_date=None, to_date=None, db=db, current_user=manager)["dependencies"] == []


def test_advanced_issue_fields_persist_and_filter(db):
    manager = _user(db, "pms-issue-manager@example.com", ["pms_manage_projects"])
    project = create_project(
        PMSProjectCreate(name="Software Delivery", project_key="SD"),
        db=db,
        current_user=manager,
    )

    task = create_task(
        project.id,
        PMSTaskCreate(
            title="Fix calendar regression",
            task_key="SD-1",
            work_type="Bug",
            epic_key="EPIC-PLANNING",
            component="Calendar",
            severity="S1",
            environment="Production",
            affected_version="v2.2.1",
            fix_version="v2.3",
            release_name="May Stabilization",
            original_estimate_hours=12,
            remaining_estimate_hours=5,
            story_points=3,
            security_level="Internal",
            development_branch="fix/sd-1-calendar-regression",
            development_commits=2,
            development_prs=1,
            development_build="Failing",
        ),
        db=db,
        current_user=manager,
    )

    assert task.work_type == "Bug"
    assert task.component == "Calendar"
    assert task.fix_version == "v2.3"
    assert task.rank == 1

    filtered = list_tasks(
        project.id,
        skip=0,
        limit=100,
        status=None,
        assignee_id=None,
        sprint_id=None,
        epic_id=None,
        component_id=None,
        release_id=None,
        work_type="Bug",
        epic_key=None,
        component="Calendar",
        severity="S1",
        fix_version="v2.3",
        release_name="May Stabilization",
        security_level=None,
        db=db,
        current_user=manager,
    )

    assert [item.task_key for item in filtered] == ["SD-1"]


def test_normalized_planning_objects_link_to_tasks(db):
    manager = _user(db, "pms-planning-manager@example.com", ["pms_manage_projects"])
    project = create_project(
        PMSProjectCreate(name="Roadmap Build", project_key="RB"),
        db=db,
        current_user=manager,
    )
    epic = create_epic(
        project.id,
        PMSEpicCreate(epic_key="RB-EPIC-1", name="Planning Intelligence", status="Active"),
        db=db,
        current_user=manager,
    )
    component = create_component(
        project.id,
        PMSComponentCreate(name="Timeline", lead_user_id=manager.id),
        db=db,
        current_user=manager,
    )
    release = create_release(
        project.id,
        PMSReleaseCreate(name="v2.4", status="Planning", readiness_percent=35),
        db=db,
        current_user=manager,
    )

    task = create_task(
        project.id,
        PMSTaskCreate(
            title="Build critical path rollup",
            task_key="RB-1",
            epic_id=epic.id,
            component_id=component.id,
            release_id=release.id,
            work_type="Story",
        ),
        db=db,
        current_user=manager,
    )

    assert task.epic_id == epic.id
    assert task.component_id == component.id
    assert task.release_id == release.id
    assert task.epic_key == "RB-EPIC-1"
    assert task.initiative == "Planning Intelligence"
    assert task.component == "Timeline"
    assert task.release_name == "v2.4"
    assert task.fix_version == "v2.4"

    filtered = list_tasks(
        project.id,
        skip=0,
        limit=100,
        status=None,
        assignee_id=None,
        sprint_id=None,
        epic_id=epic.id,
        component_id=component.id,
        release_id=release.id,
        work_type=None,
        epic_key=None,
        component=None,
        severity=None,
        fix_version=None,
        release_name=None,
        security_level=None,
        db=db,
        current_user=manager,
    )
    assert [item.task_key for item in filtered] == ["RB-1"]


def test_roadmap_returns_epics_tasks_sprints_dependencies_and_logs_schedule_changes(db):
    manager = _user(db, "pms-roadmap-manager@example.com", ["pms_manage_projects"])
    project = create_project(
        PMSProjectCreate(name="Roadmap Delivery", project_key="RMD"),
        db=db,
        current_user=manager,
    )
    epic = create_epic(
        project.id,
        PMSEpicCreate(
            epic_key="RMD-EPIC-1",
            name="Cross-sprint roadmap",
            status="Planned",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 6, 15),
            owner_id=manager.id,
        ),
        db=db,
        current_user=manager,
    )
    create_sprint(
        project.id,
        PMSSprintCreate(name="Roadmap Sprint", start_date="2026-05-06", end_date="2026-05-20"),
        db=db,
        current_user=manager,
    )
    blocker = create_task(
        project.id,
        PMSTaskCreate(title="Dependency task", task_key="RMD-1", epic_id=epic.id, story_points=3),
        db=db,
        current_user=manager,
    )
    done_task = create_task(
        project.id,
        PMSTaskCreate(title="Completed roadmap task", task_key="RMD-2", epic_id=epic.id, status="Done", story_points=5),
        db=db,
        current_user=manager,
    )
    add_task_dependency(
        done_task.id,
        PMSTaskDependencyCreate(depends_on_task_id=blocker.id),
        db=db,
        current_user=manager,
    )

    roadmap = get_roadmap(
        projectId=project.id,
        ownerId=None,
        status=None,
        from_date=date(2026, 5, 1),
        to=date(2026, 7, 1),
        db=db,
        current_user=manager,
    )

    assert [item["id"] for item in roadmap["projects"]] == [project.id]
    assert roadmap["sprints"][0]["name"] == "Roadmap Sprint"
    assert roadmap["epics"][0]["epic_key"] == "RMD-EPIC-1"
    assert roadmap["epics"][0]["task_count"] == 2
    assert roadmap["epics"][0]["completed_task_count"] == 1
    assert roadmap["epics"][0]["story_points"] == 8
    assert roadmap["epics"][0]["completed_story_points"] == 5
    assert roadmap["epics"][0]["dependencies"][0]["source_task_id"] == blocker.id
    assert roadmap["epics"][0]["dependencies"][0]["target_task_id"] == done_task.id

    epic_tasks = list_epic_tasks(epic.id, db=db, current_user=manager)
    assert {task["task_key"] for task in epic_tasks} == {"RMD-1", "RMD-2"}

    updated = update_epic_schedule(
        epic.id,
        EpicScheduleUpdateRequest(
            start_date=date(2026, 5, 10),
            end_date=date(2026, 6, 30),
            status="In Progress",
        ),
        db=db,
        current_user=manager,
    )

    assert updated["start_date"] == "2026-05-10"
    assert updated["end_date"] == "2026-06-30"
    assert updated["status"] == "In Progress"
    actions = {activity.action for activity in db.query(PMSActivity).filter(PMSActivity.project_id == project.id).all()}
    assert "epic.schedule_changed" in actions
    assert "epic.status_changed" in actions


def test_workload_heatmap_is_accessible_project_scoped_and_uses_capacity(db):
    manager = _user(db, "pms-workload-manager@example.com", ["pms_manage_projects"])
    teammate = _user(db, "pms-workload-teammate@example.com")
    outsider = _user(db, "pms-workload-outsider@example.com")
    project = create_project(
        PMSProjectCreate(name="Capacity Planning", project_key="CP"),
        db=db,
        current_user=manager,
    )
    add_project_member(
        project.id,
        PMSProjectMemberCreate(user_id=teammate.id, role="Member"),
        db=db,
        current_user=manager,
    )
    db.add(PMSUserCapacity(
        organization_id=project.organization_id,
        user_id=teammate.id,
        week_start_date=date(2026, 5, 4),
        capacity_hours=20,
    ))
    db.commit()
    create_task(
        project.id,
        PMSTaskCreate(
            title="Build workload heatmap",
            task_key="CP-1",
            assignee_user_id=teammate.id,
            start_date=date(2026, 5, 4),
            due_date=date(2026, 5, 8),
            estimated_hours=30,
            story_points=5,
        ),
        db=db,
        current_user=manager,
    )

    heatmap = get_workload_heatmap(
        projectId=project.id,
        teamId=None,
        sprintId=None,
        from_date=date(2026, 5, 4),
        to=date(2026, 5, 11),
        basis="hours",
        db=db,
        current_user=manager,
    )

    teammate_row = next(row for row in heatmap["rows"] if row["user_id"] == teammate.id)
    first_cell = teammate_row["cells"][0]
    assert first_cell["planned_hours"] == 30
    assert first_cell["capacity_hours"] == 20
    assert first_cell["status"] == "over"
    assert first_cell["tasks"][0]["task_key"] == "CP-1"
    assert heatmap["summary"]["over_capacity"] == 1

    outsider_heatmap = get_workload_heatmap(
        projectId=None,
        teamId=None,
        sprintId=None,
        from_date=date(2026, 5, 4),
        to=date(2026, 5, 11),
        basis="hours",
        db=db,
        current_user=outsider,
    )
    assert outsider_heatmap["rows"] == []


def test_dev_integrations_link_github_prs_and_hide_tokens(db):
    manager = _user(db, "pms-dev-manager@example.com", ["pms_manage_projects"])
    project = create_project(
        PMSProjectCreate(name="Developer Workflow", project_key="DW"),
        db=db,
        current_user=manager,
    )
    task = create_task(
        project.id,
        PMSTaskCreate(title="Ship repository webhook", task_key="DW-1", status="In Review"),
        db=db,
        current_user=manager,
    )

    integration_payload = create_dev_integration(
        DevIntegrationCreateRequest(
            provider="github",
            project_id=project.id,
            repo_owner="acme",
            repo_name="web-app",
            access_token="secret-token",
            webhook_secret="hook-secret",
        ),
        db=db,
        current_user=manager,
    )

    assert integration_payload["has_access_token"] is True
    assert "access_token" not in integration_payload
    listed = list_dev_integrations(projectId=project.id, db=db, current_user=manager)
    assert listed[0]["repo_owner"] == "acme"

    integration = db.query(PMSDevIntegration).filter(PMSDevIntegration.id == integration_payload["id"]).first()
    links = _process_dev_payload(
        db,
        integration,
        "github",
        {
            "pull_request": {
                "number": 42,
                "title": "DW-1 finish dev integration",
                "body": "Links commits to the PMS task.",
                "html_url": "https://github.com/acme/web-app/pull/42",
                "state": "closed",
                "merged": True,
                "head": {"ref": "feature/DW-1-dev-panel"},
                "user": {"login": "octo"},
            }
        },
        "pull_request",
    )
    db.commit()

    assert len(links) == 1
    dev_links = list_task_dev_links(task.id, db=db, current_user=manager)
    assert dev_links[0]["link_type"] == "pr"
    assert dev_links[0]["status"] == "merged"
    db.refresh(task)
    assert task.status == "Done"
    actions = {activity.action for activity in db.query(PMSActivity).filter(PMSActivity.task_id == task.id).all()}
    assert "development.link_added" in actions
    assert "status.changed" in actions

    delete_dev_integration(integration.id, db=db, current_user=manager)
    assert list_dev_integrations(projectId=project.id, db=db, current_user=manager) == []


def test_portfolio_dashboard_is_accessible_scoped_and_calculates_health(db):
    manager = _user(db, "pms-portfolio-manager@example.com", ["pms_manage_projects"])
    outsider = _user(db, "pms-portfolio-outsider@example.com")
    client = create_client(
        PMSClientCreate(name="Acme Portfolio", company_name="Acme"),
        db=db,
        current_user=manager,
    )
    project = create_project(
        PMSProjectCreate(
            name="Portfolio Delivery",
            project_key="PD",
            client_id=client.id,
            manager_user_id=manager.id,
            status="Active",
            start_date=date.today() - timedelta(days=45),
            due_date=date.today() - timedelta(days=10),
            progress_percent=40,
            budget_amount=100000,
        ),
        db=db,
        current_user=manager,
    )
    create_task(
        project.id,
        PMSTaskCreate(
            title="Late executive task",
            task_key="PD-1",
            status="In Progress",
            due_date=date.today() - timedelta(days=15),
            estimated_hours=12,
        ),
        db=db,
        current_user=manager,
    )
    create_task(
        project.id,
        PMSTaskCreate(
            title="Blocked launch task",
            task_key="PD-2",
            status="Blocked",
            is_blocking=True,
            estimated_hours=8,
        ),
        db=db,
        current_user=manager,
    )

    summary = get_portfolio_summary(ownerId=None, clientId=None, status=None, db=db, current_user=manager)
    assert summary["total_projects"] == 1
    assert summary["active_projects"] == 1
    assert summary["total_open_tasks"] == 2
    assert summary["team_workload_summary"]["open_estimated_hours"] == 20
    assert summary["at_risk_projects"] == 1

    projects = get_portfolio_projects(ownerId=None, clientId=None, status=None, health="Blocked", db=db, current_user=manager)
    assert projects["items"][0]["client_name"] == "Acme Portfolio"
    assert projects["items"][0]["health"] == "Blocked"
    assert projects["items"][0]["overdue_tasks"] >= 1

    trend = get_portfolio_health_trend(ownerId=None, clientId=None, status=None, db=db, current_user=manager)
    assert len(trend["items"]) == 6

    outsider_summary = get_portfolio_summary(ownerId=None, clientId=None, status=None, db=db, current_user=outsider)
    assert outsider_summary["total_projects"] == 0


def test_pms_risk_register_is_project_scoped_and_affects_health(db):
    manager = _user(db, "pms-risk-manager@example.com", ["pms_manage_projects"])
    outsider = _user(db, "pms-risk-outsider@example.com")
    project = create_project(
        PMSProjectCreate(name="Risky Project", project_key="RISK", status="Active"),
        db=db,
        current_user=manager,
    )
    task = create_task(
        project.id,
        PMSTaskCreate(title="Mitigate vendor exposure", task_key="RISK-1"),
        db=db,
        current_user=manager,
    )

    risk = create_risk(
        PMSRiskCreate(
            project_id=project.id,
            linked_task_id=task.id,
            title="Vendor delay could block launch",
            category="Delivery",
            probability=5,
            impact=4,
            status="open",
            owner_user_id=manager.id,
            mitigation_plan="Line up a backup vendor.",
            contingency_plan="Reduce launch scope.",
            due_date=date.today() + timedelta(days=7),
        ),
        db=db,
        current_user=manager,
    )

    assert risk.risk_score == 20
    assert list_risks(projectId=project.id, status=None, ownerId=None, severity="high", db=db, current_user=manager)[0].id == risk.id
    dashboard = get_project_dashboard(project.id, db=db, current_user=manager)
    assert dashboard["metrics"]["high_risks"] == 1
    projects = get_portfolio_projects(ownerId=None, clientId=None, status=None, health="Blocked", db=db, current_user=manager)
    assert projects["items"][0]["open_high_risks"] == 1

    with pytest.raises(HTTPException) as exc:
        list_risks(projectId=project.id, status=None, ownerId=None, severity=None, db=db, current_user=outsider)
    assert exc.value.status_code == 403

    updated = update_risk(risk.id, PMSRiskUpdate(status="closed", probability=2), db=db, current_user=manager)
    assert updated.status == "closed"
    assert updated.risk_score == 8
    assert list_risks(projectId=project.id, status="open", ownerId=None, severity=None, db=db, current_user=manager) == []

    delete_risk(risk.id, db=db, current_user=manager)
    assert list_risks(projectId=project.id, status=None, ownerId=None, severity=None, db=db, current_user=manager) == []

    actions = {activity.action for activity in db.query(PMSActivity).filter(PMSActivity.project_id == project.id).all()}
    assert {"risk.created", "risk.updated", "risk.deleted"}.issubset(actions)


def test_pms_reports_are_real_data_and_access_scoped(db):
    manager = _user(db, "pms-reports-manager@example.com", ["pms_manage_projects"])
    outsider = _user(db, "pms-reports-outsider@example.com")
    project = create_project(
        PMSProjectCreate(name="Reports Project", project_key="RPT"),
        db=db,
        current_user=manager,
    )
    sprint = create_sprint(
        project.id,
        PMSSprintCreate(name="Sprint Reports", start_date=date.today() - timedelta(days=7), end_date=date.today() + timedelta(days=7)),
        db=db,
        current_user=manager,
    )
    task = create_task(
        project.id,
        PMSTaskCreate(task_key="RPT-1", title="Reportable work", status="To Do", priority="High", sprint_id=sprint.id, story_points=5, assignee_user_id=manager.id),
        db=db,
        current_user=manager,
    )
    update_task(task.id, PMSTaskUpdate(status="In Progress"), db=db, current_user=manager)
    update_task(task.id, PMSTaskUpdate(status="Done"), db=db, current_user=manager)
    complete_sprint(sprint.id, SprintCompleteRequest(), db=db, current_user=manager)

    distribution = report_task_distribution(projectId=project.id, assigneeId=None, from_=None, to=None, db=db, current_user=manager)
    assert distribution["total_tasks"] == 1
    assert distribution["by_status"][0]["story_points"] == 5

    flow = report_cumulative_flow(projectId=project.id, from_=date.today() - timedelta(days=1), to=date.today(), db=db, current_user=manager)
    assert flow["points"]
    cycle = report_cycle_time(
        projectId=project.id,
        assigneeId=None,
        from_=date.today() - timedelta(days=1),
        to=date.today(),
        db=db,
        current_user=manager,
    )
    assert cycle["items"][0]["task_key"] == "RPT-1"
    time_status = report_time_in_status(projectId=project.id, from_=date.today() - timedelta(days=1), to=date.today(), db=db, current_user=manager)
    assert any(item["status"] == "Done" for item in time_status["statuses"])
    team = report_team_performance(projectId=project.id, sprintId=sprint.id, db=db, current_user=manager)
    assert team["items"][0]["completed_points"] == 5
    health = report_project_health(projectId=project.id, from_=date.today() - timedelta(days=7), to=date.today(), db=db, current_user=manager)
    assert health["points"]

    outsider_distribution = report_task_distribution(projectId=project.id, assigneeId=None, from_=None, to=None, db=db, current_user=outsider)
    assert outsider_distribution["total_tasks"] == 0


def test_sprint_review_retro_completion_and_action_items(db):
    manager = _user(db, "sprint-review@example.com", ["pms_manage_projects"])
    outsider = _user(db, "sprint-review-outsider@example.com")
    project = create_project(
        PMSProjectCreate(name="Sprint Review Project", project_key="SRP"),
        db=db,
        current_user=manager,
    )
    sprint = create_sprint(
        project.id,
        PMSSprintCreate(name="Sprint Review", start_date=date.today() - timedelta(days=7), end_date=date.today()),
        db=db,
        current_user=manager,
    )
    next_sprint = create_sprint(
        project.id,
        PMSSprintCreate(name="Next Sprint", start_date=date.today() + timedelta(days=1), end_date=date.today() + timedelta(days=14)),
        db=db,
        current_user=manager,
    )
    done_task = create_task(
        project.id,
        PMSTaskCreate(task_key="SRP-1", title="Completed story", status="Done", sprint_id=sprint.id, story_points=5),
        db=db,
        current_user=manager,
    )
    unfinished_task = create_task(
        project.id,
        PMSTaskCreate(task_key="SRP-2", title="Carry forward story", status="In Progress", sprint_id=sprint.id, story_points=3),
        db=db,
        current_user=manager,
    )
    start_sprint(sprint.id, db=db, current_user=manager)

    completed = complete_sprint(
        sprint.id,
        SprintCompleteRequest(
            carry_forward_sprint_id=next_sprint.id,
            incomplete_action="move_to_next_sprint",
            review_notes="Demo accepted by stakeholders.",
            retrospective_notes="Keep QA involved earlier.",
            what_went_well="Scope stayed stable.",
            what_did_not_go_well="Late test data.",
            outcome="Release candidate approved",
            action_items=[{"title": "Prepare test data checklist", "due_date": str(date.today() + timedelta(days=3))}],
            create_action_item_tasks=True,
        ),
        db=db,
        current_user=manager,
    )

    assert completed.status == "Completed"
    assert completed.completed_by_user_id == manager.id
    assert completed.completed_story_points == 5
    assert completed.outcome == "Release candidate approved"
    db.refresh(unfinished_task)
    assert unfinished_task.sprint_id == next_sprint.id

    review = get_sprint_review(sprint.id, db=db, current_user=manager)
    assert review["sprint"].review_notes == "Demo accepted by stakeholders."
    assert review["completed_tasks"][0]["id"] == done_task.id
    assert review["incomplete_tasks"] == []
    assert len(review["action_items"]) == 1
    assert review["action_items"][0].created_task_id is not None

    updated = update_sprint_review(
        sprint.id,
        SprintCompleteRequest(
            incomplete_action="keep_in_sprint",
            review_notes="Final notes updated.",
            retrospective_notes="Retro notes updated.",
            outcome="Closed with follow-ups",
            action_items=[{"title": "Review carry-forward scope"}],
        ),
        db=db,
        current_user=manager,
    )
    assert updated["sprint"].review_notes == "Final notes updated."
    assert updated["sprint"].outcome == "Closed with follow-ups"
    assert updated["action_items"][0].title == "Review carry-forward scope"

    with pytest.raises(HTTPException):
        get_sprint_review(sprint.id, db=db, current_user=outsider)


def test_market_gap_api_additions_for_sprints_dependencies_filters_and_reports(db):
    manager = _user(db, "pms-gap-manager@example.com", ["pms_manage_projects"])
    project = create_project(
        PMSProjectCreate(name="Market Gap APIs", project_key="MG"),
        db=db,
        current_user=manager,
    )
    release = create_release(
        project.id,
        PMSReleaseCreate(name="v3.0", status="Planning", readiness_percent=40),
        db=db,
        current_user=manager,
    )
    sprint = create_sprint(
        project.id,
        PMSSprintCreate(name="Sprint Gap", start_date="2026-05-07", end_date="2026-05-21", capacity_hours=40),
        db=db,
        current_user=manager,
    )
    blocker = create_task(
        project.id,
        PMSTaskCreate(title="Critical blocker", task_key="MG-1", work_type="Bug", severity="S1", story_points=5, release_id=release.id),
        db=db,
        current_user=manager,
    )
    dependent = create_task(
        project.id,
        PMSTaskCreate(title="Dependent story", task_key="MG-2", work_type="Story", story_points=8),
        db=db,
        current_user=manager,
    )

    dependency = add_task_dependency(
        dependent.id,
        PMSTaskDependencyCreate(depends_on_task_id=blocker.id),
        db=db,
        current_user=manager,
    )
    assert dependency.depends_on_task_id == blocker.id

    bulk = bulk_update_tasks(
        TaskBulkUpdateRequest(task_ids=[blocker.id, dependent.id], sprint_id=sprint.id, release_id=release.id),
        db=db,
        current_user=manager,
    )
    assert bulk["updated_count"] == 2

    started = start_sprint(sprint.id, db=db, current_user=manager)
    assert started.status == "Active"
    assert started.committed_story_points == 13

    blocker.status = "Done"
    db.add(blocker)
    db.commit()
    completed = complete_sprint(
        sprint.id,
        SprintCompleteRequest(),
        db=db,
        current_user=manager,
    )
    assert completed.status == "Completed"
    assert completed.velocity_points == 5

    velocity = get_project_velocity(project.id, db=db, current_user=manager)
    assert velocity["average_velocity_points"] == 5

    saved = create_saved_filter(
        project.id,
        PMSSavedFilterCreate(name="Critical release bugs", view_type="backlog", query="severity = S1 AND release = v3.0"),
        db=db,
        current_user=manager,
    )
    assert saved.name == "Critical release bugs"

    readiness = get_release_readiness(release.id, db=db, current_user=manager)
    assert readiness["total_tasks"] == 2
    assert readiness["severity_counts"]["S1"] == 1

    workload = get_project_workload(project.id, group_by="sprint", sprint_id=None, db=db, current_user=manager)
    assert workload["group_by"] == "sprint"

    activity = list_project_activity(project.id, task_id=None, limit=20, db=db, current_user=manager)
    assert any(item.action == "dependency.added" for item in activity)


def test_trash_restore_enforces_project_access(db):
    from app.apps.project_management.api.router import list_trashed_tasks, restore_trashed_task
    manager = _user(db, "trash-manager@example.com", ["pms_manage_projects"])
    outsider = _user(db, "trash-outsider@example.com")
    project = create_project(PMSProjectCreate(name="Recovery", project_key="REC"), db=db, current_user=manager)
    task = create_task(project.id, PMSTaskCreate(title="Recover me", task_key="REC-1"), db=db, current_user=manager)
    delete_task(task.id, db=db, current_user=manager)
    assert [row["id"] for row in list_trashed_tasks(db=db, current_user=manager)] == [task.id]
    assert list_trashed_tasks(db=db, current_user=outsider) == []
    with pytest.raises(HTTPException) as denied:
        restore_trashed_task(task.id, db=db, current_user=outsider)
    assert denied.value.status_code == 403
    assert task.deleted_at is not None
    restore_trashed_task(task.id, db=db, current_user=manager)
    assert task.deleted_at is None
    assert list_trashed_tasks(db=db, current_user=manager) == []


def test_custom_fields_validate_types_and_project_scope(db):
    from app.apps.project_management.custom_fields import create_field, save_value, task_fields, FieldInput, ValueInput
    manager = _user(db, "field-manager@example.com", ["pms_manage_projects"])
    outsider = _user(db, "field-outsider@example.com")
    project = create_project(PMSProjectCreate(name="Fields", project_key="FLD"), db=db, current_user=manager)
    other = create_project(PMSProjectCreate(name="Other fields", project_key="OTH"), db=db, current_user=manager)
    task = create_task(project.id, PMSTaskCreate(title="Client return", task_key="FLD-1"), db=db, current_user=manager)
    definition = create_field(project.id, FieldInput(name="Tax period", field_type="dropdown", options=["2025", "2026"]), db=db, user=manager)
    save_value(task.id, definition["id"], ValueInput(value="2026"), db=db, user=manager)
    assert task_fields(task.id, db=db, user=manager)["fields"][0]["value"] == "2026"
    with pytest.raises(HTTPException) as invalid:
        save_value(task.id, definition["id"], ValueInput(value="invalid"), db=db, user=manager)
    assert invalid.value.status_code == 422
    foreign = create_field(other.id, FieldInput(name="Other", field_type="text"), db=db, user=manager)
    with pytest.raises(HTTPException) as cross_project:
        save_value(task.id, foreign["id"], ValueInput(value="bad"), db=db, user=manager)
    assert cross_project.value.status_code == 404
    with pytest.raises(HTTPException) as denied:
        task_fields(task.id, db=db, user=outsider)
    assert denied.value.status_code == 403
    for field_type, valid, invalid in [("number", 12.5, "no"), ("date", "2026-10-23", "2026-02-30"), ("checkbox", True, "true")]:
        field = create_field(project.id, FieldInput(name=field_type, field_type=field_type), db=db, user=manager)
        save_value(task.id, field["id"], ValueInput(value=valid), db=db, user=manager)
        with pytest.raises(HTTPException) as bad:
            save_value(task.id, field["id"], ValueInput(value=invalid), db=db, user=manager)
        assert bad.value.status_code == 422

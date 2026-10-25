"""Module adapters. The forms engine itself never imports a product model."""

from datetime import date, timedelta
from fastapi import HTTPException


def validate(db, definition, owner, module_key):
    if not definition.workflow.enabled:
        return
    if module_key != "pms":
        raise HTTPException(422, "Task intake is available in PMS forms")
    from app.apps.project_management.access import get_project_for_action

    get_project_for_action(db, definition.workflow.project_id, owner, "manage_tasks")
    if definition.workflow.assignee_id:
        from app.apps.project_management.models import PMSProjectMember

        if (
            not db.query(PMSProjectMember)
            .filter_by(
                project_id=definition.workflow.project_id,
                user_id=definition.workflow.assignee_id,
            )
            .first()
        ):
            raise HTTPException(422, "Assignee must belong to the workflow project")


def on_response(db, definition, answers, owner, module_key, request_id):
    if not definition.workflow.enabled:
        return None
    validate(db, definition, owner, module_key)
    from app.apps.project_management.models import (
        PMSBoard,
        PMSBoardColumn,
        PMSTask,
        PMSProject,
        PMSActivity,
    )
    from app.apps.project_management.automations import apply_task_rules

    w = definition.workflow
    project = db.get(PMSProject, w.project_id)
    board = (
        db.query(PMSBoard)
        .filter_by(project_id=project.id)
        .order_by(PMSBoard.id)
        .first()
    )
    if not board:
        board = PMSBoard(
            project_id=project.id, name="Default Board", board_type="Kanban"
        )
        db.add(board)
        db.flush()
    column = (
        db.query(PMSBoardColumn).filter_by(board_id=board.id, status_key="TODO").first()
    )
    if not column:
        column = PMSBoardColumn(
            board_id=board.id, name="To Do", status_key="TODO", position=1
        )
        db.add(column)
        db.flush()
    description = "\n\n".join(
        f"{f.label}: {answers[f.id]}" for f in definition.fields if f.id in answers
    )
    task = PMSTask(
        project_id=project.id,
        board_id=board.id,
        column_id=column.id,
        task_key="FORM-" + request_id.hex[:24].upper(),
        title=str(answers[w.title_field])[:220],
        description=description,
        reporter_user_id=owner.id,
        status="To Do",
        priority=w.priority,
        due_date=(
            date.today() + timedelta(days=w.due_days)
            if w.due_days is not None
            else None
        ),
        position=0,
        rank=1,
    )
    if w.assignee_id:
        task.assignee_user_ids = [w.assignee_id]
    db.add(task)
    db.flush()
    apply_task_rules(db, task, project, owner, "task.created")
    db.add(
        PMSActivity(
            project_id=project.id,
            task_id=task.id,
            actor_user_id=owner.id,
            action="task.created",
            entity_type="task",
            entity_id=task.id,
            summary=f"Created from public form: {definition.name}"[:300],
        )
    )
    return task.id


def options(db, user, module_key):
    if module_key != "pms":
        return {"projects": []}
    from app.apps.project_management.access import (
        accessible_project_query,
        get_project_for_action,
    )

    projects = []
    for project in accessible_project_query(db, user).limit(200).all():
        try:
            get_project_for_action(db, project.id, user, "manage_tasks")
        except HTTPException:
            continue
        projects.append({"id": project.id, "name": project.name})
    return {"projects": projects}

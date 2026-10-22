"""Disposable real-PostgreSQL server for whole-suite browser regression.

The fixed *_test database is recreated; the application database is untouched.
"""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")

if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from app.core.config import settings
    source = make_url(settings.SQLALCHEMY_DATABASE_URI)
    if source.get_backend_name() != "postgresql":
        raise RuntimeError("Browser regression requires PostgreSQL")
    target = source.set(database="business_suite_browser_test")
    admin = create_engine(source.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.exec_driver_sql('DROP DATABASE IF EXISTS "business_suite_browser_test" WITH (FORCE)')
        connection.exec_driver_sql('CREATE DATABASE "business_suite_browser_test"')
    admin.dispose()
    settings.DATABASE_URL = target.render_as_string(hide_password=False)
    settings.ENVIRONMENT = "test"
    settings.DEBUG = False
    settings.INSTALLED_APPS = ["hrms", "crm", "project_management", "srm", "fam"]
    settings.BACKEND_CORS_ORIGINS = ["http://127.0.0.1:5181", "http://127.0.0.1:5182"]
    from app.db.migrations import upgrade_schema
    upgrade_schema()
    from app.main import app
    from app.db.session import SessionLocal, engine
    from app.models.user import User, Role
    from app.core.security import get_password_hash
    with SessionLocal() as db:
        from app.db.init_db import init_db
        init_db(db)
        from app.apps.business_os.services.module_service import ensure_business_os_seed
        ensure_business_os_seed(db, 1)
        for name, email, admin in [("pms_admin", "owner@example.com", True), ("employee", "member@example.com", False)]:
            role = db.query(Role).filter_by(name=name).first()
            if not role:
                role = Role(name=name)
                db.add(role)
                db.flush()
            db.add(User(email=email, hashed_password=get_password_hash("WorkspaceQA@123"), role_id=role.id, is_active=True, is_superuser=admin))
        db.commit()
        from datetime import date, timedelta
        from app.apps.project_management.models import PMSWorkspace, PMSWorkspaceMember, PMSProject, PMSBoard, PMSBoardColumn, PMSTask
        owner = db.query(User).filter_by(email="owner@example.com").one()
        workspace = PMSWorkspace(name="Product studio")
        db.add(workspace)
        db.flush()
        db.add(PMSWorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role="Owner"))
        demo_users = []
        employee_role = db.query(Role).filter_by(name="employee").one()
        for email in ["maya.desai@example.com", "arjun.rao@example.com", "priya.shah@example.com"]:
            person = User(email=email, hashed_password="qa-only-disabled", is_active=True, role_id=employee_role.id)
            db.add(person)
            db.flush()
            db.add(PMSWorkspaceMember(workspace_id=workspace.id, user_id=person.id, role="Member"))
            demo_users.append(person)
        demo_projects = []
        for key, title in [("LCH", "Product launch"), ("WEB", "Website refresh"), ("CEX", "Customer experience")]:
            project = PMSProject(name=title, project_key=key, workspace_id=workspace.id, owner_user_id=owner.id, status="Active")
            db.add(project)
            db.flush()
            board = PMSBoard(project_id=project.id, name=title, board_type="Kanban")
            db.add(board)
            db.flush()
            columns = {}
            for index, (status, status_key) in enumerate([("To Do", "TODO"), ("In Progress", "IN_PROGRESS"), ("In Review", "IN_REVIEW"), ("Done", "DONE")]):
                column = PMSBoardColumn(board_id=board.id, name=status, status_key=status_key, position=index)
                db.add(column)
                db.flush()
                columns[status] = column.id
            demo_projects.append((project, board, columns))
        samples = [
            (0, "Shape the launch story", "To Do", "High", "Bring positioning, audience insights, and the big idea into one clear narrative."),
            (1, "Explore a fresh visual direction", "To Do", "Medium", "A calmer, more thoughtful first impression for our next chapter."),
            (2, "Map the onboarding journey", "To Do", "Low", ""),
            (1, "Build the new landing page", "In Progress", "High", "Turn the approved direction into a fast, accessible experience."),
            (0, "Bring the product demo to life", "In Progress", "Medium", "A two-minute walkthrough of the moments that matter."),
            (2, "Review the welcome emails", "In Review", "Medium", "A warm welcome. A useful next step. Nothing more."),
            (1, "Check mobile layouts", "In Review", "High", ""),
            (0, "Align the team on milestones", "Done", "Low", ""),
            (2, "Gather customer conversations", "Done", "Medium", "Everything we learned, ready for the team."),
        ]
        for index, (project_index, title, status, priority, description) in enumerate(samples):
            project, board, columns = demo_projects[project_index]
            db.add(PMSTask(project_id=project.id, board_id=board.id, column_id=columns[status], task_key=f"{project.project_key}-{index+1}", title=title, description=description, status=status, priority=priority, assignee_user_id=demo_users[index % 3].id if index != 2 else None, start_date=date(2026, 10, 22), due_date=date(2026, 10, 22) + timedelta(days=index+1), position=index))
        db.commit()
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8766)

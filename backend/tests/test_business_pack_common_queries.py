"""Mapper identities, not table aliases/names, delimit a native graph."""
import pytest
from fastapi import HTTPException
from sqlalchemy import select,func,true
from sqlalchemy.orm import aliased,joinedload,registry,Load
from app.models.employee import Employee
from app.models.attendance import Attendance
from app.models.user import User,Role,Permission,role_permissions
from app.business_packs.common_queries import assert_mapped_sources


def denied(statement,models,**kwargs):
    with pytest.raises(HTTPException) as error:assert_mapped_sources(statement,models,**kwargs)
    assert error.value.status_code==403


@pytest.mark.parametrize('shape',['entity','projection','alias','join','count'])
def test_known_alias_projection_join_and_scoped_count_remain_valid(shape):
    alias=aliased(Employee)
    statements={'entity':select(Employee),'projection':select(Employee.id),'alias':select(alias),
        'join':select(Employee).join(alias,alias.reporting_manager_id==Employee.id),
        'count':select(func.count()).select_from(select(Employee).subquery())}
    assert_mapped_sources(statements[shape],{Employee})


@pytest.mark.parametrize('shape',['mixed','alias','count','join'])
def test_unknown_mapper_in_secondary_source_is_never_inherited_from_primary_mapper(shape):
    unknown=aliased(Attendance)
    statement={'mixed':select(Employee,Attendance),
        'alias':select(Employee,unknown),
        'count':select(func.count()).select_from(select(Employee,unknown).subquery()),
        'join':select(Employee).join(Attendance,Attendance.employee_id==Employee.id)}[shape]
    denied(statement,{Employee})


def test_late_alternate_mapper_over_same_table_has_no_registered_class_authority():
    alternate=registry()
    class AlternateAttendance:pass
    alternate.map_imperatively(AlternateAttendance,Attendance.__table__)
    try:
        denied(select(Employee,AlternateAttendance),{Employee,Attendance})
        denied(select(Employee,aliased(AlternateAttendance)),{Employee,Attendance},trusted_identity=True)
    finally:alternate.dispose()


def test_unannotated_raw_join_cannot_leak_private_existence_through_known_rows():
    denied(select(Employee).join(Attendance.__table__,true()),{Employee})
    alias=aliased(Employee)
    denied(select(alias).join(Employee.__table__,true()),{Employee})


def test_raw_alias_is_not_scoped_by_same_physical_model_name():
    raw=Employee.__table__.alias('otherwise_unscoped_employee')
    denied(select(Employee).join(raw,true()),{Employee})


def test_registered_model_alias_cannot_relabel_another_table_as_employment():
    disguised=aliased(Employee,Attendance.__table__.alias(),adapt_on_names=True)
    denied(select(disguised),{Employee,Attendance})


def test_scoped_outer_model_does_not_certify_raw_same_table_inside_subquery():
    disguised=aliased(Employee,select(Employee.__table__).subquery(),adapt_on_names=True)
    denied(select(Employee,disguised),{Employee})
    scoped=aliased(Employee,select(Employee).subquery())
    assert_mapped_sources(select(scoped),{Employee})


def test_eager_paths_and_nested_load_options_must_be_registered():
    denied(select(User).options(joinedload(User.employee)),{User})
    denied(select(User).options(Load(User).options(joinedload(User.employee))),{User})
    denied(select(User).options(joinedload('*')),{User})
    assert_mapped_sources(select(User).options(joinedload(User.employee)),{User,Employee})


def test_protective_raiseload_is_not_a_data_source_grant():
    assert_mapped_sources(select(User).options(Load(User).raiseload('*')),{User})


def test_explicit_authorization_association_is_required_and_read_only():
    statement=select(Permission).join(role_permissions,role_permissions.c.permission_id==Permission.id)
    denied(statement,{Permission})
    assert_mapped_sources(statement,{Permission},allowed_associations=(role_permissions,))


def test_actual_legacy_orm_query_count_retains_its_scoped_source(db):
    from sqlalchemy import event
    statements=[]
    def capture(execution):statements.append(execution.statement)
    event.listen(db,'do_orm_execute',capture)
    try:db.query(Employee).count()
    finally:event.remove(db,'do_orm_execute',capture)
    assert len(statements)==1
    assert_mapped_sources(statements[0],{Employee})


def test_truthy_fake_mapper_annotations_do_not_certify_raw_private_columns():
    from types import SimpleNamespace
    fake=Attendance.__table__.c.remarks._annotate({'parentmapper':SimpleNamespace(class_=Employee)})
    denied(select(Employee).where(fake=='private'),{Employee})


def test_real_mapper_annotation_on_a_raw_alias_does_not_bind_orm_scope():
    from sqlalchemy import inspect
    raw=Employee.__table__.alias('not_an_orm_employee')
    fake=raw.c.first_name._annotate({'parentmapper':inspect(Employee)})
    denied(select(Employee).where(fake=='private'),{Employee})


def test_native_projected_query_keeps_its_memoized_orm_join(db):
    from app.models.employee import EmployeeEducation
    query=db.query(EmployeeEducation).join(Employee).filter(Employee.deleted_at.is_(None)).with_entities(EmployeeEducation.pass_year).distinct()
    assert_mapped_sources(query.statement,{EmployeeEducation,Employee})


def test_native_relationship_any_keeps_exact_correlated_mapped_sources():
    from app.models.employee import EmployeeEducation
    statement=select(Employee).where(Employee.educations.any(EmployeeEducation.pass_year==2026))
    assert_mapped_sources(statement,{Employee,EmployeeEducation})
    denied(statement,{Employee})


def test_native_directory_scoped_count_with_mapped_id_filter(db):
    from sqlalchemy import event
    from app.models.employee import EmployeeEducation
    from app.business_packs.employee_core import _count_stars
    statements=[]
    def capture(execution):statements.append(execution.statement)
    event.listen(db,'do_orm_execute',capture)
    try:db.query(Employee).filter(Employee.id.in_(select(EmployeeEducation.employee_id).where(EmployeeEducation.pass_year==2026))).count()
    finally:event.remove(db,'do_orm_execute',capture)
    assert len(statements)==1
    assert_mapped_sources(statements[0],{Employee,EmployeeEducation})
    assert len(_count_stars(statements[0]))==1

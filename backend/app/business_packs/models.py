"""Pack configuration and immutable native-record anchors; no duplicate ledgers.

These models do not activate packs, grant native permissions, register routes or
change existing ORM boundaries. Services must validate the real Branch.company_id,
installed manifest/version, role, native master ownership and actor authority.
Context identity is permanent. A later primary-selection reference may point to a
different context; neither the old context nor its source records may be retagged.
"""
import re

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey,
    ForeignKeyConstraint, Integer, String, UniqueConstraint, event, inspect, select,
)
from sqlalchemy.orm import validates
from sqlalchemy.sql import func
from app.db.base_class import Base


PACK_STATES = ('draft', 'active', 'suspended', 'retired')
_KEY = re.compile(r'[a-z][a-z0-9_]{0,63}\Z', re.ASCII)
_TABLE = re.compile(r'[a-z][a-z0-9_]{0,119}\Z', re.ASCII)


class PackIdentityError(ValueError):
    """An immutable context/native-record identity was changed."""


class PackRevisionError(ValueError):
    """A manually supplied revision does not advance exactly once."""


class _Validated:
    @validates('pack_key', 'role')
    def _key(self, name, value):
        if not isinstance(value, str) or not _KEY.fullmatch(value):
            raise ValueError(f'Invalid Business Pack {name}')
        return value

    @validates('resource_table')
    def _table(self, name, value):
        if not isinstance(value, str) or not _TABLE.fullmatch(value):
            raise ValueError('Invalid native resource table')
        return value

    @validates('resource_key', 'source')
    def _text(self, name, value):
        maximum = 500 if name == 'resource_key' else 80
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError(f'Invalid native resource {name}')
        return value

    @validates('pack_version', 'revision')
    def _positive(self, name, value):
        if type(value) is not int or value < 1:
            raise ValueError(f'Business Pack {name} must be a positive integer')
        return value

    @validates('state')
    def _state(self, name, value):
        if value not in PACK_STATES:
            raise ValueError('Invalid Business Pack state')
        return value


class PackActivation(_Validated, Base):
    __tablename__ = 'business_pack_activations'
    __table_args__ = (
        UniqueConstraint('company_id', 'pack_key', 'pack_version', name='uq_pack_activation_version'),
        UniqueConstraint('id', 'company_id', 'pack_key', 'pack_version', name='uq_pack_activation_identity'),
        CheckConstraint("state IN ('draft','active','suspended','retired')", name='ck_pack_activation_state'),
        CheckConstraint('pack_version > 0', name='ck_pack_activation_version'),
        CheckConstraint('revision > 0', name='ck_pack_activation_revision'),
        CheckConstraint('length(trim(pack_key)) BETWEEN 1 AND 64', name='ck_pack_activation_key'),
    )
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='RESTRICT'), nullable=False)
    pack_key = Column(String(64), nullable=False)
    pack_version = Column(Integer, nullable=False, default=1, server_default='1')
    state = Column(String(20), nullable=False, default='draft', server_default='draft')
    revision = Column(Integer, nullable=False, default=1, server_default='1')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __mapper_args__ = {'version_id_col': revision}


class PackContext(_Validated, Base):
    __tablename__ = 'business_pack_contexts'
    __table_args__ = (
        UniqueConstraint('activation_id', 'branch_id', name='uq_pack_context_activation_branch'),
        UniqueConstraint('id', 'company_id', 'branch_id', name='uq_pack_context_identity'),
        ForeignKeyConstraint(
            ['activation_id', 'company_id', 'pack_key', 'pack_version'],
            ['business_pack_activations.id', 'business_pack_activations.company_id', 'business_pack_activations.pack_key', 'business_pack_activations.pack_version'],
            name='fk_pack_context_activation_identity', ondelete='RESTRICT',
        ),
        CheckConstraint("state IN ('draft','active','suspended','retired')", name='ck_pack_context_state'),
        CheckConstraint('pack_version > 0', name='ck_pack_context_version'),
        CheckConstraint('revision > 0', name='ck_pack_context_revision'),
        CheckConstraint('length(trim(pack_key)) BETWEEN 1 AND 64', name='ck_pack_context_key'),
    )
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='RESTRICT'), nullable=False)
    branch_id = Column(Integer, ForeignKey('branches.id', ondelete='RESTRICT'), nullable=False)
    activation_id = Column(Integer, nullable=False)
    pack_key = Column(String(64), nullable=False)
    pack_version = Column(Integer, nullable=False)
    state = Column(String(20), nullable=False, default='draft', server_default='draft')
    ever_activated = Column(Boolean(create_constraint=True, name='ck_pack_context_ever_activated'), nullable=False, default=False, server_default='false')
    revision = Column(Integer, nullable=False, default=1, server_default='1')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __mapper_args__ = {'version_id_col': revision}


class PackUserGrant(_Validated, Base):
    __tablename__ = 'business_pack_user_grants'
    __table_args__ = (
        UniqueConstraint('context_id', 'user_id', name='uq_pack_user_context'),
        ForeignKeyConstraint(
            ['context_id', 'company_id', 'branch_id'],
            ['business_pack_contexts.id', 'business_pack_contexts.company_id', 'business_pack_contexts.branch_id'],
            name='fk_pack_user_grant_context', ondelete='RESTRICT',
        ),
        CheckConstraint('revision > 0', name='ck_pack_user_grant_revision'),
        CheckConstraint('length(trim(role)) BETWEEN 1 AND 64', name='ck_pack_user_grant_role'),
    )
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='RESTRICT'), nullable=False)
    branch_id = Column(Integer, ForeignKey('branches.id', ondelete='RESTRICT'), nullable=False)
    context_id = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    role = Column(String(64), nullable=False)
    active = Column(Boolean(create_constraint=True, name='ck_pack_user_grant_active'), nullable=False, default=True, server_default='true')
    revision = Column(Integer, nullable=False, default=1, server_default='1')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __mapper_args__ = {'version_id_col': revision}


class PackRecordOwnership(_Validated, Base):
    """Append-only anchor to a native source; shared definitions use availability."""
    __tablename__ = 'business_pack_record_ownership'
    __table_args__ = (
        UniqueConstraint('resource_table', 'resource_key', name='uq_pack_native_record_anchor'),
        ForeignKeyConstraint(
            ['context_id', 'company_id', 'branch_id'],
            ['business_pack_contexts.id', 'business_pack_contexts.company_id', 'business_pack_contexts.branch_id'],
            name='fk_pack_record_context', ondelete='RESTRICT',
        ),
        CheckConstraint('revision > 0', name='ck_pack_record_revision'),
        CheckConstraint('length(trim(resource_table)) BETWEEN 1 AND 120', name='ck_pack_record_table'),
        CheckConstraint('length(trim(resource_key)) BETWEEN 1 AND 500', name='ck_pack_record_key'),
        CheckConstraint('length(trim(source)) BETWEEN 1 AND 80', name='ck_pack_record_source'),
    )
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='RESTRICT'), nullable=False)
    branch_id = Column(Integer, ForeignKey('branches.id', ondelete='RESTRICT'), nullable=False)
    context_id = Column(Integer, nullable=False)
    resource_table = Column(String(120), nullable=False)
    resource_key = Column(String(500), nullable=False)
    source = Column(String(80), nullable=False, default='created', server_default='created')
    revision = Column(Integer, nullable=False, default=1, server_default='1')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __mapper_args__ = {'version_id_col': revision}


class PackMasterAvailability(_Validated, Base):
    """Explicit availability of an existing native master in one exact context."""
    __tablename__ = 'business_pack_master_availability'
    __table_args__ = (
        UniqueConstraint('context_id', 'resource_table', 'resource_key', name='uq_pack_master_context'),
        ForeignKeyConstraint(
            ['context_id', 'company_id', 'branch_id'],
            ['business_pack_contexts.id', 'business_pack_contexts.company_id', 'business_pack_contexts.branch_id'],
            name='fk_pack_master_context', ondelete='RESTRICT',
        ),
        CheckConstraint('revision > 0', name='ck_pack_master_revision'),
        CheckConstraint('length(trim(resource_table)) BETWEEN 1 AND 120', name='ck_pack_master_table'),
        CheckConstraint('length(trim(resource_key)) BETWEEN 1 AND 500', name='ck_pack_master_key'),
    )
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='RESTRICT'), nullable=False)
    branch_id = Column(Integer, ForeignKey('branches.id', ondelete='RESTRICT'), nullable=False)
    context_id = Column(Integer, nullable=False)
    resource_table = Column(String(120), nullable=False)
    resource_key = Column(String(500), nullable=False)
    active = Column(Boolean(create_constraint=True, name='ck_pack_master_active'), nullable=False, default=True, server_default='true')
    revision = Column(Integer, nullable=False, default=1, server_default='1')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __mapper_args__ = {'version_id_col': revision}


_IDENTITY = {
    PackActivation: ('id', 'company_id', 'pack_key', 'pack_version'),
    PackContext: ('id', 'company_id', 'branch_id', 'activation_id', 'pack_key', 'pack_version'),
    PackUserGrant: ('id', 'company_id', 'branch_id', 'context_id', 'user_id'),
    PackMasterAvailability: ('id', 'company_id', 'branch_id', 'context_id', 'resource_table', 'resource_key'),
}


def _immutable_update(mapper, connection, target):
    state = inspect(target)
    names = _IDENTITY[type(target)]
    # Read persisted identity so expired/unloaded attributes cannot bypass the
    # protection by presenting an empty attribute-history.deleted collection.
    table = target.__table__
    extra = ('ever_activated', 'state') if isinstance(target, PackContext) else ()
    original = connection.execute(select(*(table.c[name] for name in (*names, 'revision', *extra))).where(table.c.id == state.identity[0])).mappings().one_or_none()
    if original is None or any(getattr(target, name) != original[name] for name in names):
        raise PackIdentityError('Business Pack identity is immutable; create a separate context or grant')
    if state.attrs.revision.history.has_changes() and target.revision != original['revision'] + 1:
        raise PackRevisionError('Business Pack revision must advance exactly once')
    if isinstance(target, PackContext):
        if original['ever_activated'] and not target.ever_activated:
            raise PackIdentityError('Business Pack activation history cannot be cleared')
        if original['ever_activated'] or original['state'] != 'draft' or target.state != 'draft':
            target.ever_activated = True


def _activation_history_insert(mapper, connection, target):
    target.ever_activated = bool(target.ever_activated) or target.state not in (None, 'draft')


def _append_only_update(mapper, connection, target):
    if any(attribute.history.has_changes() for attribute in inspect(target).attrs):
        raise PackIdentityError('Native Business Pack record ownership is append-only')


def _append_only_delete(mapper, connection, target):
    raise PackIdentityError('Native Business Pack record ownership cannot be removed or retagged')


for _model in _IDENTITY:
    event.listen(_model, 'before_update', _immutable_update)
event.listen(PackContext, 'before_insert', _activation_history_insert)
event.listen(PackRecordOwnership, 'before_update', _append_only_update)
event.listen(PackRecordOwnership, 'before_delete', _append_only_delete)

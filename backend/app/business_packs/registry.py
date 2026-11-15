"""Immutable definitions for seven proposed Business Packs.

This registry grants nothing. Activation, verified branch/context membership,
native module/action permissions and immutable record ownership must all be
enforced by later integration. Shared service names indicate code reuse only;
they never make one pack's operational data visible to another pack.
"""
from dataclasses import dataclass, field, replace
from enum import Enum
import re
from types import MappingProxyType
from typing import Mapping


NATIVE_MODULE_KEYS = frozenset({'hrms', 'crm', 'project_management', 'srm', 'fam'})
_KEY = re.compile(r'[a-z][a-z0-9_]{0,63}\Z', re.ASCII)
_CAPABILITY = re.compile(r'[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){2,}\Z', re.ASCII)


class PackRegistryError(ValueError):
    """An unsupported or malformed pack/role was requested."""


class FeatureState(str, Enum):
    SHARED_SERVICE_EXISTS = 'shared_service_exists'
    PARTIAL_DOMAIN_EXISTS = 'partial_domain_exists'
    PLANNED = 'planned'


def _key(value, kind):
    if not isinstance(value, str) or not _KEY.fullmatch(value):
        raise PackRegistryError(f'Malformed {kind} key')
    return value


@dataclass(frozen=True)
class PackRole:
    pack_key: str
    key: str
    label: str
    capabilities: frozenset[str]
    grants_company_admin: bool = field(default=False, init=False)

    def __post_init__(self):
        _key(self.pack_key, 'pack')
        _key(self.key, 'role')
        if not isinstance(self.capabilities, frozenset) or not self.capabilities:
            raise PackRegistryError('Role capabilities must be a nonempty immutable allow-list')
        for capability in self.capabilities:
            if (not isinstance(capability, str) or not _CAPABILITY.fullmatch(capability)
                    or not capability.startswith(self.pack_key + '.')
                    or any(part in {'company_admin', 'super_admin', 'platform_admin'} for part in capability.split('.'))):
                raise PackRegistryError('A role capability must remain inside its pack')


@dataclass(frozen=True)
class PackWorkflow:
    key: str
    label: str
    state: FeatureState
    shared_service: str | None = None

    def __post_init__(self):
        _key(self.key, 'workflow')
        if not isinstance(self.state, FeatureState):
            raise PackRegistryError('Workflow readiness must use a declared state')
        if self.shared_service is not None:
            _key(self.shared_service, 'shared service')


@dataclass(frozen=True)
class PackManifest:
    key: str
    label: str
    required_modules: frozenset[str]
    optional_modules: frozenset[str]
    roles: tuple[PackRole, ...]
    workflows: tuple[PackWorkflow, ...]
    exclusions: tuple[str, ...]
    version: int = field(default=1, init=False)
    foundation_state: str = field(default='registry_only', init=False)
    activation_ready: bool = field(default=False, init=False)
    isolation_ready: bool = field(default=False, init=False)
    ui_integrated: bool = field(default=False, init=False)

    def __post_init__(self):
        _key(self.key, 'pack')
        if (not isinstance(self.required_modules, frozenset)
                or not isinstance(self.optional_modules, frozenset)
                or not self.required_modules
                or not (self.required_modules | self.optional_modules) <= NATIVE_MODULE_KEYS
                or self.required_modules & self.optional_modules):
            raise PackRegistryError('Pack dependencies must use distinct known native module keys')
        if not isinstance(self.roles, tuple) or not self.roles:
            raise PackRegistryError('Pack roles must be a nonempty immutable tuple')
        if (any(not isinstance(role, PackRole) or role.pack_key != self.key for role in self.roles)
                or len({role.key for role in self.roles}) != len(self.roles)):
            raise PackRegistryError('Pack roles must be unique and belong to this pack')
        if (not isinstance(self.workflows, tuple) or not self.workflows
                or any(not isinstance(workflow, PackWorkflow) for workflow in self.workflows)
                or len({workflow.key for workflow in self.workflows}) != len(self.workflows)):
            raise PackRegistryError('Pack workflows must be unique immutable definitions')
        if not isinstance(self.exclusions, tuple):
            raise PackRegistryError('Pack exclusions must be immutable')

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset(capability for role in self.roles for capability in role.capabilities)

    @property
    def shared_services(self) -> frozenset[str]:
        return frozenset(workflow.shared_service for workflow in self.workflows if workflow.shared_service)


def _role(pack, key, label, *capabilities):
    # The literal lists below are allow-lists, not actions inferred from a job
    # title, native module role or a broad "admin" suffix.
    return PackRole(pack, key, label, frozenset(f'{pack}.{capability}' for capability in capabilities))


def _workflow(key, label, state=FeatureState.PLANNED, service=None):
    return PackWorkflow(key, label, state, service)


_EXISTS = FeatureState.SHARED_SERVICE_EXISTS
_PARTIAL = FeatureState.PARTIAL_DOMAIN_EXISTS

_MANIFESTS = (
    PackManifest('retail', 'Retail', frozenset({'srm'}), frozenset({'hrms', 'crm', 'fam'}), (
        _role('retail', 'cashier', 'Cashier', 'checkout.view', 'checkout.create', 'payments.record'),
        _role('retail', 'storekeeper', 'Storekeeper', 'stock.view', 'stock.receive', 'stock.count'),
        _role('retail', 'store_manager', 'Store manager', 'checkout.view', 'checkout.create', 'payments.record', 'stock.view', 'stock.receive', 'stock.count', 'returns.approve', 'discounts.approve', 'sessions.close', 'reports.view', 'settings.manage'),
    ), (
        _workflow('checkout', 'Native POS checkout', _EXISTS, 'pos'),
        _workflow('stock', 'Native stock and purchasing', _EXISTS, 'inventory'),
        _workflow('payments', 'Native invoices and receipts', _EXISTS, 'billing'),
        _workflow('register_close', 'Pack cashier sessions and cash close'),
        _workflow('returns', 'Original-sale-linked return workflow', _PARTIAL, 'sales_returns'),
    ), ('Loyalty and ecommerce integrations are later scope.',)),
    PackManifest('construction', 'Construction', frozenset({'crm', 'project_management', 'srm'}), frozenset({'hrms', 'fam'}), (
        _role('construction', 'billing_officer', 'Construction billing officer', 'billing.view', 'billing.prepare', 'payments.record', 'reports.view'),
        _role('construction', 'site_engineer', 'Site engineer', 'sites.view', 'diary.record', 'measurements.prepare', 'materials.request'),
        _role('construction', 'quantity_surveyor', 'Quantity surveyor', 'sites.view', 'boq.prepare', 'variations.prepare', 'measurements.prepare', 'measurements.certify'),
        _role('construction', 'project_manager', 'Construction project manager', 'sites.view', 'diary.record', 'boq.prepare', 'boq.approve', 'variations.prepare', 'variations.approve', 'measurements.prepare', 'measurements.certify', 'subcontracts.manage', 'materials.request', 'billing.prepare', 'discounts.approve', 'sessions.close', 'reports.view', 'settings.manage'),
    ), (
        _workflow('project_delivery', 'Native project delivery', _EXISTS, 'project_delivery'),
        _workflow('boq', 'BOQ and variations', _PARTIAL),
        _workflow('site_work', 'Measurements and site diary', _PARTIAL),
        _workflow('materials', 'Native inventory material issues', _PARTIAL, 'inventory'),
        _workflow('billing', 'Certified billing and retention', _PARTIAL, 'billing'),
    ), ('Tendering and advanced subcontract payroll are later scope.',)),
    PackManifest('hospital', 'Hospital', frozenset({'hrms', 'srm'}), frozenset({'crm', 'fam'}), (
        _role('hospital', 'doctor', 'Doctor', 'appointments.view', 'visits.start', 'visits.complete'),
        _role('hospital', 'receptionist', 'Receptionist', 'patients.view', 'patients.register', 'appointments.view', 'appointments.schedule', 'appointments.check_in'),
        _role('hospital', 'cashier', 'Hospital cashier', 'appointments.view', 'billing.view', 'billing.prepare', 'payments.record'),
        _role('hospital', 'hospital_manager', 'Hospital pack manager', 'patients.view', 'patients.register', 'providers.manage', 'appointments.view', 'appointments.schedule', 'appointments.check_in', 'appointments.cancel', 'appointments.no_show', 'visits.start', 'visits.complete', 'billing.view', 'billing.prepare', 'payments.record', 'discounts.approve', 'sessions.close', 'reports.view', 'settings.manage'),
    ), (
        _workflow('appointments', 'Common appointment scheduling', _EXISTS, 'appointments'),
        _workflow('providers', 'HRMS-linked doctor availability', _EXISTS, 'provider_availability'),
        _workflow('visit_checkout', 'Native visit invoice, advance and payment', _EXISTS, 'billing'),
    ), ('Clinical notes, prescriptions, admissions, beds, labs and insurance are excluded.',)),
    PackManifest('pharma', 'Pharma', frozenset({'srm'}), frozenset({'hrms', 'crm', 'fam'}), (
        _role('pharma', 'cashier', 'Pharmacy cashier', 'medicines.view', 'batches.view', 'checkout.view', 'checkout.create', 'payments.record'),
        _role('pharma', 'pharmacist', 'Pharmacist', 'medicines.view', 'batches.view', 'dispensing.prepare', 'checkout.create'),
        _role('pharma', 'storekeeper', 'Pharma storekeeper', 'medicines.view', 'batches.view', 'batches.receive', 'stock.count'),
        _role('pharma', 'pharmacy_manager', 'Pharmacy pack manager', 'medicines.view', 'medicines.manage', 'batches.view', 'batches.receive', 'batches.quarantine', 'dispensing.prepare', 'checkout.create', 'stock.count', 'returns.approve', 'recalls.manage', 'sessions.close', 'reports.view', 'settings.manage'),
    ), (
        _workflow('native_checkout', 'Native sales checkout', _EXISTS, 'pos'),
        _workflow('native_stock', 'Native stock quantity ledger', _EXISTS, 'inventory'),
        _workflow('native_billing', 'Native invoices and payments', _EXISTS, 'billing'),
        _workflow('batch_expiry', 'Batch allocation, expiry blocking and traceability'),
        _workflow('recalls', 'Batch-linked returns and recalls'),
    ), ('Pharmaceutical manufacturing, prescription integrations and regulatory filing are excluded.',)),
    PackManifest('accounting_firm', 'Accounts Company', frozenset({'crm', 'project_management', 'srm'}), frozenset({'hrms', 'fam'}), (
        _role('accounting_firm', 'billing_officer', 'Accounts billing officer', 'billing.view', 'billing.prepare', 'payments.record', 'reports.view'),
        _role('accounting_firm', 'preparer', 'Preparer', 'engagements.view', 'documents.request', 'work.prepare', 'time.record'),
        _role('accounting_firm', 'reviewer', 'Reviewer', 'engagements.view', 'documents.view', 'work.review', 'work.return'),
        _role('accounting_firm', 'engagement_manager', 'Engagement manager', 'engagements.view', 'engagements.manage', 'documents.request', 'documents.view', 'work.prepare', 'work.review', 'work.return', 'time.record', 'billing.prepare', 'discounts.approve', 'sessions.close', 'reports.view', 'settings.manage'),
    ), (
        _workflow('client_master', 'Native client master', _EXISTS, 'customers'),
        _workflow('delivery', 'Native projects, tasks and time', _EXISTS, 'project_delivery'),
        _workflow('billing', 'Native service invoicing and receipts', _EXISTS, 'billing'),
        _workflow('period_work', 'Recurring engagement periods and document requests'),
        _workflow('review', 'Independent preparer and reviewer controls'),
    ), ('Client books require explicit separate delegation; automatic statutory filing is excluded.',)),
    PackManifest('salon', 'Salon', frozenset({'hrms', 'srm'}), frozenset({'crm', 'fam'}), (
        _role('salon', 'stylist', 'Stylist', 'appointments.view', 'visits.start', 'visits.complete'),
        _role('salon', 'receptionist', 'Salon receptionist', 'customers.view', 'appointments.view', 'appointments.schedule', 'appointments.check_in'),
        _role('salon', 'cashier', 'Salon cashier', 'appointments.view', 'billing.view', 'billing.prepare', 'payments.record'),
        _role('salon', 'salon_manager', 'Salon pack manager', 'customers.view', 'providers.manage', 'appointments.view', 'appointments.schedule', 'appointments.check_in', 'appointments.cancel', 'appointments.no_show', 'visits.start', 'visits.complete', 'billing.view', 'billing.prepare', 'payments.record', 'discounts.approve', 'sessions.close', 'reports.view', 'settings.manage'),
    ), (
        _workflow('appointments', 'Common appointment scheduling', _EXISTS, 'appointments'),
        _workflow('providers', 'HRMS-linked stylist availability', _EXISTS, 'provider_availability'),
        _workflow('checkout', 'Native visit invoice, advance and payment', _EXISTS, 'billing'),
        _workflow('eligibility', 'Pack-specific staff and service eligibility', _PARTIAL),
    ), ('Memberships, prepaid packages and commissions are later scope.',)),
    PackManifest('restaurant', 'Restaurant', frozenset({'hrms', 'srm'}), frozenset({'crm', 'fam'}), (
        _role('restaurant', 'chef', 'Chef', 'kitchen.view', 'kitchen.prepare', 'kitchen.ready'),
        _role('restaurant', 'server', 'Server', 'tables.view', 'orders.view', 'orders.create', 'orders.serve'),
        _role('restaurant', 'cashier', 'Restaurant cashier', 'orders.view', 'billing.view', 'billing.prepare', 'payments.record'),
        _role('restaurant', 'restaurant_manager', 'Restaurant pack manager', 'tables.view', 'tables.manage', 'orders.view', 'orders.create', 'orders.serve', 'kitchen.view', 'kitchen.prepare', 'kitchen.ready', 'orders.void', 'billing.view', 'billing.prepare', 'payments.record', 'discounts.approve', 'sessions.close', 'reservations.schedule', 'reports.view', 'settings.manage'),
    ), (
        _workflow('checkout', 'Native POS and billing services', _EXISTS, 'pos'),
        _workflow('billing', 'Native invoices and payments', _EXISTS, 'billing'),
        _workflow('reservations', 'Common appointment scheduling for reservations', _EXISTS, 'appointments'),
        _workflow('table_orders', 'Tables, menu modifiers and service orders'),
        _workflow('kitchen', 'Kitchen tickets and preparation workflow'),
        _workflow('settlement', 'Split bills, table transfer and shift close'),
    ), ('Delivery aggregators, recipe costing and offline synchronization are later scope.',)),
)

# Appointments are a shared capability, independent of each pack's sales
# pipeline. A service desk assignment is explicit, never inherited by doctors,
# chefs, engineers, preparers or other specialist roles. Native scheduling,
# billing, collection and module permissions are still independently required.
_MANIFESTS = tuple(replace(pack,
    roles=pack.roles + (_role(pack.key, 'service_desk', 'Service desk',
        'customers.register', 'appointments.view', 'appointments.schedule', 'appointments.check_in',
        'billing.view', 'billing.prepare', 'payments.record'),),
    workflows=pack.workflows + (() if 'appointments' in pack.shared_services else (
        _workflow('appointments', 'Common appointment scheduling', _EXISTS, 'appointments'),
    )),
) for pack in _MANIFESTS)

# Catalogue management is an explicit pack action, independently native-gated.
_CATALOG_MANAGERS = frozenset({'store_manager','project_manager','hospital_manager','pharmacy_manager','engagement_manager','salon_manager','restaurant_manager'})
_MANIFESTS = tuple(replace(pack,roles=tuple(replace(role,capabilities=role.capabilities | frozenset({pack.key+'.catalog.view',pack.key+'.catalog.manage'}))
    if role.key in _CATALOG_MANAGERS else role for role in pack.roles)) for pack in _MANIFESTS)

# Small businesses can explicitly assign one person the pack's operational
# duties. This role remains inside that pack and retains native permission gates.
_MANIFESTS = tuple(replace(pack, roles=pack.roles + (
    _role(pack.key, 'business_owner', 'Business owner', *sorted({
        capability.removeprefix(pack.key + '.')
        for role in pack.roles for capability in role.capabilities
    })),
)) for pack in _MANIFESTS)

PACKS: Mapping[str, PackManifest] = MappingProxyType({pack.key: pack for pack in _MANIFESTS})
PACK_ALIASES: Mapping[str, str] = MappingProxyType({
    'saloon': 'salon', 'pharmacy': 'pharma', 'accounts_company': 'accounting_firm',
})


def resolve_pack_key(value: str) -> str:
    key = _key(value, 'pack')
    key = PACK_ALIASES.get(key, key)
    if key not in PACKS:
        raise PackRegistryError('Unsupported business pack')
    return key


def get_pack(key: str) -> PackManifest:
    return PACKS[resolve_pack_key(key)]


def list_packs() -> tuple[PackManifest, ...]:
    return _MANIFESTS


def get_role(pack_key: str, role_key: str) -> PackRole:
    pack = get_pack(pack_key)
    role_key = _key(role_key, 'role')
    for role in pack.roles:
        if role.key == role_key:
            return role
    raise PackRegistryError('Unsupported role for this business pack')

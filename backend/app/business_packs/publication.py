"""Code-owned finite release profiles; never caller/database declarations of readiness."""
from dataclasses import dataclass
from types import MappingProxyType

@dataclass(frozen=True)
class Publication:
    version: int
    isolation_version: int
    workflows: frozenset[str]
    proof_key: str

PUBLICATIONS = MappingProxyType({
    'hospital': Publication(1, 1, frozenset({'appointments', 'providers', 'visit_checkout'}), 'hospital-native-appointments-payments-v1'),
    'salon': Publication(1, 1, frozenset({'appointments', 'providers', 'checkout', 'eligibility'}), 'salon-native-scheduling-checkout-v1'),
    'accounting_firm': Publication(1, 1, frozenset({'client_master', 'delivery', 'billing', 'period_work', 'review', 'appointments'}), 'accounts-native-engagements-billing-v1'),
    'construction': Publication(1, 1, frozenset({'project_delivery', 'boq', 'site_work', 'materials', 'billing', 'appointments'}), 'construction-native-project-delivery-v1'),
})

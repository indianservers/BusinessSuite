"""Code-owned native SRM graph for common appointment/checkout integration.

This definition enables no pack and binds no request. Physical inventory,
projects/deals/contacts and specialized domain operations remain separate audits.
Private providers, registers and transactions never become shared masters.
"""
from dataclasses import dataclass
from .registry import get_pack

RECORD_TABLES=frozenset({
    'srm_industry_records','srm_service_booking_policies','srm_service_specialist_eligibility',
    'srm_pos_service_checkouts','srm_pos_checkout_lines','srm_pos_service_occurrences','srm_pos_checkout_payments',
    'srm_anonymous_cash_accounts','srm_pos_sessions','srm_pos_cash_movements','srm_pos_cashier_closings','srm_pos_held_bills',
    'srm_sales_orders','srm_sales_order_lines','srm_invoice_drafts','srm_invoices','srm_invoice_lines','srm_invoice_history',
    'srm_receipts','srm_receipt_allocations','srm_revenue_events','srm_audit_logs','srm_inventory_movements',
    'business_invoice_contexts','business_receipt_contexts','service_follow_ups','service_follow_up_activities',
    'service_follow_up_reminders','service_follow_up_attachments','notifications','suite_service_policies','communication_customer_events','email_outbox','suite_service_events',
})
RETAIL_RECORD_TABLES=frozenset({'business_retail_sale_stock_sources','business_retail_returns',
    'business_retail_return_lines','srm_pos_returns','srm_pos_return_lines',
    'srm_goods_receipts','srm_goods_receipt_lines'})
PHARMA_RECORD_TABLES=frozenset({'business_pharma_batch_receipts','business_pharma_batch_allocations',
    'business_pharma_recalls','business_pharma_recall_events','business_pharma_returns',
    'business_pharma_return_lines','business_pharma_return_lots','srm_pos_returns','srm_pos_return_lines'})
MASTER_TABLES=frozenset({'employees','crm_companies','srm_products','srm_warehouses'})
# These identify required boundary extensions; they are NOT generic exemptions.
ACTOR_COMPANY_AUTHORITY_READS=frozenset({'suite_access_memberships','suite_access_policies'})
COMPANY_AUTHORITY_READS=frozenset({'suite_access_roles','bos_enabled_modules'})
SHARED_CONTROL_READS=frozenset({'suite_service_policies','suite_company_master_details','business_seller_grants'})
NATIVE_LINKS=(
    ('srm_sales_orders','customer_id','crm_companies','id'),
    ('srm_sales_orders','crm_company_id','crm_companies','id'),
    ('srm_sales_order_lines','product_id','srm_products','id'),
    ('srm_sales_order_lines','sales_order_id','srm_sales_orders','id'),
    ('srm_invoices','customer_id','crm_companies','id'),
    ('srm_receipts','customer_id','crm_companies','id'),
)

@dataclass(frozen=True)
class NativeSRMDefinition:
    pack_key:str
    pack_version:int
    declared_workflows:frozenset[str]
    policy:object
    runtime_ready:bool=False


def native_srm_policy(pack_key):
    # The guarded graph is installed before the route handler can load this model.
    from app.apps.srm import anonymous_cash_models  # noqa: F401
    from .boundary import PackBoundaryPolicy,PackNativeLink,PackSourceLink,PackDerivedLink
    manifest=get_pack(pack_key)
    if 'srm' not in manifest.required_modules:raise ValueError('Native SRM dependency is required')
    # Resolve the current manifest; adding a workflow never declares it ready.
    declared=frozenset(workflow.key for workflow in manifest.workflows)
    retail=manifest.key=='retail'
    pharma=manifest.key=='pharma'
    if manifest.key == 'restaurant':
        from .restaurant.models import RECORD_TABLES as restaurant_tables
    else:
        restaurant_tables = frozenset()
    accounting = manifest.key == 'accounting_firm'
    if accounting:
        from .accounting_firm.models import RECORD_TABLES as accounting_tables
        accounting_tables = accounting_tables | frozenset({'srm_engagements'})
    else:
        accounting_tables = frozenset()
    links=NATIVE_LINKS+((('srm_pos_return_lines','return_id','srm_pos_returns','id'),
        ('srm_goods_receipt_lines','goods_receipt_id','srm_goods_receipts','id')) if retail else ())
    if accounting:
        links += (('srm_engagements', 'customer_id', 'crm_companies', 'id'),
                  ('srm_engagements', 'sales_order_id', 'srm_sales_orders', 'id'))
    return NativeSRMDefinition(manifest.key,manifest.version,declared,PackBoundaryPolicy(
        record_tables=RECORD_TABLES|(RETAIL_RECORD_TABLES if retail else frozenset())|(PHARMA_RECORD_TABLES if pharma else frozenset())|restaurant_tables|accounting_tables,master_tables=MASTER_TABLES,
        shared_read_tables=ACTOR_COMPANY_AUTHORITY_READS|COMPANY_AUTHORITY_READS|SHARED_CONTROL_READS,
        native_links=tuple(PackNativeLink(*link) for link in links),
        source_links=(PackSourceLink('communication_customer_events','source_type','source_id',
            (('order','srm_sales_orders'),('invoice','srm_invoices'),('follow_up','service_follow_ups'))
            + ((('service','srm_engagements'),) if accounting else ())),
            PackSourceLink('suite_service_events','entity_type','entity_id',(('invoice','srm_invoices'),))),
        derived_links=(PackDerivedLink('srm_inventory_movements',frozenset({'srm_sales_order_lines'})|(frozenset({'srm_pos_return_lines','srm_goods_receipt_lines'}) if retail else frozenset())|(frozenset({'business_pharma_batch_receipts','business_pharma_return_lots'}) if pharma else frozenset())|(frozenset({'business_restaurant_kitchen_lines'}) if manifest.key=='restaurant' else frozenset())|(frozenset({'srm_industry_records'}) if manifest.key=='construction' else frozenset()),
            frozenset({'organization_id','movement_number','movement_type','movement_date','product_id','warehouse_id','quantity_in','quantity_out','rate','value','reference_number','notes','created_by','created_at'})),
            PackDerivedLink('email_outbox',frozenset({'srm_sales_orders','srm_invoices','srm_receipts','notifications'})
                | (frozenset({'srm_engagements'}) if accounting else frozenset())
                | (frozenset({'srm_goods_receipts'}) if retail else frozenset()),
            frozenset({'event_key','organization_id','module','recipient_user_id','recipient','subject','body','is_html'})),
            PackDerivedLink('suite_service_events',frozenset({'srm_invoices'}),
                frozenset({'organization_id','module_key','event_type','entity_type','entity_id','actor_id','request_key','payload_json'})),)))


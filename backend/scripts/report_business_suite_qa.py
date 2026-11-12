"""Build requested QA reports from executed JUnit/browser evidence, never guessed results."""
import json
import re
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'backend/outputs'
PLAN = json.loads((Path(__file__).with_name('business_suite_qa_cases.json')).read_text(encoding='utf-8'))

# The original full run is a pre-fix baseline. Verified targeted reruns take
# precedence even if the long-running baseline finishes later.
BASELINE = OUT / 'business-suite-full-regression.xml'
FINAL = OUT / 'business-suite-full-final.xml'
ARTIFACTS = [
    'business-suite-postgres-regression.xml', 'business-suite-pos-after.xml',
    'business-suite-postgres-fixes-verified.xml', 'business-suite-gst-after.xml',
    'business-suite-masterdata-after.xml', 'business-suite-crossmodule-security.xml',
    'business-suite-postgres-acceptance.xml', 'business-suite-final-fixes.xml',
    'business-suite-postgres-final.xml', 'business-suite-live-browser.xml',
    'business-suite-pos-latest.xml',
    'business-suite-commercial-links.xml', 'business-suite-postgres-closure.xml',
    'business-suite-operator-after.xml', 'business-suite-regression-repairs.xml',
    'business-suite-knowledge-retest.xml',
]

BLOCKED = {
    4:'FAM retains its native party/ledger view. Canonical vendor identity reconciliation is not implemented end to end.',
    7:'Sales-only users have no approved lead adapter independent of CRM grants; routing alone does not grant CRM access.',
    8:'The common PMS calendar exists, but CRM native events and service appointments are not one calendar projection.',
    13:'A Sales-only lead-write adapter is not implemented; broadening CRM permissions would not be a safe QA fix.',
    15:'Vendor-to-FAM canonical identity mapping requires reconciliation of legacy party IDs; no business records were merged.',
    18:'CRM-linked task reads are tested; task quick-create still needs explicit CRM associations and origin-aware return navigation.',
    19:'Persistent private notes are tested; a universal customer-to-note association with cross-module visibility is incomplete.',
    24:'POS checkout posts a sales order; it does not atomically issue an invoice and persist its payment.',
    29:'Split/partial payment inputs are not persisted as native receipts by POS checkout. This is a release blocker.',
    38:'The current POS/catalog workflow does not expose a complete, verified tax-inclusive pricing contract.',
    58:'Batch/serial master persistence and duplicate rejection are tested; POS allocation, expiry enforcement and serial lifecycle are not certified by those master-data tests.',
    62:'AMC product/asset association is not implemented as a verified canonical relationship.',
    63:'AMC technician assignment does not implement the requested HRMS employee/skill eligibility contract.',
    64:'AMC service-visit appointment projection into the common calendar is not implemented.',
    65:'Generic recurring billing exists; an AMC renewal reminder workflow was not verified.',
    66:'Generic renewal status/audit persistence is tested; new AMC coverage terms and renewal history were not exercised end to end.',
    67:'Native FAM invoice posting is tested, but the requested AMC-to-invoice workflow is not complete.',
    68:'Contract expiry/status persistence is tested; cancellation/expiry enforcement across AMC visits and billing is not implemented end to end.',
    94:'Service-package expiry and entitlement storage/redemption workflow is not implemented.',
    95:'Service-package partial redemption and its idempotent ledger are not implemented.',
    96:'Customer appointment cancellation is blocked by the missing service-appointment workflow.',
    97:'Appointment employee reassignment is blocked by the missing employee-backed appointment workflow.',
    98:'Appointment crossing-midnight behavior cannot be certified without the appointment implementation.',
    99:'Employee timezone changes for appointments cannot be certified without the scheduling implementation.',
    104:'Configured rates are tested; effective-dated item classification selection and missing-classification policy remain incomplete.',
}
for number in range(41,51):
    BLOCKED[number]='Service appointments, employee eligibility/availability, resource conflict checks and POS billing integration are not implemented. Existing meetings/Gantt boards are not substitutes.'

LINKS = {
    1:['f:test-common-routes.cjs','b:test_project_and_all_filters_keep_original_tasks'],
    2:['f:test-common-routes.cjs','b:test_profiles_and_links_cannot_cross_users_or_organizations'],
    3:['f:test-common-routes.cjs','b:tests.test_pms_teams.'],
    5:['f:test-common-routes.cjs','b:tests.test_pms_private_notes.'],
    6:['b:test_tc006_012_common_customer_ui_uses_real_canonical_api'],
    9:['f:test-common-routes.cjs','b:test_tc006_012_common_customer_ui_uses_real_canonical_api'],
    10:['f:test-common-routes.cjs','f:test-navigation-guards.cjs','f:test-desktop-navigation.cjs'],
    11:['b:test_tc006_012_common_customer_ui_uses_real_canonical_api'],
    12:['b:test_tc006_012_common_customer_ui_uses_real_canonical_api'],
    14:['b:test_conversion_reuses_identity_preserves_history_and_correction'],
    16:['b:test_profile_contact_edit_requests_hr_approval_and_syncs_after_approval'],
    17:['b:tests.test_pms_teams.'],
    20:['b:test_multiple_relationships_counts_filters_and_conflicts','b:test_secondary_phone_country_and_optional_sharing_reason'],
    21:['b:test_tc054_stock_type_cannot_be_spoofed_as_service'],
    22:['b:test_tc027_bill_discount_is_allocated_before_each_item_tax'],
    23:['b:test_tc060_service_does_not_move_stock'],
    25:['b:test_tc025_exempt_fixture_preserves_zero_tax'],
    26:['b:test_tc027_bill_discount_is_allocated_before_each_item_tax'],
    27:['b:test_tc027_bill_discount_is_allocated_before_each_item_tax'],
    28:['b:test_pos_held_bill_recall_lifecycle_is_database_backed'],
    30:['b:test_tc030_nonrestocked_return_still_consumes_refundable_quantity','b:test_tc030_concurrent_nonrestocked_refunds_cannot_exceed_original_sale'],
    31:['b:test_tc031_039_configured_rate_components_and_decimal_rounding'],
    32:['b:test_tc031_039_configured_rate_components_and_decimal_rounding'],
    33:['b:test_tc031_039_configured_rate_components_and_decimal_rounding'],
    34:['b:test_tc031_039_configured_rate_components_and_decimal_rounding'],
    35:['b:test_tc027_bill_discount_is_allocated_before_each_item_tax'],
    36:['b:test_fam_gst_intra_and_inter_state_logic','b:test_tc031_039_configured_rate_components_and_decimal_rounding'],
    37:['b:test_fam_gst_intra_and_inter_state_logic','b:test_tc031_039_configured_rate_components_and_decimal_rounding'],
    39:['b:test_tc031_039_configured_rate_components_and_decimal_rounding','b:test_tc006_012_common_customer_ui_uses_real_canonical_api'],
    40:['b:test_tc040_refund_uses_original_discount_and_tax_snapshot','b:test_fam_reverses_srm_invoice_posting_with_opposite_voucher'],
    51:['b:test_srm_product_master_and_opening_stock_are_database_backed'],
    52:['b:test_srm_product_master_and_opening_stock_are_database_backed','b:tests.test_fam_inventory_opening_stock.'],
    53:['b:test_srm_product_master_and_opening_stock_are_database_backed'],
    54:['b:test_tc054_stock_type_cannot_be_spoofed_as_service'],
    55:['b:test_srm_product_master_and_opening_stock_are_database_backed'],
    56:['b:test_srm_product_master_and_opening_stock_are_database_backed','b:tests.test_fam_inventory_transfer_accounting.'],
    57:['b:test_srm_product_master_and_opening_stock_are_database_backed'],
    58:['b:test_srm_product_master_and_opening_stock_are_database_backed'],
    59:['b:test_tc059_two_checkouts_cannot_sell_the_last_unit_twice'],
    60:['b:test_tc060_service_does_not_move_stock'],
    61:['b:test_tc061_contract_reuses_existing_canonical_customer'],
    66:['b:test_srm_contract_create_persists'],
    68:['b:test_srm_contract_create_persists','b:test_end_date_and_template_settings'],
    69:['b:tests.test_security_employee_scope.'],
    70:['b:tests.test_fam_srm_posting_rbac.','b:test_commercial_role_matrix'],
    71:['b:test_tc071_foreign_customer_cannot_be_attached_to_pos_order','b:test_links_pricing_tax_and_tenant_isolation'],
    72:['b:tests.test_security_backend_enforcement.'],
    73:['b:test_tc073_return_cannot_substitute_another_product','b:test_tc073_return_customer_cannot_be_replaced'],
    74:['b:tests.test_security_files_and_formulas.'],
    75:['b:test_tc075_text_identity_history_prevents_permanent_deletion','b:test_srm_contract_create_persists'],
    76:['b:test_tc076_tax_rate_bounds_cannot_be_bypassed','b:test_tc076_pos_totals_and_tax_are_server_authoritative'],
    77:['b:test_tc077_ten_thousand_customers_have_bounded_page_and_queries'],
    78:['b:test_grid_bulk_export_and_source_identity','b:test_srm_product_master_and_opening_stock_are_database_backed'],
    79:['f:test-navigation-branding.cjs'],
    80:['f:test-background-refresh.cjs','f:test-record-list-refresh.cjs','f:test-record-mutations.cjs'],
    81:['b:test_relationship_edits_reject_stale_version','b:test_financial_profile_roundtrip_conflict_and_optional'],
    82:['b:test_tc082_duplicate_concurrent_checkout_has_one_order_and_stock_movement'],
    83:['f:test-common-routes.cjs','f:test-navigation-workspaces.cjs'],
    84:['b:test_tc006_012_common_customer_ui_uses_real_canonical_api','f:test-mobile-fam-workflows.cjs','f:test-mobile-pms-notes.cjs'],
    86:['b:test_nulls_and_invalid_score_return_validation_errors','b:test_tc106_invalid_quantity_is_atomic'],
    87:['b:test_tc006_012_common_customer_ui_uses_real_canonical_api','b:test_unicode_mononym_and_controls'],
    88:['b:test_long_display_names_fit_canonical_identity_columns'],
    89:['b:test_secondary_phone_country_and_optional_sharing_reason'],
    90:['b:test_duplicate_prevention_and_transfer_tenant_attributes'],
    91:['b:test_multiple_relationships_counts_filters_and_conflicts'],
    92:['b:test_tc092_zero_price_product_is_zero_billed_but_still_issues_stock'],
    93:['b:test_tc093_fractional_quantity_stock_and_money_remain_consistent','b:test_tc111_unsupported_sale_precision_cannot_be_silently_truncated'],
    100:['b:test_fam_srm_invoice_and_receipt_posting_are_idempotent','b:test_tc082_duplicate_concurrent_checkout_has_one_order_and_stock_movement'],
    101:['b:test_unknown_delivery_outcome_survives_reload_without_resend'],
    102:['b:test_tc059_oversell_rolls_back_order_and_stock'],
    103:['b:test_tc059_oversell_rolls_back_order_and_stock'],
    105:['b:test_tc109_inactive_catalog_item_cannot_be_sold','b:test_tc040_refund_uses_original_discount_and_tax_snapshot'],
    106:['f:test-navigation-guards.cjs','f:test-record-cache.cjs'],
    107:['b:test_read_permission_does_not_grant_mutation_or_hr_access','b:test_commercial_role_matrix'],
}
# A provider delivery timeout is not a payment-gateway timeout. Never count one
# as evidence for the other. The actual requested case stays blocked.
BLOCKED[101]='Native POS gateway payment persistence/reconciliation is incomplete; an email/provider timeout test does not establish payment-gateway behavior.'

BUGS = [
 ('B01','Critical','Client item-type flag bypassed stock issuance',[54,59,76],['backend/app/apps/srm/api/router.py'],'Determine inventory behavior from the canonical product and lock stock rows.',['b:test_tc054_stock_type_cannot_be_spoofed_as_service','b:test_tc059_two_checkouts_cannot_sell_the_last_unit_twice']),
 ('B02','Critical','Negative/zero quantities and negative money were accepted',[76,86,93],['backend/app/apps/srm/schemas.py'],'Validate positive, storable quantity precision and nonnegative finite line amounts.',['b:test_tc106_invalid_quantity_is_atomic','b:test_tc107_negative_money_is_rejected','b:test_tc111_unsupported_sale_precision_cannot_be_silently_truncated']),
 ('B03','Critical','POS trusted client totals/tax and lost bill discounts',[26,27,35,76],['backend/app/apps/srm/api/router.py','backend/app/apps/srm/services/commercial.py'],'Reuse commercial decimal normalization, allocate bill discounts and snapshot canonical item tax.',['b:test_tc076_pos_totals_and_tax_are_server_authoritative','b:test_tc027_bill_discount_is_allocated_before_each_item_tax']),
 ('B04','Critical','Non-restocked refunds did not consume refundable quantity',[30],['backend/app/apps/srm/api/router.py'],'Count every return and serialize competing refunds.',['b:test_tc030_nonrestocked_return_still_consumes_refundable_quantity','b:test_tc030_concurrent_nonrestocked_refunds_cannot_exceed_original_sale']),
 ('B05','Critical','Return could substitute a different inventory product',[73],['backend/app/apps/srm/api/router.py'],'Bind returns to the original sale line and validate warehouse scope.',['b:test_tc073_return_cannot_substitute_another_product']),
 ('B06','High','Refund lost original discounts/tax and allowed over-refund',[40,105],['backend/app/apps/srm/api/router.py'],'Use remaining original value/tax, proportional refunds and last-return rounding remainder.',['b:test_tc040_refund_uses_original_discount_and_tax_snapshot','b:test_tc108_refund_cannot_exceed_original_sale_value']),
 ('B07','High','PostgreSQL contact retention query compared text IDs to integers',[75],['backend/app/apps/crm/contact_directory.py'],'Bind identifiers using their stored SQL type; retain linked history.',['b:test_tc075_text_identity_history_prevents_permanent_deletion','b:test_permanent_deletion_is_admin_only_and_protects_referenced_contacts']),
 ('B08','High','FAM GST ties rounded differently from commercial/POS arithmetic',[31,39],['backend/app/apps/fam/api/router.py'],'Apply explicit ROUND_HALF_UP to each tax component.',['b:test_tc031_039_configured_rate_components_and_decimal_rounding']),
 ('B09','High','GST API accepted negative and invalid component rates',[76],['backend/app/apps/fam/schemas.py'],'Validate GST component bounds and nonnegative taxable/cess values; preserve configurable positive cess.',['b:test_tc076_tax_rate_bounds_cannot_be_bypassed']),
 ('B10','Medium','100-customer page performed 405 SELECTs',[77],['backend/app/shared/master_data.py'],'Batch details, relationships and branch availability for the authorized page only.',['b:test_tc077_ten_thousand_customers_have_bounded_page_and_queries']),
 ('B11','Medium','FAM table adapter swallowed the financial empty state',[84],['frontend/src/apps/fam/FinancialStatementsPage.tsx'],'Render explicit empty status and suppress stale statements on failed requests.',['f:test-mobile-fam-workflows.cjs']),
 ('B12','Medium','Successful bank-rule creation left its dialog open',[84],['frontend/src/apps/fam/BankRulesPage.tsx'],'Close on an explicit successful creation revision; retain forms on errors.',['f:test-mobile-fam-workflows.cjs']),
 ('B13','Medium','Navigation/accounting harnesses had stale dependencies, server assumptions and races',[10,79,83],['frontend/scripts/test-navigation-workspaces.cjs','frontend/scripts/test-navigation-categories.cjs','frontend/scripts/test-operations-workspaces.cjs','frontend/scripts/test-relationship-hub.cjs','frontend/scripts/test-accounting-connected.cjs'],'Load real route helpers, honor current workspace presentation, start isolated servers and await confirmed requests.',['f:test-navigation-workspaces.cjs','f:test-navigation-categories.cjs','f:test-operations-workspaces.cjs','f:test-relationship-hub.cjs','f:test-accounting-connected.cjs']),
 ('B14','Critical','POS order/return accepted foreign or replacement customer IDs',[71,73],['backend/app/apps/srm/api/router.py'],'Reuse tenant-scoped commercial customer/contact resolvers and bind return customer to its source sale.',['b:test_tc071_foreign_customer_cannot_be_attached_to_pos_order','b:test_tc073_return_customer_cannot_be_replaced']),
 ('B15','High','Workflow interpretation intercepted pending single-action help/cancellation',[18],['backend/app/ai_operator/workflows.py'],'Preserve ownership of pending single-action slot filling and cancellation.',['b:test_invalid_followup_keeps_question_and_cancel_only_affects_that_chat','b:test_ambiguous_or_help_reply_never_becomes_a_task_title']),
 ('B16','High','Nested provider/worker retries made nine requests for a three-attempt job',[106],['backend/app/ai_operator/providers.py','backend/app/ai_operator/jobs.py'],'Worker owns retries through a context-local one-attempt provider budget; synchronous retries retain their bounded contract.',['b:test_provider_retry_budget_and_failed_attempt_telemetry']),
 ('B17','High','POS rounded payable to whole currency units and displayed a local rather than confirmed total',[39],['frontend/src/apps/srm/pages/SRMPOSPage.tsx'],'Keep cents in the preview and display the persisted server total after checkout.',['b:test_tc006_012_common_customer_ui_uses_real_canonical_api']),
 ('B18','High','Checkpoint snapshots mistook a successful own update for a stale plan',[18,102],['backend/app/ai_operator/jobs.py'],'Reload persisted task state before computing the next checkpoint digest; retain checks against actual external edits.',['b:test_background_work_uses_durable_queue_and_after_commit_events','b:test_expired_lease_resumes_without_duplicate_completed_step','b:test_failed_checkpoint_preserves_completed_effects_and_resumes']),
]


def junit(path):
    if not path.exists(): return []
    try: root=ET.parse(path).getroot()
    except ET.ParseError: return []
    records=[]
    for case in root.iter('testcase'):
        failure=case.find('failure'); error=case.find('error'); skipped=case.find('skipped')
        bad=failure if failure is not None else error
        records.append({'node':case.get('classname','')+'.'+case.get('name',''), 'name':case.get('name',''),
                        'status':'FAIL' if bad is not None else 'BLOCKED' if skipped is not None else 'PASS',
                        'actual':(bad.get('message','').splitlines() or ['Assertion failed'])[0] if bad is not None else skipped.get('message','Skipped') if skipped is not None else 'Executed assertions passed',
                        'seconds':float(case.get('time','0')), 'artifact':str(path.relative_to(ROOT)),
                        'properties':{p.get('name'):p.get('value') for p in case.findall('./properties/property')}})
    return records


def collect():
    records={}
    for row in junit(BASELINE): records[row['node']]=row
    for name in ARTIFACTS:
        for row in junit(OUT/name): records[row['node']]=row
    for row in junit(FINAL):
        # A SQLite-only full run skips real PostgreSQL race tests. Preserve
        # their executed PostgreSQL PASS rather than replacing it with SKIP.
        if row['status']=='BLOCKED' and records.get(row['node'],{}).get('status')=='PASS':
            continue
        records[row['node']]=row
    front_path=OUT/'business-suite-frontend-results.json'
    front=json.loads(front_path.read_text(encoding='utf-8')) if front_path.exists() else []
    return records,{row['script']:row for row in front}


def evidence(patterns, records, frontend):
    matches=[]; missing=[]
    for pattern in patterns:
        kind, value=pattern.split(':',1)
        rows=([{'node':value,'status':frontend[value]['status'],'artifact':'backend/outputs/business-suite-frontend-results.json','actual':frontend[value]['output'].strip().splitlines()[-1] if frontend[value]['output'].strip() else 'No output'}] if value in frontend else []) if kind=='f' else [row for row in records.values() if row['node'].startswith(value) or row['name'].startswith(value)]
        if not rows: missing.append(pattern)
        matches.extend(rows)
    status='FAIL' if any(row['status']=='FAIL' for row in matches) else 'NOT RUN' if missing or not matches else 'BLOCKED' if any(row['status']=='BLOCKED' for row in matches) else 'PASS'
    return status,matches,missing


def full_progress():
    if FINAL.exists() or (OUT/'business-suite-full-final.log').exists():
        rows=junit(FINAL)
        text=(OUT/'business-suite-full-final.log').read_text(encoding='utf-8',errors='replace')
        collected=re.search(r'(\d+) items',text)
        entries=max([int(m[1]) for m in re.finditer(r'\[(\d+)/(\d+)\]',text)]+[len(rows),sum(len(m[1]) for m in re.finditer(r'^([.FsxXE]+)\s+\[\s*\d+%\]',text,re.M))])
        return {'observed_progress_entries':entries,'collected':int(collected[1]) if collected else len(rows),
                'failed_nodes_from_progress':[row['node'] for row in rows if row['status']=='FAIL'],
                'completed':bool(rows),'artifact':'backend/outputs/business-suite-full-final.xml'}
    text=(OUT/'business-suite-full-regression.log').read_text(encoding='utf-8',errors='replace') if (OUT/'business-suite-full-regression.log').exists() else ''
    entries=sum(len(m[1]) for line in text.splitlines() if (m:=re.match(r'^([.FsxXE]+)\s+\[\s*\d+%\]',line)))
    collection=(OUT/'business-suite-collection.log').read_text(encoding='utf-8',errors='replace')
    nodes=[line for line in collection.splitlines() if line.startswith('tests/') and '::' in line]
    offset=0;failures=[]
    for line in text.splitlines():
        match=re.match(r'^([.FsxXE]+)\s+\[\s*\d+%\]',line)
        if match:
            failures.extend(nodes[offset+i] for i,char in enumerate(match[1]) if char in 'FE' and offset+i<len(nodes))
            offset+=len(match[1])
    return {'observed_progress_entries':entries,'collected':len(nodes),'failed_nodes_from_progress':failures,'completed':bool(junit(BASELINE))}


def main():
    records,front=collect(); progress=full_progress(); results=[]
    for case in PLAN:
        number=int(case['id'][2:]); patterns=LINKS.get(number,[])
        status,matched,missing=evidence(patterns,records,front)
        reason=BLOCKED.get(number)
        if number==85:
            baseline=junit(FINAL)
            status='FAIL' if baseline and any(row['status']=='FAIL' for row in baseline) else 'PASS' if baseline else 'BLOCKED'
            reason=f"Full current-code repository regression: {progress['observed_progress_entries']} progress entries of {progress['collected']}; {'completed' if progress['completed'] else 'still running/not yet complete'}."
        elif reason: status='BLOCKED'
        bugs=[bug for bug in BUGS if number in bug[3]]
        actual=reason or ('Executed: '+', '.join(sorted({row['node'] for row in matched}))) if matched or reason else 'No executed evidence matched this requested scenario.'
        result={**case,'expected':case['case']+' with canonical identities, correct amounts, authorized scope and retained history.',
                'status':status,'severity':'Critical' if number in {24,29,71,73,76,82,100,103} else 'High' if reason else 'Medium',
                'actual':actual,'root_cause':reason or '; '.join(bug[2] for bug in bugs) or 'No defect reproduced in the linked assertions.',
                'fix':'; '.join(bug[5] for bug in bugs) or ('Requires an approved implementation/reconciliation stage; no production data changed.' if reason else 'Existing behavior tested.'),
                'files_changed':sorted({file for bug in bugs for file in bug[4]}),
                'retest':status if status!='BLOCKED' else 'BLOCKED — the complete requested workflow is not verified.',
                'evidence':sorted({row['artifact']+' :: '+row['node'] for row in matched}),'missing_evidence':missing}
        results.append(result)
    bug_results=[]
    for ident,severity,title,ids,files,fix,patterns in BUGS:
        status,matched,missing=evidence(patterns,records,front)
        bug_results.append({'id':ident,'severity':severity,'title':title,'status':'FIXED AND VERIFIED' if status=='PASS' else 'FIX APPLIED; RETEST '+status,
                            'fix':fix,'files':files,'cases':[f'TC{n:03}' for n in ids], 'evidence':sorted({row['artifact']+' :: '+row['node'] for row in matched}),'missing':missing})
    totals=Counter(row['status'] for row in results); backend=Counter(row['status'] for row in records.values()); browser=Counter(row['status'] for row in front.values())
    summary={'business_cases_planned':len(results),'business_case_statuses':dict(totals),
             'business_cases_executed':totals['PASS']+totals['FAIL'],
             'business_cases_blocked':totals['BLOCKED'],'business_cases_untested':totals['NOT RUN'],
             'backend_unique_latest_test_nodes':len(records),'backend_statuses':dict(backend),
             'frontend_harnesses':len(front),'frontend_statuses':dict(browser),
             'bugs_identified':len(bug_results),'bugs_fixed_verified':sum(row['status']=='FIXED AND VERIFIED' for row in bug_results),
             'identified_fixable_bugs_unverified':sum(row['status']!='FIXED AND VERIFIED' for row in bug_results),
             'open_workflow_gap_cases':sum(row['status']=='BLOCKED' and int(row['id'][2:]) in BLOCKED for row in results),
             'full_repository_regression':progress,'release_status':'BLOCKED'}
    (OUT/'business-suite-qa-summary.json').write_text(json.dumps({'summary':summary,'cases':results,'bugs':bug_results},ensure_ascii=False,indent=2),encoding='utf-8')
    intro=['# Business Suite QA report','', 'Date: 12 November 2026. Release status: **BLOCKED**.','',
           'This report distinguishes requested business workflows from individual automated assertions. Missing service appointments/packages and incomplete POS invoicing/payment posting are not counted as passing features.', '',
           f"Business cases planned: **{len(results)}**. Statuses: "+', '.join(f'{key} **{totals[key]}**' for key in ('PASS','FAIL','BLOCKED','NOT RUN'))+'.',
           f"Completed evidence contains **{len(records)} unique latest backend test nodes** ({dict(backend)}) and **{len(front)} frontend harnesses** ({dict(browser)}). Route-harness checks are separate from real browser/API workflows.",'',
           'Safety: the configured application PostgreSQL schema was inspected in a READ ONLY transaction. All financial writes, 10,000-customer seeding and concurrency checks used disposable SQLite databases or a separate localhost PostgreSQL cluster. No application tables were migrated, dropped, truncated, reset or merged. No external messages/payments were sent.', '',
           'Evidence: `backend/outputs/business-suite-qa-summary.json`, JUnit XML/logs under `backend/outputs/business-suite-*`, and the read-only `business-suite-source-schema.json`. GST rates are synthetic configured fixtures, not legal classifications.','',
           f"Full current-code repository regression: **{progress['observed_progress_entries']} observed progress entries**; completed: **{progress['completed']}**. The stopped serial pre-fix baseline log is retained separately.",'',
           'Scope qualifications: common-route harnesses verify registry/permission/context behavior and use stub native content. The live browser test mounts the actual registered React pages and forwards requests unchanged to the real disposable FastAPI DB. POS tax/discount tests certify order arithmetic; they do not establish invoice issuance or receipt posting. Generic contract lifecycle tests do not establish AMC scheduling or HRMS technician integration.','']
    for row in results:
        intro.extend([f"## {row['id']} — {row['case']}",'',f"- Module: {row['module']}",f"- Expected: {row['expected']}",f"- Actual: {row['actual']}",f"- Status: **{row['status']}**",f"- Severity: {row['severity']}",f"- Root cause: {row['root_cause']}",f"- Fix: {row['fix']}",'- Files changed: '+(', '.join(f'`{file}`' for file in row['files_changed']) or 'None for this scenario.'),f"- Retest: {row['retest']}",'- Evidence: '+('; '.join(f'`{item}`' for item in row['evidence']) or 'No passing execution evidence for the complete requested workflow.'),''])
    (ROOT/'BUSINESS_SUITE_QA_REPORT.md').write_text('\n'.join(intro),encoding='utf-8')
    fixes=['# Business Suite bug fixes','',f"Identified defect groups: {len(bug_results)}. Fixed and verified: {summary['bugs_fixed_verified']}. Verification is based on executed evidence, not code inspection alone.",'']
    for row in bug_results:
        fixes.extend([f"## {row['id']} — {row['title']}",'',f"- Severity: {row['severity']}",f"- Status: **{row['status']}**",f"- Reproduction: linked automated scenarios initially failed; retained before-fix artifacts include POS, GST, PostgreSQL retention, pagination and full-regression failure reruns.",f"- Root cause: {row['title']}",f"- Correction: {row['fix']}",'- Files: '+', '.join(f'`{file}`' for file in row['files']),'- Retest evidence: '+('; '.join(f'`{item}`' for item in row['evidence']) or 'Pending.'),''])
    (ROOT/'BUSINESS_SUITE_BUG_FIXES.md').write_text('\n'.join(fixes),encoding='utf-8')
    regression=['# Business Suite regression results','',f"Unique latest backend test nodes: {len(records)} — {dict(backend)}.",f"Frontend harnesses: {len(front)} — {dict(browser)}.",'',
                '## Completed runs','']
    typecheck_path=OUT/'business-suite-frontend-typecheck.json'
    if typecheck_path.exists():
        typecheck=json.loads(typecheck_path.read_text(encoding='utf-8-sig'))
        regression.append(f"- Frontend `npm run typecheck`: exit {typecheck['exit_code']}; main app, Node and interns-hub configurations. Evidence: `backend/outputs/business-suite-frontend-typecheck.json` and `.log`.")
    for name in [*ARTIFACTS, FINAL.name]:
        rows=junit(OUT/name)
        if rows: regression.append(f"- `{name}`: {len(rows)} test nodes — {dict(Counter(row['status'] for row in rows))}.")
    regression.extend(['','## Full repository regression','',f"Observed progress: {progress['observed_progress_entries']}. Completed: {progress['completed']}.",
                       'The final run uses four isolated workers on the current code. Its results take precedence over targeted runs. The stopped serial pre-fix baseline reached 28%; its log is retained as historical evidence.','',
                       '## Reproduce','', '`powershell -File backend/scripts/run_business_suite_postgres_qa.ps1` creates a fresh localhost-only QA cluster, runs the selected real PostgreSQL scenarios, stops it, and retains artifacts.',
                       '`backend/venv/Scripts/python.exe backend/scripts/run_business_suite_frontend_qa.py` runs all selected isolated frontend harnesses.',
                       'From `backend`: `venv/Scripts/python.exe -m pytest -q --junitxml=outputs/full-regression.xml` runs the full repository suite. It is considerably larger than the business acceptance matrix.',
                       'From `frontend`: `npm run test:common-routes` and `npx tsc --noEmit`.','',
                       'No production migration, verified production backup or deployment was performed; none was needed for these code-only fixes.'])
    (ROOT/'BUSINESS_SUITE_REGRESSION_RESULTS.md').write_text('\n'.join(regression),encoding='utf-8')
    pending=['# Business Suite pending issues','', '**Release remains blocked.** A clean run does not create missing functionality.','',
             '## Required implementation and reconciliation','',
             '- Critical: POS checkout needs one atomic, idempotent workflow that issues the native invoice, persists split/partial receipts, updates stock and posts through existing FAM controls. Current checkout records a sales order and payment-mode metadata, not a financial receipt.',
             '- High: implement employee-backed service appointments, working hours/leave/resource conflicts, lifecycle, common calendar projection and completed-service billing.',
             '- High: implement package/membership entitlement expiry, redemption uniqueness, reversals and history.',
             '- High: complete AMC asset links, HRMS technician identity, visit scheduling and renewal/invoice integration using existing contracts/recurrence/tasks.',
             '- High: reconcile FAM legacy party IDs with canonical CRM customer/vendor identities without automatic name/phone merging.',
             '- High: approve Sales lead-access adapters and complete CRM task/note associations without broadening underlying permissions.',
             '- High: complete effective-dated tax classifications and inclusive-pricing contracts. Existing historical invoice tax values must not be recalculated.',
             ('- Full repository regression completed; remaining failures, if listed below, require correction and retest.' if progress['completed'] else '- Full repository regression must finish and all remaining failures must be retested against the final working tree.'),'',
             '## Requested cases still blocked or not run','']
    pending.extend(f"- {row['id']}: {row['case']} — {row['actual']}" for row in results if row['status'] in {'BLOCKED','NOT RUN','FAIL'})
    failed=[row for row in records.values() if row['status']=='FAIL']
    if failed:
        pending.extend(['','## Remaining executed failures',''])
        pending.extend(f"- `{row['node']}` — {row['actual']} (`{row['artifact']}`)." for row in failed)
    (ROOT/'BUSINESS_SUITE_PENDING_ISSUES.md').write_text('\n'.join(pending),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()

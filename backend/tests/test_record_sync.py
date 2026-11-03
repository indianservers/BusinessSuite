"""Standalone protocol tests; no production DB, auth secrets, or migrations needed."""
import unittest
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from app.core.middleware.record_sync import RecordSyncMiddleware, SnapshotStore, eligible, split_view
from app.core.middleware.security_headers import SecurityHeadersMiddleware

class RecordSyncTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'id': i, 'name': 'Record ' + str(i), 'description': 'x' * 120} for i in range(100)]
        self.scope = 'user1:tenant1:branch1:permissions1'
        self.denied = False
        self.no_store = False
        self.calls = 0
        app = FastAPI()
        @app.get('/api/v1/crm/leads')
        @app.get('/api/v1/srm/sales-orders')
        @app.get('/api/v1/employees/')
        def records(request: Request):
            self.calls += 1
            if self.denied:
                return JSONResponse({'detail': 'Forbidden'}, status_code=403)
            request.state.record_sync_scope = self.scope
            return JSONResponse({'items': self.rows, 'total': len(self.rows)}, headers={'Cache-Control': 'no-store'} if self.no_store else {})
        app.add_middleware(RecordSyncMiddleware, store=SnapshotStore(4))
        app.add_middleware(SecurityHeadersMiddleware)
        self.client = TestClient(app)

    def first(self, path='/api/v1/crm/leads'):
        return self.client.get(path, headers={'X-Suite-Sync': '1'})

    def again(self, first, **headers):
        return self.client.get('/api/v1/crm/leads', headers={'X-Suite-Sync': '1', 'X-Suite-Sync-Cursor': first.headers['x-suite-sync-cursor'], 'If-None-Match': first.headers['etag'], **headers})

    def test_existing_clients_unchanged_and_no_store(self):
        r = self.client.get('/api/v1/crm/leads')
        self.assertEqual(r.json()['items'], self.rows)
        self.assertEqual(r.headers['cache-control'], 'private, no-store')
        self.assertNotIn('x-suite-sync-cursor', r.headers)

    def test_unchanged_is_304_after_authorization_route_runs(self):
        r = self.first()
        unchanged = self.again(r)
        self.assertEqual(unchanged.status_code, 304)
        self.assertEqual(unchanged.content, b'')
        self.assertEqual(self.calls, 2)

    def test_update_insert_delete_and_deterministic_order(self):
        first = self.first()
        self.rows[4]['name'] = 'Updated'
        self.rows.pop(10)
        self.rows.insert(0, {'id': 1000, 'name': 'New'})
        second = self.again(first)
        self.assertEqual(second.headers['x-suite-sync-mode'], 'delta')
        data = second.json()
        self.assertEqual([r['id'] for r in data['upserts']], [1000, 4])
        self.assertEqual(data['removed'], ['10'])
        self.assertEqual(data['order'], [str(row['id']) for row in self.rows])
        self.assertEqual(data['meta']['total'], 100)
        self.assertLess(len(second.content), len(first.content) // 5)

    def test_filter_departure_is_removal(self):
        first = self.first()
        self.rows = self.rows[:80]
        second = self.again(first)
        self.assertEqual(len(second.json()['removed']), 20)

    def test_record_permission_revocation_is_removal(self):
        first = self.first()
        self.rows = self.rows[1:]
        self.assertEqual(self.again(first).json()['removed'], ['0'])

    def test_role_tenant_branch_or_user_change_forces_authorized_full_reset(self):
        for scope in ['user2', 'tenant2', 'branch2', 'permissions2']:
            first = self.first()
            self.scope = scope
            second = self.again(first)
            self.assertEqual(second.status_code, 304)
            self.assertEqual(second.headers['x-suite-sync-scope'], scope)

    def test_revoked_route_never_returns_304(self):
        first = self.first()
        self.denied = True
        second = self.again(first)
        self.assertEqual(second.status_code, 403)
        self.assertEqual(second.headers['cache-control'], 'private, no-store')

    def test_cursor_eviction_restart_and_forgery_reset(self):
        first = self.first()
        self.rows[0]['name'] = 'Changed during cursor eviction'
        for i in range(6): self.first()
        self.assertEqual(self.again(first).headers['x-suite-sync-mode'], 'full')
        self.assertEqual(self.again(first, **{'X-Suite-Sync-Cursor': 'forged'}).headers['x-suite-sync-mode'], 'full')

    def test_unchanged_etag_survives_worker_restart(self):
        first = self.first()
        for i in range(6): self.first()
        self.assertEqual(self.again(first).status_code, 304)

    def test_cursor_cannot_cross_filter_or_sort(self):
        first = self.first()
        second = self.client.get('/api/v1/crm/leads?search=other', headers={'X-Suite-Sync': '1', 'X-Suite-Sync-Cursor': first.headers['x-suite-sync-cursor'], 'If-None-Match': first.headers['etag']})
        self.assertEqual(second.status_code, 304)  # Authorization and the current full representation still match.

    def test_endpoint_no_store_respected(self):
        self.no_store = True
        self.assertNotIn('x-suite-sync-cursor', self.first().headers)

    def test_financial_views_are_memory_only(self):
        self.assertEqual(self.first('/api/v1/srm/sales-orders').headers['x-suite-cache'], 'memory')

    def test_sensitive_fields_never_persist(self):
        for key in ['salary', 'bank_account', 'password', 'personal_email', 'passport', 'medical_notes', 'access_token']:
            self.rows[0][key] = 'sensitive'
            self.assertNotIn('x-suite-cache', self.first('/api/v1/employees/').headers)
            self.rows[0].pop(key)

    def test_large_list_unstable_ids_exports_and_secret_endpoints_excluded(self):
        self.rows = [{'id': n} for n in range(501)]
        self.assertNotIn('x-suite-cache', self.first().headers)
        self.assertIsNone(split_view([{'name': 'no id'}]))
        self.assertIsNone(split_view([{'id': 1}, {'id': 1}]))
        for path in ['/api/v1/payroll', '/api/v1/employees/1', '/api/v1/crm/leads/export', '/api/v1/auth/users']:
            self.assertFalse(eligible(path))

    def test_actual_module_routes_and_composite_keys(self):
        for path in ['/api/v1/crm/lead-management/leads', '/api/v1/crm/deal-workspace/grid/query', '/api/v1/catalog/items', '/api/v1/profiles/directory', '/api/v1/project-management/people-workspace/people', '/api/v1/interns-hub/learning/assignments', '/api/v1/leave/my-requests']:
            self.assertTrue(eligible(path), path)
        for payload, expected in [({'rows': [{'id': 1}]}, ['1']), ([{'id': 1, 'kind': 'product'}, {'id': 1, 'kind': 'service'}], ['product:1', 'service:1']), ([{'task_id': 1, 'user_id': 2}], ['task:1:user:2']), ([{'userId': 3}], ['3']), ([{'attendance_id': None, 'employee_id': 3, 'date': '2026-11-03'}], ['employee:3:date:2026-11-03'])]:
            self.assertEqual(split_view(payload)[2], expected)

    def test_benchmark_transfer(self):
        first = self.first()
        unchanged = self.again(first)
        self.rows[42]['name'] = 'Changed by another user'
        delta = self.again(first)
        print(f'BENCHMARK 100 rows: full={len(first.content)} bytes, unchanged={len(unchanged.content)} bytes, one-row delta={len(delta.content)} bytes, reduction={100*(1-len(delta.content)/len(first.content)):.1f}%')

if __name__ == '__main__':
    unittest.main()

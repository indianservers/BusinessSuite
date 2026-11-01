"""The production page audit must never invoke jobs, sends or callback URLs."""
import importlib.util
from pathlib import Path
import pytest

path = Path(__file__).resolve().parents[2] / 'qa/audit_page_database_reads.py'
spec = importlib.util.spec_from_file_location('page_read_audit', path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


@pytest.mark.parametrize('path', [
    '/api/v1/internal/email-dispatch', '/api/v1/internal/cron',
    '/api/v1/auth/verify-email', '/api/v1/crm/oauth/callback',
    '/api/v1/forms/public/{token}', '/api/v1/project-management/realtime',
    '/api/v1/files/download/{id}', '/api/v1/hrms/payroll/export',
    '/api/v1/automation/process', '/api/v1/crm/leads/{id}/convert',
    '/api/v1/project-management/providers/{id}/test',
    '/api/v1/communication/messages/{id}/mark-read',
])
def test_audit_excludes_non_page_side_effects(path):
    assert audit.DENY.search(path) or audit.SIDE_EFFECT_WORDS.search(path)


@pytest.mark.parametrize('path', [
    '/api/v1/project-management/projects', '/api/v1/project-management/tasks',
    '/api/v1/project-management/task-workspace/tasks/{task_id}',
    '/api/v1/employees/', '/api/v1/crm/leads', '/api/v1/fam/dashboard',
])
def test_audit_allows_page_list_and_detail_reads(path):
    assert not audit.DENY.search(path)
    assert not audit.SIDE_EFFECT_WORDS.search(path)

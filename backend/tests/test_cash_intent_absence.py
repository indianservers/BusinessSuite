"""Native absence evidence is exact, keyed and never inferred from an old error body."""
import pytest
from app.apps.srm.models import SRMPOSCashMovement, SRMPOSSession
from tests.test_cash_movement_intents import till, command, PATH

FIELDS = ('x-cash-intent-outcome','x-cash-intent-request-key','x-cash-intent-session-id')


def close(client, till, cash='100'):
    result=client.post('/api/v1/srm/pos/cashier-closing', headers=till[0],
        json={'session_id':till[1],'counted_cash':cash})
    assert result.status_code==201,result.text


def test_absent_key_closed_register_preserves_old_body_and_proves_exact_absence(client, db, till):
    body=command(till)
    close(client,till)
    result=client.post(PATH,headers=till[0],json=body)
    assert result.status_code==400,result.text
    assert result.json()=={'detail':'Cannot add cash movement to a closed session'}
    assert [result.headers[field] for field in FIELDS]==['not_created',body['request_key'],str(till[1])]
    assert db.query(SRMPOSCashMovement).count()==0


def test_legacy_keyless_closed_error_has_no_absence_proof(client, db, till):
    body=command(till);body.pop('request_key')
    close(client,till)
    result=client.post(PATH,headers=till[0],json=body)
    assert result.status_code==400,result.text
    assert result.json()=={'detail':'Cannot add cash movement to a closed session'}
    assert all(field not in result.headers for field in FIELDS)


@pytest.mark.parametrize('changed',[False,True])
def test_committed_closed_replay_and_changed_body_never_claim_not_created(client, db, till, changed):
    body=command(till)
    first=client.post(PATH,headers=till[0],json=body);assert first.status_code==201,first.text
    close(client,till,'110')
    result=client.post(PATH,headers=till[0],json={**body,'amount':'11'} if changed else body)
    assert result.status_code==(409 if changed else 201),result.text
    if not changed:assert result.json()['movement_id']==first.json()['movement_id']
    assert all(field not in result.headers for field in FIELDS)
    assert db.query(SRMPOSCashMovement).count()==1


def test_ambiguous_native_currency_never_proves_absence(client, db, till):
    first=client.post(PATH,headers=till[0],json=command(till,amount='2'))
    assert first.status_code==201,first.text
    close(client,till,'102')
    row=db.get(SRMPOSSession,till[1]);row.metadata_json={**row.metadata_json,'cash_currency':'USD'};db.commit()
    result=client.post(PATH,headers=till[0],json=command(till))
    assert result.status_code==409,result.text
    assert all(field not in result.headers for field in FIELDS)


def test_authority_change_during_absence_recheck_never_proves_absence(client, db, till, monkeypatch):
    from app.apps.srm import cash_movement_intents as intents
    close(client,till)
    original=intents._authority;calls=[]
    def revoke(db,user,*args):
        calls.append(1)
        if len(calls)==2:
            user.role.permissions=[p for p in user.role.permissions if p.name!='srm_manage'];db.flush()
        return original(db,user,*args)
    monkeypatch.setattr(intents,'_authority',revoke)
    result=client.post(PATH,headers=till[0],json=command(till))
    assert result.status_code==403,result.text
    assert all(field not in result.headers for field in FIELDS)
    assert db.query(SRMPOSCashMovement).count()==0


def test_actual_browser_can_read_absence_proof_headers(client, db, till):
    close(client,till)
    result=client.post(PATH,headers={**till[0],'Origin':'http://localhost:5173'},json=command(till))
    assert result.status_code==400,result.text
    exposed=result.headers.get('access-control-expose-headers','').lower()
    assert all(field in exposed for field in FIELDS)

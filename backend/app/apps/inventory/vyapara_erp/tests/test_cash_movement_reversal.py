from test_core import app_with_db,login
from app.extensions import db
from app.models import CashMovement,POSSession,AuditLog


def test_cash_movement_reversal_preserves_history_and_net_drawer():
    app=app_with_db()
    with app.app_context():
        session=POSSession(session_no='QA-233',opened_by=1,register_id=1,status='Open',opening_cash=1000,total_cash=1180)
        db.session.add(session);db.session.commit();sid=session.id
        with app.test_client() as client:
            login(client)
            client.post('/pos/cash-movement',data={'movement_type':'Cash In','amount':'500','reason':'Mistake'})
            movement=CashMovement.query.one();mid=movement.id
            assert client.post(f'/pos/cash-movements/{mid}/reverse',data={'reason':''}).status_code==400
            response=client.post(f'/pos/cash-movements/{mid}/reverse',data={'reason':'Entered in error'},follow_redirects=True)
            assert b'Both entries remain' in response.data
            assert client.post(f'/pos/cash-movements/{mid}/reverse',data={'reason':'Repeat'}).status_code==400
            assert CashMovement.query.count()==2
            assert AuditLog.query.filter_by(action='Reverse',module='CashMovement',record_id=mid).one().new_data['reason']=='Entered in error'
            client.post('/pos/close-session',data={'closing_cash':'2180'})
            db.session.expire_all();saved=db.session.get(POSSession,sid)
            assert float(saved.expected_closing_cash)==2180 and float(saved.cash_difference)==0
            assert client.post(f'/pos/cash-movements/{mid}/reverse',data={'reason':'Closed'}).status_code==400
            history=client.get('/pos/sessions')
            assert b'Mistake' in history.data and b'Reversal of #1' in history.data and b'Reversed' in history.data

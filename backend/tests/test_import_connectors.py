import time
from app.shared import import_connectors as connectors
from tests.test_import_workspace import import_headers


def test_connectors_require_setup_and_keep_tokens_private(client,db,import_headers,monkeypatch):
    for key in ("IMPORT_QUICKBOOKS_CLIENT_ID","IMPORT_QUICKBOOKS_CLIENT_SECRET","IMPORT_QUICKBOOKS_REDIRECT_URI"):
        monkeypatch.delenv(key,raising=False)
    response=client.get("/api/v1/imports/fam/connections",headers=import_headers)
    assert response.status_code==200,response.text
    assert response.json()["providers"][0]["configured"] is False
    assert client.post("/api/v1/imports/fam/connections/quickbooks/start",headers=import_headers,json={}).status_code==409
    monkeypatch.setenv("IMPORT_QUICKBOOKS_CLIENT_ID","fixture-client")
    monkeypatch.setenv("IMPORT_QUICKBOOKS_CLIENT_SECRET","fixture-secret")
    monkeypatch.setenv("IMPORT_QUICKBOOKS_REDIRECT_URI","https://suite.example.com/fam/import-data")
    started=client.post("/api/v1/imports/fam/connections/quickbooks/start",headers=import_headers,json={})
    assert started.status_code==200,started.text
    from urllib.parse import urlsplit,parse_qs
    query=parse_qs(urlsplit(started.json()["url"]).query)
    assert "fixture-secret" not in started.text
    state=query["state"][0]
    def provider(method,url,**kwargs):
        if method=="POST":return {"access_token":"private-access","refresh_token":"private-refresh","expires_in":3600}
        assert url=="https://quickbooks.api.intuit.com/v3/company/123/query"
        return {"QueryResponse":{"Account":[{"Id":"10","AcctNum":"1000","Name":"Cash","AccountType":"Bank"}]}}
    monkeypatch.setattr(connectors,"request_json",provider)
    completed=client.post("/api/v1/imports/fam/connections/complete",headers=import_headers,json={"provider":"quickbooks","state":state,"code":"single-use-code","account_id":"123"})
    assert completed.status_code==200,completed.text
    assert "private-" not in completed.text
    assert client.post("/api/v1/imports/fam/connections/complete",headers=import_headers,json={"provider":"quickbooks","state":state,"code":"single-use-code","account_id":"123"}).status_code==409
    identity=completed.json()["id"]
    fetched=client.post(f"/api/v1/imports/fam/connections/{identity}/fetch",headers=import_headers,json={"entity":"ledgers"})
    assert fetched.status_code==200,fetched.text
    assert fetched.json()["status"]=="uploaded"
    assert fetched.json()["table"]["rows"][0][:3]==["1000","Cash","asset"]
    assert "private-" not in client.get("/api/v1/imports/fam/connections",headers=import_headers).text
    from app.shared.import_models import ImportConnection
    record=db.get(ImportConnection,identity)
    assert "private-" not in record.secret
    assert client.delete(f"/api/v1/imports/fam/connections/{identity}",headers=import_headers).status_code==200


def test_zoho_region_and_external_ids_are_not_trusted(client,import_headers,monkeypatch):
    for key,value in (("CLIENT_ID","fixture"),("CLIENT_SECRET","fixture"),("REDIRECT_URI","https://suite.example.com/fam/import-data")):
        monkeypatch.setenv("IMPORT_ZOHO_"+key,value)
    assert client.post("/api/v1/imports/fam/connections/zoho/start",headers=import_headers,json={"region":"evil.example"}).status_code==422
    response=client.post("/api/v1/imports/fam/connections/zoho/start",headers=import_headers,json={"region":"in"})
    assert response.status_code==200
    assert response.json()["url"].startswith("https://accounts.zoho.in/")
    from urllib.parse import urlsplit,parse_qs
    state=parse_qs(urlsplit(response.json()["url"]).query)["state"][0]
    denied=client.post("/api/v1/imports/fam/connections/complete",headers=import_headers,json={"provider":"zoho","state":state,"code":"code","account_id":"../other-account"})
    assert denied.status_code==422


import pytest
from tests.test_import_workspace import preview, action


@pytest.mark.parametrize("provider", ["quickbooks", "zoho"])
@pytest.mark.parametrize("entity", ["ledgers", "outstanding_bills"])
def test_provider_finance_review_duplicate_and_revoke(client, db, import_headers, monkeypatch, provider, entity):
    from urllib.parse import urlsplit, parse_qs
    from app.apps.fam.models import FAMLedgerGroup, FAMLedger, FAMParty, FAMBillReference
    from app.shared.import_models import ImportConnection
    from test_identity_utils import own_workflow_records
    from app.shared.import_catalog import get_spec

    group=FAMLedgerGroup(company_id=1,group_code="CONNECTOR",group_name="Connector assets",nature="asset")
    db.add(group);db.flush()
    ledger=FAMLedger(company_id=1,ledger_code="CONNECTOR-AR",ledger_name="Connector receivables",ledger_group_id=group.id,nature="asset")
    db.add(ledger);db.flush()
    party=FAMParty(company_id=1,party_type="customer",party_code="CONNECTOR-CUSTOMER",legal_name="Provider customer",ledger_id=ledger.id)
    db.add(party);db.flush();own_workflow_records(db,group,ledger,party);db.commit()
    prefix="IMPORT_QUICKBOOKS" if provider=="quickbooks" else "IMPORT_ZOHO"
    for key in ("CLIENT_ID","CLIENT_SECRET","REDIRECT_URI"):
        monkeypatch.setenv(prefix+"_"+key,"https://suite.example.com/fam/import-data" if key=="REDIRECT_URI" else "fixture")
    started=client.post(f"/api/v1/imports/fam/connections/{provider}/start",headers=import_headers,json={"region":"in"})
    assert started.status_code==200,started.text
    state=parse_qs(urlsplit(started.json()["url"]).query)["state"][0]
    calls=[]
    def provider_request(method,url,**kwargs):
        calls.append((method,url,kwargs))
        if method=="POST":
            return {"access_token":"secret-access","refresh_token":"secret-refresh","expires_in":3600}
        if provider=="quickbooks":
            assert url=="https://quickbooks.api.intuit.com/v3/company/123/query"
            assert kwargs["headers"]["Authorization"]=="Bearer secret-access"
            if entity=="ledgers":
                row={"Id":"900001","AcctNum":"IMPORTED-ACCOUNT","Name":"Provider cash","AccountType":"Bank"}
                return {"QueryResponse":{"Account":[row,row]}}
            row={"Id":"900002","DocNumber":"PROVIDER-INV","TxnDate":"2026-11-01","DueDate":"2026-12-01","TotalAmt":1000,"Balance":600,"CustomerRef":{"value":"999999"},"CurrencyRef":{"value":"INR"}}
            return {"QueryResponse":{"Invoice":[row,row]}}
        assert url.startswith("https://www.zohoapis.in/books/v3/")
        assert kwargs["params"]["organization_id"]=="123"
        assert kwargs["headers"]["Authorization"]=="Zoho-oauthtoken secret-access"
        if entity=="ledgers":
            row={"account_id":"900001","account_code":"IMPORTED-ACCOUNT","account_name":"Provider cash","account_type":"bank"}
            return {"code":0,"chartofaccounts":[row,row],"page_context":{"has_more_page":False}}
        row={"invoice_id":"900002","invoice_number":"PROVIDER-INV","date":"2026-11-01","due_date":"2026-12-01","total":1000,"balance":600,"customer_id":"999999","currency_code":"INR"}
        return {"code":0,"invoices":[row,row],"page_context":{"has_more_page":False}}
    monkeypatch.setattr(connectors,"request_json",provider_request)
    connected=client.post("/api/v1/imports/fam/connections/complete",headers=import_headers,json={"provider":provider,"state":state,"code":"fixture-code","account_id":"123"})
    assert connected.status_code==200,connected.text
    connection_id=connected.json()["id"]
    # Force a refresh as part of the full provider-to-staging flow.
    connection=db.get(ImportConnection,connection_id)
    tokens=connectors.unseal(connection);tokens["expires_at"]=0
    connection.secret=connectors.seal(tokens);db.commit()
    model=FAMLedger if entity=="ledgers" else FAMBillReference
    before=db.query(model).count()
    def fetch():
        result=client.post(f"/api/v1/imports/fam/connections/{connection_id}/fetch",headers=import_headers,json={"entity":entity})
        assert result.status_code==200,result.text
        assert "secret-access" not in result.text and "secret-refresh" not in result.text
        return result.json()
    batch=fetch()
    assert batch["status"]=="uploaded" and batch["source"]==provider
    assert db.query(model).count()==before, "Fetch must only stage data"
    assert any(kwargs.get("data",{}).get("grant_type")=="refresh_token" for _,_,kwargs in calls)
    assert action(client,import_headers,batch,"commit").status_code==409
    fields=get_spec("fam",entity).fields
    mapping={field["key"]:field["key"] for field in fields if field["key"] in batch["table"]["headers"]}
    missing=client.post(f"/api/v1/imports/fam/batches/{batch['id']}/preview",headers=import_headers,json={"version":batch["version"],"mapping":mapping})
    assert missing.status_code==422, "Local group/party mappings must be required"
    constants={"ledger_group_id":str(group.id)} if entity=="ledgers" else {"party_id":str(party.id),"ledger_id":str(ledger.id)}
    invalid_constants={**constants, next(iter(constants)):"999999"}
    invalid=preview(client,import_headers,batch,mapping,constants=invalid_constants)
    assert not invalid["preview"]["can_import"], "Provider IDs cannot substitute for local references"
    assert action(client,import_headers,invalid,"commit").status_code==409
    ready=preview(client,import_headers,invalid,mapping,constants=constants)
    assert ready["preview"]["can_import"],ready["preview"]
    assert ready["preview"]["counts"]=={"create":1,"skip":1}
    assert db.query(model).count()==before, "Preview must not write Finance records"
    imported=action(client,import_headers,ready,"commit")
    assert imported.status_code==200,imported.text
    assert db.query(model).count()==before+1
    if entity=="outstanding_bills":
        native=db.query(FAMBillReference).filter_by(bill_number="PROVIDER-INV").one()
        assert native.party_id==party.id and native.ledger_id==ledger.id
        assert float(native.outstanding_amount)==600
    duplicate=fetch()
    blocked=preview(client,import_headers,duplicate,mapping,constants=constants,duplicates="error")
    assert not blocked["preview"]["can_import"]
    assert action(client,import_headers,blocked,"commit").status_code==409
    skipped=preview(client,import_headers,blocked,mapping,constants=constants,duplicates="skip")
    assert skipped["preview"]["counts"]=={"skip":2}
    assert db.query(model).count()==before+1
    revoked=action(client,import_headers,imported.json(),"revoke")
    assert revoked.status_code==200,revoked.text
    assert db.query(model).count()==before
    again=preview(client,import_headers,skipped,mapping,constants=constants)
    assert again["preview"]["counts"]=={"create":1,"skip":1}
    assert action(client,import_headers,revoked.json(),"revoke").status_code==409
    # A later local edit blocks revoke without partially deleting the record.
    reimported=action(client,import_headers,again,"commit")
    assert reimported.status_code==200,reimported.text
    native=db.query(model).filter_by(**({"ledger_code":"IMPORTED-ACCOUNT"} if entity=="ledgers" else {"bill_number":"PROVIDER-INV"})).one()
    key="ledger_name" if entity=="ledgers" else "outstanding_amount"
    setattr(native,key,"Edited after import" if entity=="ledgers" else 500)
    db.commit()
    denied=action(client,import_headers,reimported.json(),"revoke")
    assert denied.status_code==409,denied.text
    assert db.query(model).count()==before+1

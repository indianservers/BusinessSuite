import pytest
from fastapi import HTTPException
from app.ai_operator.agent_mcp import Binding,safe_schema,rpc


@pytest.mark.parametrize('schema',[{'$ref':'https://example.com/schema'},{'pattern':'(a+)+$'},{'properties':{'x':{'patternProperties':{}}}}])
def test_discovery_rejects_external_or_unbounded_schema(schema):
    with pytest.raises(HTTPException) as exc:safe_schema(schema)
    assert exc.value.status_code==422


def test_rpc_matches_response_and_accepts_bounded_sse(monkeypatch):
    from app.ai_operator.service import digest
    ident=digest({'key':'test','method':'tools/list'})[:24]
    def invoke(*args,**kwargs):
        assert kwargs['confirmed'] is True
        assert args[4]['headers']['MCP-Protocol-Version']=='2025-11-25'
        return {'body':'data: {"jsonrpc":"2.0","id":"'+ident+'","result":{"tools":[]}}\n\n','headers':{}}
    monkeypatch.setattr('app.apps.power_apps.integrations.service.invoke',invoke)
    config=Binding(name='Test',connection_id=1,endpoint='https://example.com/mcp')
    assert rpc(None,None,None,config,'tools/list',{},'test')[0]=={'tools':[]}


def test_rpc_rejects_unmatched_response(monkeypatch):
    monkeypatch.setattr('app.apps.power_apps.integrations.service.invoke',lambda *a,**k:{'body':{'jsonrpc':'2.0','id':'wrong','result':{}}})
    with pytest.raises(HTTPException):rpc(None,None,None,Binding(name='Test',connection_id=1,endpoint='https://example.com/mcp'),'tools/list',{},'test')

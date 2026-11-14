"""Customer recipient names are literal text, not SQL patterns."""
import pytest
from tests.test_import_workspace import import_headers
BASE='/api/v1/communication/customers'
@pytest.mark.parametrize("needle",["%","_",chr(92),chr(92)+"%",chr(92)+"_","/"])
def test_customer_recipient_name_literal(client,db,import_headers,needle):
    ids=[]
    for name in ["Ordinary customer","QA"+needle+"Literal"]:
        response=client.post(BASE+'/recipients',headers=import_headers,json={
            'name':name,'email':'synthetic@example.com','preferences':{},'consent_source':'Synthetic QA'})
        assert response.status_code==201,response.text
        ids.append(response.json()['id'])
    response=client.get(BASE+'/recipients',headers=import_headers,params={'search':needle})
    assert response.status_code==200,response.text
    assert [r['id'] for r in response.json()['items']]==[ids[1]]
    response=client.get(BASE+'/recipients',headers=import_headers,params={'search':'ORDINARY'})
    assert response.status_code==200,response.text
    assert [r['id'] for r in response.json()['items']]==[ids[0]]


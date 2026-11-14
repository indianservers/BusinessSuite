"""Literal resource searches preserve environment and company filters."""
import pytest
from tests.test_power_apps import actors,create,ROOT
@pytest.mark.parametrize("needle",[chr(92),chr(92)+"%",chr(92)+"_","%","_","/"])
def test_resource_name_search_literal(client,actors,needle):
    ordinary=create(client,actors[0],name="Ordinary resource")
    match=create(client,actors[0],name="QA"+needle+"Literal")
    create(client,actors[1],name="QA"+needle+"Literal")
    create(client,actors[0],name="QA"+needle+"Literal",env="testing")
    response=client.get(ROOT+'/automations',headers=actors[0],params={'search':needle,'limit':1})
    assert response.status_code==200,response.text
    assert response.json()['total']==1
    assert [r['id'] for r in response.json()['items']]==[match['id']]
    ordinary_result=client.get(ROOT+'/automations',headers=actors[0],params={'search':'ORDINARY'})
    assert ordinary_result.status_code==200,ordinary_result.text
    assert [r['id'] for r in ordinary_result.json()['items']]==[ordinary['id']]

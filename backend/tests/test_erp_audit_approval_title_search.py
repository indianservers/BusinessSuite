"""Approval inbox searches preserve literal titles and actor scopes."""
import pytest
from tests.test_power_approvals import actors,db,policy,users,ROOT,approval_actor_actions
@pytest.mark.parametrize('needle',[chr(92),chr(92)+'%',chr(92)+'_','%','_','/'])
def test_approval_title_search_literal(client,db,actors,needle):
    p=policy(client,actors[0],[users(db)[3]])
    ids=[]
    for index,title in enumerate(['Ordinary request','QA'+needle+'Literal']):
        r=client.post(ROOT+'/requests',headers=actors[0],json={'policy_id':p['id'],'title':title,'fields':{'amount':42},'request_key':'literal-'+str(index)})
        assert r.status_code==201,r.text
        ids.append(r.json()['id'])
    from tests.test_power_runtime import drain
    drain(db)
    for actor,scope in [(actors[0],'submitted'),(actors[3],'assigned')]:
        response=client.get(ROOT+'/requests',headers=actor,params={'search':needle,'scope':scope,'limit':1})
        assert response.status_code==200,response.text
        assert response.json()['total']==1,(scope,response.text)
        assert [r['id'] for r in response.json()['items']]==[ids[1]]
    hidden=client.get(ROOT+'/requests',headers=actors[1],params={'search':needle})
    assert hidden.status_code==200,hidden.text
    assert hidden.json()['items']==[]

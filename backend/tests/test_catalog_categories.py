from tests.test_shared_catalog import headers, item, create, ROOT
from app.apps.srm.models import SRMProduct


def tree():
    return [{"id":"hardware","name":"Hardware","children":[{"id":"laptops","name":"Laptops"}]},{"id":"consulting","name":"Consulting","children":[]}]

def test_multiple_categories_filter_and_rename(client, db, headers):
    r=client.put(ROOT+"/categories?source=srm",headers=headers,json={"version":0,"categories":tree()})
    assert r.status_code==200,r.text
    product=create(client,headers,item(category="",category_ids=["hardware","consulting","laptops"]))
    assert product["categories"]==["Hardware","Consulting","Hardware > Laptops"]
    for label in product["categories"]:
        r=client.get(ROOT+"/items",headers=headers,params={"source":"srm","category":label,"include_facets":True})
        assert r.status_code==200,r.text
        assert r.json()["total"]==1
        assert r.json()["items"][0]["category_ids"]==["hardware","consulting","laptops"]
    changed=tree();changed[0]["name"]="Equipment"
    r=client.put(ROOT+"/categories?source=srm",headers=headers,json={"version":1,"categories":changed})
    assert r.status_code==200,r.text
    result=client.get(f"{ROOT}/items/product/{product['id']}?source=srm",headers=headers).json()
    assert result["categories"]==["Equipment","Consulting","Equipment > Laptops"]
    r=client.put(ROOT+"/categories?source=srm",headers=headers,json={"version":1,"categories":changed})
    assert r.status_code==409
    r=client.put(ROOT+"/categories?source=srm",headers=headers,json={"version":2,"categories":[]})
    assert r.status_code==409


def test_choices_tenant_isolation_invalid_ids_and_delete(client,db,headers):
    foreign=SRMProduct(organization_id=99,sku="FOREIGN",item_name="Hidden",category_name="Secret category",product_type="stock",active=True)
    db.add(foreign);db.commit()
    r=client.get(ROOT+"/categories?source=srm",headers=headers)
    assert r.status_code==200,r.text
    assert "Secret category" not in r.text
    r=client.post(ROOT+"/items?source=srm",headers=headers,json=item(category_ids=["made-up"]))
    assert r.status_code==422,r.text
    r=client.put(ROOT+"/categories?source=srm",headers=headers,json={"version":0,"categories":tree()})
    assert r.status_code==200,r.text
    # Unused children and categories can be deleted.
    r=client.put(ROOT+"/categories?source=srm",headers=headers,json={"version":1,"categories":[]})
    assert r.status_code==200,r.text
    assert r.json()["categories"]==[]


def test_legacy_choices_are_preserved_and_assignable(client,db,headers):
    product=create(client,headers)
    choices=client.get(ROOT+"/categories?source=srm",headers=headers).json()
    legacy=next(n for n in choices["categories"] if n["name"]=="Software")
    payload={**product,"category_ids":[legacy["id"]]};payload.pop("id")
    r=client.put(f"{ROOT}/items/product/{product['id']}?source=srm",headers=headers,json=payload)
    assert r.status_code==200,r.text
    assert r.json()["categories"]==["Software"]
    duplicate=client.post(f"{ROOT}/items/product/{product['id']}/duplicate?source=srm",headers=headers,json={})
    assert duplicate.status_code==201,duplicate.text
    assert duplicate.json()["category_ids"]==[legacy["id"]]

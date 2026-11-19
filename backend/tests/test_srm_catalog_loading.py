from sqlalchemy import event
from tests.test_erp_audit_procurement import procurement


def test_catalog_relationship_reads_are_batched(client, db, procurement):
    headers, _, _ = procurement
    expected={}
    base="/api/v1/srm/inventory"
    for index in range(6):
        category=client.post(base+"/categories",headers=headers,json={"category_code":f"LOAD-{index}","category_name":f"Loading category {index}"})
        assert category.status_code==201,category.text
        warehouse=client.post(base+"/warehouses",headers=headers,json={"warehouse_code":f"LOAD-{index}","warehouse_name":f"Loading warehouse {index}"})
        assert warehouse.status_code==201,warehouse.text
        product=client.post(base+"/items",headers=headers,json={"sku":f"LOAD-{index}","item_name":f"Loading product {index}","category_id":category.json()["id"],"default_warehouse_id":warehouse.json()["id"]})
        assert product.status_code==201,product.text
        expected[product.json()["id"]]=(category.json()["id"],warehouse.json()["id"])
    statements=[]
    def capture(connection,cursor,statement,parameters,context,many):
        statements.append(statement)
    engine=db.get_bind()
    event.listen(engine,"before_cursor_execute",capture)
    try:
        response=client.get(base+"/items",params={"search":"Loading product","page":1,"per_page":200},headers=headers)
    finally:
        event.remove(engine,"before_cursor_execute",capture)
    assert response.status_code==200,response.text
    rows=response.json()["items"]
    assert len(rows)==6
    assert {row["id"]:(row["category"]["id"],row["default_warehouse"]["id"]) for row in rows}==expected
    for table in ("srm_product_categories","srm_warehouses"):
        assert sum(f"FROM {table} " in statement or f"FROM {table}\n" in statement for statement in statements)==1

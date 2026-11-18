from decimal import Decimal
from app.apps.srm.models import SRMProduct
from tests.test_retail_return_http import retail_setup, scenario, catalog, directory_identity
from tests.test_retail_stock_receipts import receipt


def test_reorder_threshold_equality_minimum_fallback_and_restock(client, db, retail_setup):
    product = db.get(SRMProduct, retail_setup[5])
    product.reorder_level = Decimal('5')
    product.min_stock = Decimal('2')
    db.commit()
    def stock():
        response = client.get('/api/v1/srm/retail/stock', headers=retail_setup[0], params={'low_only': True})
        assert response.status_code == 200, response.text
        return response.json()['items']
    item = next(row for row in stock() if row['product_id'] == product.id)
    assert item['is_low_stock'] and Decimal(item['reorder_threshold']) == 5
    product.reorder_level = 0
    db.commit()
    assert not stock()  # Five on hand is above minimum two.
    product.min_stock = 6
    db.commit()
    assert next(row for row in stock() if row['product_id'] == product.id)['stock_status'] == 'Low stock'
    response = client.post('/api/v1/srm/retail/stock-receipts', headers=retail_setup[0], json=receipt(retail_setup))
    assert response.status_code == 201, response.text
    assert not stock()  # Receipt clears the alert automatically.

from fastapi.testclient import TestClient

from app.entrypoint import app


def test_warehouse_model_lineage_detail_does_not_fail_on_table_key():
    with TestClient(app) as client:
        imported = client.post('/api/dolphinscheduler/import', json={'overwrite': True})
        assert imported.status_code == 200, imported.text

        scanned = client.post('/api/warehouse/scan')
        assert scanned.status_code == 200, scanned.text

        models = client.get('/api/warehouse/models?limit=10')
        assert models.status_code == 200, models.text
        rows = models.json()
        assert rows

        model = rows[0]
        assert 'table' in model
        assert 'qualified_name' in model

        lineage = client.get('/api/warehouse/lineage', params={'table': model['qualified_name']})
        assert lineage.status_code == 200, lineage.text
        data = lineage.json()
        assert data['table'] == model['qualified_name']
        assert 'edges' in data

        detail = client.get(f"/api/warehouse/models/{model['id']}/detail")
        assert detail.status_code == 200, detail.text
        detail_data = detail.json()
        assert detail_data['model']['id'] == model['id']
        assert 'lineage' in detail_data

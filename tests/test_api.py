from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app


def test_health_and_storage():
    with TestClient(app) as c:
        data=c.get('/api/health').json(); assert data['status']=='ok'; assert data['version']=='0.2.0'; assert 'source_root' in data


def test_dolphinscheduler_import_to_local_source():
    with TestClient(app) as c:
        r=c.post('/api/dolphinscheduler/import',json={'overwrite':True}); assert r.status_code==200,r.text
        data=r.json(); assert data['sql_tasks']>=3; assert data['index']['artifacts']>=3
        rows=c.get('/api/source/files').json(); assert len(rows)>=3; assert Path(rows[0]['file_path']).exists()
        assert c.get('/api/source/lineage').json(); assert c.get('/api/source/task-dependencies').json()


def test_datasource_and_metadata():
    with TestClient(app) as c:
        ds=c.get('/api/datasources').json(); assert len(ds)>=3; assert c.post(f"/api/datasources/{ds[0]['id']}/test").json()['success'] is True
        rows=c.get('/api/metadata/tables?q=order').json(); assert rows


def test_task_workspace_execute_validate_release():
    with TestClient(app) as c:
        c.post('/api/dolphinscheduler/import',json={'overwrite':True})
        t=c.post('/api/tasks',json={'title':'测试城市渠道模型','requirement':'基于订单数据建设交易域城市渠道日汇总模型','owner':'tester'}).json(); tid=t['id']
        assert Path(t['workspace_path']).exists(); detail=c.get(f'/api/tasks/{tid}').json(); assert detail['files']
        assert c.post(f'/api/tasks/{tid}/sql/validate').json()['valid'] is True
        assert c.post(f'/api/tasks/{tid}/sql/execute').json()['status']=='SUCCESS'
        v=c.post(f'/api/tasks/{tid}/validations/run').json(); assert v['passed']==v['total']
        approved=c.post(f'/api/tasks/{tid}/review/approve',json={'reviewer':'tester','note':'业务抽样确认通过'}).json()
        assert approved['status']=='RELEASE_READY'; assert Path(approved['release_path']).exists()


def test_reject_returns_to_sql_development():
    with TestClient(app) as c:
        t=c.post('/api/tasks',json={'title':'驳回测试','requirement':'测试模型','owner':'tester'}).json()
        r=c.post(f"/api/tasks/{t['id']}/review/reject",json={'reviewer':'tester','note':'口径需要修改'})
        assert r.status_code==200; assert r.json()['status']=='REWORK'; assert r.json()['phase']=='SQL_DEVELOPMENT'

from contextlib import asynccontextmanager
import json
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.config import settings
from app.db import Base, engine, SessionLocal, get_db, DataSource, DolphinSchedulerConfig, SourceArtifact, CodeLineage, MetadataTable, MetadataColumn, Domain, Subject, Task, Execution, ValidationResult, SystemSetting
from app.schemas import DataSourceCreate, DataSourceOut, DolphinSchedulerConfigIn, DolphinSchedulerImportRequest, TaskCreate, TaskOut, SqlUpdate, AgentMessage, ReviewRequest, SettingsUpdate
from app.seed import seed
from app.security import SecretBox
from app.dolphinscheduler import DolphinSchedulerImporter
from app.code_index import CodeIndexService
from app.workspace import WorkspaceManager
from app.services import DataSourceService, TaskService, SqlGuard, ExecutionService, ValidationService, AgentService


@asynccontextmanager
async def lifespan(app):
    cfg=settings(); cfg.ensure_directories(); Base.metadata.create_all(bind=engine)
    with SessionLocal() as db: seed(db)
    yield

cfg=settings()
app=FastAPI(title=cfg.app_name,version='0.2.0',description='独立 AI 数仓研发平台：DolphinScheduler → local source → Agent workspace',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=cfg.cors_origins,allow_credentials=True,allow_methods=['*'],allow_headers=['*'])


def task_or_404(db,task_id):
    x=db.get(Task,task_id)
    if not x: raise HTTPException(404,'任务不存在')
    return x


def ds_or_404(db,ds_id):
    x=db.get(DataSource,ds_id)
    if not x: raise HTTPException(404,'数据源不存在')
    return x


def ds_config_or_none(db): return db.query(DolphinSchedulerConfig).filter_by(enabled=True).order_by(DolphinSchedulerConfig.id.desc()).first()


@app.get('/')
def root(): return {'app':cfg.app_name,'version':'0.2.0','docs':'/docs','workflow':'DolphinScheduler MySQL -> source/ -> workspace/ -> validation -> human review -> releases/'}

@app.get('/api/health')
def health(): return {'status':'ok','app':cfg.app_name,'version':'0.2.0','mock_external':cfg.app_mock_external,'source_root':cfg.app_source_root,'workspace_root':cfg.app_workspace_root,'release_root':cfg.app_release_root}

@app.get('/api/dashboard')
def dashboard(db:Session=Depends(get_db)):
    vals=db.query(ValidationResult).all(); passed=sum(x.status=='PASS' for x in vals); tasks=db.query(Task).order_by(Task.id.desc()).limit(5).all()
    return {'metrics':{'domains':db.query(Domain).count(),'models':db.query(MetadataTable).count(),'tasks':db.query(Task).count(),'source_sql_tasks':db.query(SourceArtifact).count(),'validation_pass_rate':round(passed/len(vals)*100,1) if vals else 100.0},'tasks':[{'id':x.id,'task_no':x.task_no,'title':x.title,'domain':x.domain,'subject':x.subject,'phase':x.phase,'status':x.status,'owner':x.owner} for x in tasks],'storage':{'source':cfg.app_source_root,'workspace':cfg.app_workspace_root,'release':cfg.app_release_root}}


# DolphinScheduler MySQL -> local source/
@app.get('/api/dolphinscheduler/config')
def get_ds_config(db:Session=Depends(get_db)):
    x=ds_config_or_none(db)
    if not x: return None
    return {'id':x.id,'name':x.name,'host':x.host,'port':x.port,'username':x.username,'database_name':x.database_name,'enabled':x.enabled,'last_sync_at':x.last_sync_at}

@app.put('/api/dolphinscheduler/config')
def put_ds_config(p:DolphinSchedulerConfigIn,db:Session=Depends(get_db)):
    x=ds_config_or_none(db)
    if not x: x=DolphinSchedulerConfig(host=p.host,port=p.port,username=p.username,database_name=p.database_name); db.add(x)
    x.name=p.name; x.host=p.host; x.port=p.port; x.username=p.username; x.database_name=p.database_name
    if p.password: x.encrypted_password=SecretBox().encrypt(p.password)
    db.commit(); db.refresh(x); return {'id':x.id,'name':x.name,'host':x.host,'port':x.port,'username':x.username,'database_name':x.database_name,'enabled':x.enabled,'last_sync_at':x.last_sync_at}

@app.post('/api/dolphinscheduler/test')
def test_dolphinscheduler(db:Session=Depends(get_db)):
    config=ds_config_or_none(db)
    if not config and not cfg.app_mock_external: raise HTTPException(400,'请先配置 DolphinScheduler MySQL')
    try: return DolphinSchedulerImporter(db).test(config) if config else {'success':True,'message':'Mock 模式：无需真实 DS 配置','version':'mock-3.x'}
    except Exception as e: return {'success':False,'message':str(e)}

@app.post('/api/dolphinscheduler/import')
def import_dolphinscheduler(p:DolphinSchedulerImportRequest,db:Session=Depends(get_db)):
    config=ds_config_or_none(db)
    if not config and not cfg.app_mock_external: raise HTTPException(400,'请先配置 DolphinScheduler MySQL')
    try:
        result=DolphinSchedulerImporter(db).import_sql_tasks(config,p.project_code,p.project_name,p.overwrite); result['index']=CodeIndexService(db).rebuild(); return result
    except Exception as e: raise HTTPException(400,str(e))

@app.get('/api/source/files')
def source_files(q:str|None=None,project_code:str|None=None,workflow_code:str|None=None,db:Session=Depends(get_db)):
    query=db.query(SourceArtifact)
    if q: query=query.filter((SourceArtifact.task_name.like(f'%{q}%')) | (SourceArtifact.sql_text.like(f'%{q}%')) | (SourceArtifact.file_path.like(f'%{q}%')))
    if project_code: query=query.filter(SourceArtifact.project_code==project_code)
    if workflow_code: query=query.filter(SourceArtifact.workflow_code==workflow_code)
    rows=query.order_by(SourceArtifact.project_name,SourceArtifact.workflow_name,SourceArtifact.task_name).limit(500).all()
    return [{'id':x.id,'project_code':x.project_code,'project_name':x.project_name,'workflow_code':x.workflow_code,'workflow_name':x.workflow_name,'task_code':x.task_code,'task_name':x.task_name,'task_type':x.task_type,'datasource_ref':x.datasource_ref,'file_path':x.file_path,'imported_at':x.imported_at} for x in rows]

@app.get('/api/source/files/{artifact_id}')
def source_file(artifact_id:int,db:Session=Depends(get_db)):
    x=db.get(SourceArtifact,artifact_id)
    if not x: raise HTTPException(404,'代码文件不存在')
    return {'id':x.id,'project':x.project_name,'workflow':x.workflow_name,'task':x.task_name,'file_path':x.file_path,'metadata_path':x.metadata_path,'sql':x.sql_text,'task_params':json.loads(x.task_params_json or '{}')}

@app.post('/api/source/index/rebuild')
def source_rebuild(db:Session=Depends(get_db)): return CodeIndexService(db).rebuild()

@app.get('/api/source/lineage')
def source_lineage(table:str|None=None,db:Session=Depends(get_db)): return CodeIndexService(db).table_lineage(table)

@app.get('/api/source/task-dependencies')
def source_task_dependencies(db:Session=Depends(get_db)):
    rows=db.query(CodeLineage).filter_by(relation_type='TASK_DEPENDENCY').limit(1000).all(); return [{'source_task_code':x.source_name,'target_task_code':x.target_name,'artifact_id':x.artifact_id} for x in rows]


# Warehouse data sources / metadata
@app.get('/api/datasources',response_model=list[DataSourceOut])
def datasources(db:Session=Depends(get_db)): return db.query(DataSource).order_by(DataSource.id).all()

@app.post('/api/datasources',response_model=DataSourceOut)
def create_ds(p:DataSourceCreate,db:Session=Depends(get_db)):
    if db.query(DataSource).filter_by(name=p.name).first(): raise HTTPException(409,'数据源名称已存在')
    x=DataSource(name=p.name,type=p.type,host=p.host,port=p.port,username=p.username,encrypted_password=SecretBox().encrypt(p.password),database_name=p.database_name,environment=p.environment,readonly=p.readonly); db.add(x); db.commit(); db.refresh(x); return x

@app.post('/api/datasources/{id}/test')
def test_ds(id:int,db:Session=Depends(get_db)):
    try: return DataSourceService(db).test(ds_or_404(db,id))
    except Exception as e: return {'success':False,'latency_ms':0,'message':str(e)}

@app.post('/api/datasources/{id}/metadata/scan')
def scan_ds(id:int,db:Session=Depends(get_db)): return DataSourceService(db).scan(ds_or_404(db,id))

@app.get('/api/datasources/{id}/tables')
def ds_tables(id:int,db:Session=Depends(get_db)): return [{'id':x.id,'database':x.database_name,'table':x.table_name,'layer':x.layer,'domain':x.domain,'subject':x.subject,'row_count':x.row_count} for x in db.query(MetadataTable).filter_by(datasource_id=id).all()]

@app.get('/api/metadata/tables')
def metadata_tables(q:str|None=Query(None),db:Session=Depends(get_db)):
    query=db.query(MetadataTable)
    if q: query=query.filter(MetadataTable.table_name.like(f'%{q}%'))
    return [{'id':x.id,'database':x.database_name,'table':x.table_name,'comment':x.table_comment,'layer':x.layer,'domain':x.domain,'subject':x.subject,'row_count':x.row_count} for x in query.limit(200).all()]

@app.get('/api/metadata/tables/{id}')
def metadata_detail(id:int,db:Session=Depends(get_db)):
    t=db.get(MetadataTable,id)
    if not t: raise HTTPException(404,'表不存在')
    cols=db.query(MetadataColumn).filter_by(table_id=t.id).order_by(MetadataColumn.ordinal).all()
    return {'id':t.id,'database':t.database_name,'table':t.table_name,'comment':t.table_comment,'layer':t.layer,'domain':t.domain,'subject':t.subject,'row_count':t.row_count,'ddl':t.ddl,'columns':[{'name':c.name,'type':c.data_type,'comment':c.comment,'nullable':c.nullable,'role':c.role} for c in cols]}

@app.get('/api/metadata/tables/{id}/lineage')
def metadata_lineage(id:int,db:Session=Depends(get_db)):
    t=db.get(MetadataTable,id)
    if not t: raise HTTPException(404,'表不存在')
    return {'table':t.table_name,'edges':CodeIndexService(db).table_lineage(t.table_name)+CodeIndexService(db).table_lineage(f'{t.database_name}.{t.table_name}')}


# Architecture
@app.get('/api/architecture/domains')
def domains(db:Session=Depends(get_db)): return [{'id':d.id,'code':d.code,'name':d.name,'table_count':d.table_count,'subjects':[s.name for s in db.query(Subject).filter_by(domain_id=d.id).all()]} for d in db.query(Domain).all()]

@app.get('/api/architecture/domains/{code}')
def domain_detail(code:str,db:Session=Depends(get_db)):
    d=db.query(Domain).filter_by(code=code).first()
    if not d: raise HTTPException(404,'主题域不存在')
    tables=db.query(MetadataTable).filter_by(domain=d.name).all(); return {'domain':d.name,'subjects':[s.name for s in db.query(Subject).filter_by(domain_id=d.id).all()],'layers':{l:[x.table_name for x in tables if x.layer==l] for l in ['ODS','DWD','DWS','ADS']}}

@app.post('/api/architecture/scan')
def arch_scan(db:Session=Depends(get_db)): return {'success':True,'source_index':CodeIndexService(db).rebuild(),'message':'已基于本地 source/ 和元数据刷新数仓上下文'}


# Agent task workspace
@app.get('/api/tasks',response_model=list[TaskOut])
def tasks(db:Session=Depends(get_db)): return db.query(Task).order_by(Task.id.desc()).all()

@app.post('/api/tasks',response_model=TaskOut)
def create_task(p:TaskCreate,db:Session=Depends(get_db)): return TaskService(db).create(p)

@app.get('/api/tasks/{id}')
def task_detail(id:int,db:Session=Depends(get_db)):
    t=task_or_404(db,id); return {'task':TaskOut.model_validate(t),'design':json.loads(t.design_json) if t.design_json else {},'sql':t.sql_code,'files':WorkspaceManager().list_task_files(t.task_no)}

@app.get('/api/tasks/{id}/workspace/files')
def task_workspace_files(id:int,db:Session=Depends(get_db)): return WorkspaceManager().list_task_files(task_or_404(db,id).task_no)

@app.get('/api/tasks/{id}/workspace/file')
def task_workspace_file(id:int,path:str,db:Session=Depends(get_db)):
    t=task_or_404(db,id)
    try: return {'path':path,'content':WorkspaceManager().read_task_file(t.task_no,path)}
    except (ValueError,FileNotFoundError) as e: raise HTTPException(404,str(e))

@app.post('/api/tasks/{id}/continue',response_model=TaskOut)
def task_continue(id:int,db:Session=Depends(get_db)): return TaskService(db).advance(task_or_404(db,id))

@app.put('/api/tasks/{id}/code')
def task_code(id:int,p:SqlUpdate,db:Session=Depends(get_db)):
    t=task_or_404(db,id); path=TaskService(db).save_sql(t,p.sql); return {'success':True,'message':'SQL 已保存到本地任务工作区','path':str(path)}

@app.post('/api/tasks/{id}/sql/validate')
def task_validate_sql(id:int,db:Session=Depends(get_db)): return SqlGuard.inspect(task_or_404(db,id).sql_code or '',allow_write=True)

@app.post('/api/tasks/{id}/sql/explain')
def task_explain(id:int,db:Session=Depends(get_db)):
    t=task_or_404(db,id); check=SqlGuard.inspect(t.sql_code or '',allow_write=True); return {'valid':check['valid'],'plan':'MOCK PLAN: PartitionPrune(dt) -> HashJoin -> Aggregate -> Insert','tables':check['tables'],'message':'真实模式会提交到 Agent Dev StarRocks 执行 EXPLAIN'}

@app.post('/api/tasks/{id}/sql/execute')
def task_execute(id:int,db:Session=Depends(get_db)):
    t=task_or_404(db,id); ds=db.query(DataSource).filter_by(environment='DEV',enabled=True).first()
    try: ex=ExecutionService(db).execute(t,ds)
    except ValueError as e: raise HTTPException(400,str(e))
    return {'id':ex.id,'query_id':ex.query_id,'status':ex.status,'duration_ms':ex.duration_ms,'scanned_bytes':ex.scanned_bytes,'affected_rows':ex.affected_rows,'log':ex.log_text}

@app.post('/api/tasks/{id}/validations/run')
def task_validations_run(id:int,db:Session=Depends(get_db)):
    task_or_404(db,id); rows=ValidationService(db).run(id); return {'total':len(rows),'passed':sum(x.status=='PASS' for x in rows),'items':[{'rule':x.rule_name,'expected':x.expected_value,'actual':x.actual_value,'difference_rate':x.difference_rate,'status':x.status} for x in rows]}

@app.get('/api/tasks/{id}/validations')
def task_validations(id:int,db:Session=Depends(get_db)):
    task_or_404(db,id); return [{'rule':x.rule_name,'expected':x.expected_value,'actual':x.actual_value,'difference_rate':x.difference_rate,'status':x.status} for x in db.query(ValidationResult).filter_by(task_id=id).all()]

@app.post('/api/tasks/{id}/review/approve',response_model=TaskOut)
def approve(id:int,p:ReviewRequest,db:Session=Depends(get_db)): return TaskService(db).review(task_or_404(db,id),'APPROVE',p.note,p.reviewer)

@app.post('/api/tasks/{id}/review/reject',response_model=TaskOut)
def reject(id:int,p:ReviewRequest,db:Session=Depends(get_db)):
    if not p.note: raise HTTPException(400,'驳回必须填写原因')
    return TaskService(db).review(task_or_404(db,id),'REJECT',p.note,p.reviewer)

@app.post('/api/tasks/{id}/agent/message')
def agent_message(id:int,p:AgentMessage,db:Session=Depends(get_db)):
    t=task_or_404(db,id); return AgentService(db).chat(p.message,t.sql_code)


@app.get('/api/releases')
def releases(): return WorkspaceManager().list_releases()

@app.get('/api/runtime')
def runtime(db:Session=Depends(get_db)):
    rows=db.query(Execution).order_by(Execution.id.desc()).limit(100).all(); return [{'id':x.id,'task_id':x.task_id,'query_id':x.query_id,'status':x.status,'started_at':x.started_at,'duration_ms':x.duration_ms,'affected_rows':x.affected_rows,'log':x.log_text} for x in rows]

@app.get('/api/settings')
def get_settings(db:Session=Depends(get_db)): return {x.key:x.value for x in db.query(SystemSetting).all()}

@app.put('/api/settings')
def update_settings(p:SettingsUpdate,db:Session=Depends(get_db)):
    for k,v in p.values.items():
        row=db.query(SystemSetting).filter_by(key=k).first()
        if row: row.value=v
        else: db.add(SystemSetting(key=k,value=v))
    db.commit(); return {'success':True,'values':p.values}

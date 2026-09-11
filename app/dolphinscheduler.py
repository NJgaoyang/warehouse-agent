from __future__ import annotations
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from app.config import settings
from app.db import CodeLineage, DolphinSchedulerConfig, SourceArtifact
from app.security import SecretBox


def _slug(value: str | int | None, fallback: str = "unknown") -> str:
    value = str(value or fallback).strip()
    value = re.sub(r"[\\/:*?\"<>|\s]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("._")
    return value[:120] or fallback


class DolphinSchedulerImporter:
    """Read SQL tasks from DolphinScheduler MySQL and export them to local source/.

    The importer introspects the actual schema because DolphinScheduler columns vary by version.
    It never modifies DolphinScheduler tables.
    """

    def __init__(self, db: Session):
        self.db = db
        self.box = SecretBox()
        self.cfg = settings()
        self.source_root = Path(self.cfg.app_source_root).resolve() / "dolphinscheduler"
        self.source_root.mkdir(parents=True, exist_ok=True)

    def _url(self, config: DolphinSchedulerConfig):
        return URL.create("mysql+pymysql", username=config.username, password=self.box.decrypt(config.encrypted_password) or "", host=config.host, port=config.port, database=config.database_name, query={"charset": "utf8mb4"})

    def test(self, config: DolphinSchedulerConfig) -> dict:
        if self.cfg.app_mock_external:
            return {"success": True, "message": "Mock 模式：DolphinScheduler MySQL 连接成功", "version": "mock-3.x"}
        engine = create_engine(self._url(config), pool_pre_ping=True, connect_args={"connect_timeout": self.cfg.app_ds_query_timeout_seconds})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            version = conn.execute(text("SELECT VERSION()")).scalar()
            required = {"t_ds_project", "t_ds_process_definition", "t_ds_task_definition", "t_ds_process_task_relation"}
            existing = set(inspect(conn).get_table_names())
            missing = sorted(required - existing)
            if missing:
                return {"success": False, "message": f"连接成功，但缺少 DolphinScheduler 表: {', '.join(missing)}", "version": version}
        return {"success": True, "message": "DolphinScheduler MySQL 连接成功", "version": version}

    def _mock_payload(self):
        tasks = [
            {"project_code":"1001","project_name":"数仓研发","workflow_code":"2001","workflow_name":"交易域订单ETL","task_code":"3001","task_name":"ODS订单同步","task_type":"SQL","datasource_ref":"1","task_params":{"sql":"INSERT OVERWRITE ods.ods_order SELECT * FROM business.orders WHERE dt='${bizdate}';","datasource":1},"sql":"INSERT OVERWRITE ods.ods_order SELECT * FROM business.orders WHERE dt='${bizdate}';"},
            {"project_code":"1001","project_name":"数仓研发","workflow_code":"2001","workflow_name":"交易域订单ETL","task_code":"3002","task_name":"DWD订单明细","task_type":"SQL","datasource_ref":"2","task_params":{"sql":"INSERT OVERWRITE dwd.dwd_trade_order_detail SELECT order_id,user_id,city_code,channel_code,pay_amount,dt FROM ods.ods_order WHERE dt='${bizdate}';","datasource":2},"sql":"INSERT OVERWRITE dwd.dwd_trade_order_detail SELECT order_id,user_id,city_code,channel_code,pay_amount,dt FROM ods.ods_order WHERE dt='${bizdate}';"},
            {"project_code":"1001","project_name":"数仓研发","workflow_code":"2001","workflow_name":"交易域订单ETL","task_code":"3003","task_name":"DWS城市日汇总","task_type":"SQL","datasource_ref":"2","task_params":{"sql":"INSERT OVERWRITE dws.dws_trade_city_day SELECT dt,city_code,COUNT(DISTINCT order_id) order_count,SUM(pay_amount) pay_amount FROM dwd.dwd_trade_order_detail WHERE dt='${bizdate}' GROUP BY dt,city_code;","datasource":2},"sql":"INSERT OVERWRITE dws.dws_trade_city_day SELECT dt,city_code,COUNT(DISTINCT order_id) order_count,SUM(pay_amount) pay_amount FROM dwd.dwd_trade_order_detail WHERE dt='${bizdate}' GROUP BY dt,city_code;"},
        ]
        relations = [
            {"workflow_code":"2001","pre_task_code":"3001","post_task_code":"3002"},
            {"workflow_code":"2001","pre_task_code":"3002","post_task_code":"3003"},
        ]
        return tasks, relations

    @staticmethod
    def _rows_latest(rows, code_key="code"):
        result = {}
        for row in rows:
            code = str(row.get(code_key) or row.get("id"))
            current = result.get(code)
            rank = (int(row.get("version") or 0), int(row.get("id") or 0))
            current_rank = (int(current.get("version") or 0), int(current.get("id") or 0)) if current else (-1, -1)
            if current is None or rank >= current_rank: result[code] = row
        return result

    @staticmethod
    def _pick(row, *keys, default=None):
        for key in keys:
            if key in row and row[key] is not None: return row[key]
        return default

    def _load_live(self, config, project_code, project_name):
        engine = create_engine(self._url(config), pool_pre_ping=True, connect_args={"connect_timeout": self.cfg.app_ds_query_timeout_seconds})
        with engine.connect() as conn:
            tables = set(inspect(conn).get_table_names())
            required = {"t_ds_project", "t_ds_process_definition", "t_ds_task_definition", "t_ds_process_task_relation"}
            missing = sorted(required - tables)
            if missing: raise RuntimeError(f"DolphinScheduler 元数据库缺少表: {', '.join(missing)}")
            projects = [dict(x) for x in conn.execute(text("SELECT * FROM t_ds_project")).mappings().all()]
            workflows = [dict(x) for x in conn.execute(text("SELECT * FROM t_ds_process_definition")).mappings().all()]
            task_defs = [dict(x) for x in conn.execute(text("SELECT * FROM t_ds_task_definition")).mappings().all()]
            relations = [dict(x) for x in conn.execute(text("SELECT * FROM t_ds_process_task_relation")).mappings().all()]

        project_by_code = {str(self._pick(p, "code", "id")): p for p in projects}
        workflow_by_code = self._rows_latest(workflows)
        task_by_code = self._rows_latest(task_defs)
        allowed_projects = None
        if project_code: allowed_projects = {str(project_code)}
        elif project_name:
            allowed_projects = {code for code,p in project_by_code.items() if str(self._pick(p,"name",default="")).lower() == project_name.lower()}

        workflow_tasks = defaultdict(set)
        normalized_relations = []
        for rel in relations:
            wf_code = str(self._pick(rel,"process_definition_code","process_definition_id",default="0"))
            project_c = str(self._pick(rel,"project_code","project_id",default="0"))
            if allowed_projects is not None and project_c not in allowed_projects: continue
            pre = str(self._pick(rel,"pre_task_code","pre_task_node_id",default="0"))
            post = str(self._pick(rel,"post_task_code","post_task_node_id",default="0"))
            if pre not in {"0","None",""}: workflow_tasks[wf_code].add(pre)
            if post not in {"0","None",""}: workflow_tasks[wf_code].add(post)
            if post not in {"0","None",""}: normalized_relations.append({"workflow_code":wf_code,"pre_task_code":pre,"post_task_code":post})

        tasks = []
        for wf_code, task_codes in workflow_tasks.items():
            wf = workflow_by_code.get(wf_code,{})
            project_c = str(self._pick(wf,"project_code","project_id",default="0"))
            if allowed_projects is not None and project_c not in allowed_projects: continue
            project = project_by_code.get(project_c,{})
            for task_code in task_codes:
                td = task_by_code.get(task_code)
                if not td: continue
                task_type = str(self._pick(td,"task_type","task_type_name",default="")).upper()
                if task_type not in self.cfg.ds_sql_task_types: continue
                raw_params = self._pick(td,"task_params","task_params_json",default="{}")
                try: params = json.loads(raw_params) if isinstance(raw_params,str) else (raw_params or {})
                except json.JSONDecodeError: params = {"_raw":str(raw_params)}
                sql = params.get("sql") or params.get("sqlStatement") or params.get("script") or ""
                if not sql: continue
                datasource_ref = params.get("datasource") or params.get("datasourceId") or params.get("datasource_id")
                tasks.append({"project_code":project_c,"project_name":str(self._pick(project,"name",default=f"project_{project_c}")),"workflow_code":wf_code,"workflow_name":str(self._pick(wf,"name",default=f"workflow_{wf_code}")),"task_code":task_code,"task_name":str(self._pick(td,"name",default=f"task_{task_code}")),"task_type":task_type,"datasource_ref":str(datasource_ref) if datasource_ref is not None else None,"task_params":params,"sql":sql})
        return tasks, normalized_relations

    def import_sql_tasks(self, config, project_code=None, project_name=None, overwrite=True):
        if self.cfg.app_mock_external: tasks, relations = self._mock_payload()
        else:
            if config is None: raise RuntimeError("请先配置 DolphinScheduler MySQL")
            tasks, relations = self._load_live(config, project_code, project_name)
        if project_code: tasks = [x for x in tasks if str(x["project_code"]) == str(project_code)]
        if project_name: tasks = [x for x in tasks if x["project_name"] == project_name]

        relation_by_wf = defaultdict(list)
        for rel in relations: relation_by_wf[str(rel["workflow_code"])].append(rel)
        imported = skipped = 0
        projects, workflows = set(), set()
        touched = {}
        for item in tasks:
            projects.add(str(item["project_code"])); workflows.add(str(item["workflow_code"]))
            root = self.source_root / f"{_slug(item['project_name'])}__{_slug(item['project_code'])}" / f"{_slug(item['workflow_name'])}__{_slug(item['workflow_code'])}" / f"{_slug(item['task_name'])}__{_slug(item['task_code'])}"
            root.mkdir(parents=True, exist_ok=True)
            sql_path, meta_path = root / "task.sql", root / "task.json"
            external_key = f"{item['workflow_code']}:{item['task_code']}"
            if sql_path.exists() and not overwrite: skipped += 1
            else:
                sql_path.write_text(item["sql"].rstrip()+"\n", encoding="utf-8")
                upstream = [str(r["pre_task_code"]) for r in relation_by_wf[str(item["workflow_code"])] if str(r["post_task_code"]) == str(item["task_code"]) and str(r["pre_task_code"]) not in {"0",""}]
                downstream = [str(r["post_task_code"]) for r in relation_by_wf[str(item["workflow_code"])] if str(r["pre_task_code"]) == str(item["task_code"]) and str(r["post_task_code"]) not in {"0",""}]
                meta = {"source":"DolphinScheduler MySQL","project":{"code":item["project_code"],"name":item["project_name"]},"workflow":{"code":item["workflow_code"],"name":item["workflow_name"]},"task":{"code":item["task_code"],"name":item["task_name"],"type":item["task_type"]},"datasource_ref":item["datasource_ref"],"upstream_task_codes":upstream,"downstream_task_codes":downstream,"task_params":item["task_params"],"imported_at":datetime.utcnow().isoformat()}
                meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8"); imported += 1

            artifact = self.db.query(SourceArtifact).filter_by(source_type="DOLPHINSCHEDULER", external_key=external_key).first()
            if not artifact:
                artifact = SourceArtifact(source_type="DOLPHINSCHEDULER",external_key=external_key,task_name=item["task_name"],file_path=str(sql_path)); self.db.add(artifact); self.db.flush()
            artifact.project_code=str(item["project_code"]); artifact.project_name=item["project_name"]
            artifact.workflow_code=str(item["workflow_code"]); artifact.workflow_name=item["workflow_name"]
            artifact.task_code=str(item["task_code"]); artifact.task_name=item["task_name"]; artifact.task_type=item["task_type"]
            artifact.datasource_ref=item["datasource_ref"]; artifact.file_path=str(sql_path); artifact.metadata_path=str(meta_path)
            artifact.sql_text=item["sql"]; artifact.task_params_json=json.dumps(item["task_params"],ensure_ascii=False); artifact.imported_at=datetime.utcnow()
            touched[(str(item["workflow_code"]),str(item["task_code"]))]=artifact

        self.db.flush()
        wf_codes={str(x["workflow_code"]) for x in tasks}; ids=[a.id for a in touched.values()]
        if ids: self.db.query(CodeLineage).filter(CodeLineage.artifact_id.in_(ids),CodeLineage.relation_type=="TASK_DEPENDENCY").delete(synchronize_session=False)
        for rel in relations:
            wf,post,pre=str(rel["workflow_code"]),str(rel["post_task_code"]),str(rel["pre_task_code"])
            if wf not in wf_codes: continue
            artifact=touched.get((wf,post))
            if artifact and pre not in {"0","","None"}: self.db.add(CodeLineage(artifact_id=artifact.id,relation_type="TASK_DEPENDENCY",source_name=pre,target_name=post))
        if config is not None: config.last_sync_at=datetime.utcnow()
        self.db.commit()
        return {"projects":len(projects),"workflows":len(workflows),"sql_tasks":len(tasks),"imported":imported,"skipped":skipped,"source_root":str(self.source_root)}

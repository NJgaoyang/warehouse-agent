from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from app.code_index import extract_sql_lineage, normalize_table
from app.db import CodeLineage, Domain, MetadataTable, SourceArtifact, Subject
from app.warehouse_models import WarehouseModel


LAYER_RULES = [
    ("ODS", ("ods", "stg", "stage", "raw")),
    ("DWD", ("dwd", "detail", "fact")),
    ("DWS", ("dws", "summary", "aggregate", "agg")),
    ("ADS", ("ads", "app", "mart", "report")),
    ("DIM", ("dim", "dimension")),
]

DOMAIN_RULES = [
    ("trade", "交易域", ("trade", "order", "payment", "pay", "refund", "transaction", "settlement", "aftersale", "after_sale", "sale", "订单", "支付", "退款", "交易", "结算", "售后")),
    ("user", "用户域", ("user", "member", "customer", "account", "profile", "用户", "会员", "客户", "账号")),
    ("product", "商品域", ("product", "goods", "item", "sku", "spu", "category", "brand", "商品", "货品", "类目", "品牌")),
    ("marketing", "营销域", ("marketing", "campaign", "promotion", "coupon", "activity", "advert", "广告", "营销", "活动", "优惠券", "投放")),
    ("supply", "供应链域", ("inventory", "stock", "warehouse", "purchase", "supplier", "procurement", "supply", "库存", "仓储", "采购", "供应商", "供应链")),
    ("finance", "财务域", ("finance", "invoice", "billing", "cost", "profit", "revenue", "accounting", "财务", "发票", "成本", "利润", "收入")),
    ("common", "公共域", ("calendar", "region", "province", "city", "area", "dictionary", "dict", "common", "公共", "日期", "地区", "省份", "城市", "字典")),
]

SUBJECT_RULES = {
    "trade": [
        ("order", "订单主题", ("order", "订单")),
        ("payment", "支付主题", ("payment", "pay", "支付")),
        ("refund", "退款主题", ("refund", "退款")),
        ("aftersale", "售后主题", ("aftersale", "after_sale", "return", "售后", "退货")),
        ("settlement", "结算主题", ("settlement", "settle", "结算")),
    ],
    "user": [
        ("member", "会员主题", ("member", "会员")),
        ("user", "用户主题", ("user", "customer", "用户", "客户")),
        ("account", "账号主题", ("account", "账号")),
    ],
    "product": [
        ("product", "商品主题", ("product", "goods", "item", "sku", "spu", "商品", "货品")),
        ("category", "类目主题", ("category", "类目")),
        ("brand", "品牌主题", ("brand", "品牌")),
    ],
    "marketing": [
        ("activity", "活动主题", ("campaign", "activity", "promotion", "活动", "营销活动")),
        ("coupon", "优惠券主题", ("coupon", "优惠券")),
        ("advert", "广告投放主题", ("advert", "广告", "投放")),
    ],
    "supply": [
        ("inventory", "库存主题", ("inventory", "stock", "库存")),
        ("purchase", "采购主题", ("purchase", "procurement", "采购")),
        ("supplier", "供应商主题", ("supplier", "供应商")),
        ("warehouse", "仓储主题", ("warehouse", "仓储")),
    ],
    "finance": [
        ("revenue", "收入主题", ("revenue", "income", "收入")),
        ("cost", "成本主题", ("cost", "成本")),
        ("invoice", "发票主题", ("invoice", "发票")),
        ("profit", "利润主题", ("profit", "利润")),
    ],
    "common": [
        ("date", "日期主题", ("calendar", "date", "日期")),
        ("region", "地区主题", ("region", "province", "city", "area", "地区", "省份", "城市")),
        ("dictionary", "字典主题", ("dictionary", "dict", "字典")),
    ],
}


def _clean(value: str | None) -> str:
    return (value or "").replace("`", "").replace('"', "").strip()


def _split_name(name: str) -> tuple[str | None, str]:
    parts = [x for x in _clean(name).split(".") if x]
    if not parts:
        return None, "unknown"
    if len(parts) == 1:
        return None, parts[0]
    return parts[-2], parts[-1]


def _tokens(value: str) -> set[str]:
    low = value.lower()
    raw = re.split(r"[^a-z0-9_\u4e00-\u9fff]+|_+", low)
    return {x for x in raw if x}


def _contains(text: str, keyword: str) -> bool:
    low = text.lower()
    k = keyword.lower()
    if re.fullmatch(r"[a-z0-9_]+", k):
        tokens = _tokens(low)
        return k in tokens or any(token.startswith(k) or token.endswith(k) for token in tokens)
    return k in low


def infer_layer(qualified_name: str) -> tuple[str, float, list[str]]:
    database, table = _split_name(qualified_name)
    candidates = [table.lower()]
    if database:
        candidates.append(database.lower())
    for layer, aliases in LAYER_RULES:
        for alias in aliases:
            for candidate in candidates:
                if candidate == alias or candidate.startswith(alias + "_") or candidate.startswith(alias + "-"):
                    return layer, 0.99, [f"{candidate} 命中 {alias} 分层前缀"]
                if candidate.endswith("_" + alias):
                    return layer, 0.90, [f"{candidate} 命中 {alias} 分层后缀"]
    return "UNKNOWN", 0.20, ["未命中 ODS/DWD/DWS/ADS/DIM 命名规则"]


def infer_domain(context: str) -> tuple[str, str, float, list[str]]:
    scores: list[tuple[int, str, str, list[str]]] = []
    for code, name, keywords in DOMAIN_RULES:
        hits = [k for k in keywords if _contains(context, k)]
        if hits:
            scores.append((len(hits), code, name, hits))
    if not scores:
        return "unknown", "待识别", 0.20, ["项目/工作流/任务/表名未命中已配置主题域关键词"]
    scores.sort(key=lambda x: (x[0], x[1] != "common"), reverse=True)
    count, code, name, hits = scores[0]
    confidence = min(0.98, 0.72 + 0.06 * count)
    return code, name, confidence, [f"命中关键词: {', '.join(hits[:8])}"]


def infer_subject(domain_code: str, context: str) -> tuple[str, str, float, list[str]]:
    rules = SUBJECT_RULES.get(domain_code, [])
    scores: list[tuple[int, str, str, list[str]]] = []
    for code, name, keywords in rules:
        hits = [k for k in keywords if _contains(context, k)]
        if hits:
            scores.append((len(hits), code, name, hits))
    if not scores:
        if domain_code == "unknown":
            return "unknown", "待识别主题", 0.20, ["主题域尚未识别"]
        return "general", "综合主题", 0.45, ["未命中细分主题关键词，暂归综合主题"]
    scores.sort(key=lambda x: x[0], reverse=True)
    count, code, name, hits = scores[0]
    confidence = min(0.98, 0.78 + 0.06 * count)
    return code, name, confidence, [f"命中关键词: {', '.join(hits[:8])}"]


class WarehouseAnalysisService:
    def __init__(self, db: Session):
        self.db = db

    def scan(self) -> dict:
        artifacts = self.db.query(SourceArtifact).all()
        state: dict[str, dict] = defaultdict(lambda: {
            "produced_by": set(), "consumed_by": set(), "contexts": [],
            "upstream": set(), "downstream": set(), "task_codes": set(),
            "task_names": set(),
        })

        edges: set[tuple[str, str]] = set()
        parse_failures = 0
        for artifact in artifacts:
            sql = artifact.sql_text or ""
            try:
                info = extract_sql_lineage(sql)
            except Exception:
                parse_failures += 1
                continue
            reads = {_clean(x) for x in info.get("reads", []) if _clean(x)}
            writes = {_clean(x) for x in info.get("writes", []) if _clean(x)}
            context = " ".join(filter(None, [artifact.project_name, artifact.workflow_name, artifact.task_name, *reads, *writes]))
            task_key = str(artifact.task_code or artifact.id)
            task_label = artifact.task_name or task_key

            for table in writes:
                x = state[table]
                x["produced_by"].add(task_key)
                x["task_codes"].add(task_key)
                x["task_names"].add(task_label)
                x["contexts"].append(context)
            for table in reads:
                x = state[table]
                x["consumed_by"].add(task_key)
                x["task_codes"].add(task_key)
                x["task_names"].add(task_label)
                x["contexts"].append(context)
            for source in reads:
                for target in writes:
                    if source == target:
                        continue
                    edges.add((source, target))
                    state[source]["downstream"].add(target)
                    state[target]["upstream"].add(source)

        self.db.query(WarehouseModel).delete(synchronize_session=False)
        models: list[WarehouseModel] = []
        for qualified_name, item in sorted(state.items()):
            database, table = _split_name(qualified_name)
            context = " ".join([qualified_name, *item["contexts"]])
            layer, layer_conf, layer_evidence = infer_layer(qualified_name)
            domain_code, domain_name, domain_conf, domain_evidence = infer_domain(context)
            subject_code, subject_name, subject_conf, subject_evidence = infer_subject(domain_code, context)
            confidence = round(layer_conf * 0.35 + domain_conf * 0.35 + subject_conf * 0.30, 4)
            evidence = {
                "layer": layer_evidence,
                "domain": domain_evidence,
                "subject": subject_evidence,
                "task_names": sorted(item["task_names"])[:20],
                "upstream": sorted(item["upstream"])[:50],
                "downstream": sorted(item["downstream"])[:50],
            }
            model = WarehouseModel(
                qualified_name=qualified_name,
                database_name=database,
                table_name=table,
                layer=layer,
                domain_code=domain_code,
                domain_name=domain_name,
                subject_code=subject_code,
                subject_name=subject_name,
                confidence=confidence,
                produced_by_count=len(item["produced_by"]),
                consumed_by_count=len(item["consumed_by"]),
                upstream_count=len(item["upstream"]),
                downstream_count=len(item["downstream"]),
                evidence_json=json.dumps(evidence, ensure_ascii=False),
                task_codes_json=json.dumps(sorted(item["task_codes"]), ensure_ascii=False),
                updated_at=datetime.utcnow(),
            )
            self.db.add(model)
            models.append(model)
        self.db.flush()

        # Replace demo domain/subject rows with the architecture inferred from real code.
        self.db.query(Subject).delete(synchronize_session=False)
        self.db.query(Domain).delete(synchronize_session=False)
        grouped: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
        for model in models:
            grouped[(model.domain_code, model.domain_name)].add((model.subject_code, model.subject_name))
        for (domain_code, domain_name), subjects in sorted(grouped.items(), key=lambda x: x[0][1]):
            table_count = sum(1 for x in models if x.domain_code == domain_code)
            domain = Domain(code=domain_code, name=domain_name, table_count=table_count)
            self.db.add(domain)
            self.db.flush()
            for subject_code, subject_name in sorted(subjects, key=lambda x: x[1]):
                self.db.add(Subject(domain_id=domain.id, code=f"{domain_code}_{subject_code}"[:60], name=subject_name))

        # Enrich physical metadata when a matching table has been scanned from a datasource.
        by_qualified = {x.qualified_name.lower(): x for x in models}
        by_table: dict[str, list[WarehouseModel]] = defaultdict(list)
        for x in models:
            by_table[x.table_name.lower()].append(x)
        for mt in self.db.query(MetadataTable).all():
            key = f"{mt.database_name}.{mt.table_name}".lower()
            inferred = by_qualified.get(key)
            if inferred is None and len(by_table.get(mt.table_name.lower(), [])) == 1:
                inferred = by_table[mt.table_name.lower()][0]
            if inferred:
                mt.layer = inferred.layer if inferred.layer != "UNKNOWN" else mt.layer
                mt.domain = inferred.domain_name if inferred.domain_code != "unknown" else mt.domain
                mt.subject = inferred.subject_name if inferred.subject_code != "unknown" else mt.subject

        self.db.commit()
        overview = self.overview()
        overview["scan"] = {
            "source_artifacts": len(artifacts),
            "tables_discovered": len(models),
            "lineage_edges": len(edges),
            "parse_failures": parse_failures,
        }
        return overview

    def overview(self) -> dict:
        rows = self.db.query(WarehouseModel).order_by(WarehouseModel.layer, WarehouseModel.qualified_name).all()
        layers = {name: 0 for name in ["ODS", "DWD", "DWS", "ADS", "DIM", "UNKNOWN"]}
        domains: dict[str, dict] = {}
        for row in rows:
            layers[row.layer] = layers.get(row.layer, 0) + 1
            d = domains.setdefault(row.domain_code, {
                "code": row.domain_code,
                "name": row.domain_name,
                "table_count": 0,
                "subjects": {},
                "layers": defaultdict(int),
                "avg_confidence": 0.0,
                "_confidence_total": 0.0,
            })
            d["table_count"] += 1
            d["subjects"][row.subject_code] = row.subject_name
            d["layers"][row.layer] += 1
            d["_confidence_total"] += row.confidence
        domain_list = []
        for d in domains.values():
            count = d["table_count"] or 1
            d["avg_confidence"] = round(d.pop("_confidence_total") / count, 4)
            d["subjects"] = [{"code": code, "name": name} for code, name in sorted(d["subjects"].items(), key=lambda x: x[1])]
            d["layers"] = dict(d["layers"])
            domain_list.append(d)
        domain_list.sort(key=lambda x: (-x["table_count"], x["name"]))
        return {
            "total_tables": len(rows),
            "recognized_layers": sum(v for k, v in layers.items() if k != "UNKNOWN"),
            "unknown_tables": layers.get("UNKNOWN", 0),
            "layers": layers,
            "domains": domain_list,
        }

    def domains(self) -> list[dict]:
        return self.overview()["domains"]

    def models(self, layer: str | None = None, domain: str | None = None, subject: str | None = None, q: str | None = None, limit: int = 500) -> list[dict]:
        query = self.db.query(WarehouseModel)
        if layer:
            query = query.filter(WarehouseModel.layer == layer.upper())
        if domain:
            query = query.filter((WarehouseModel.domain_code == domain) | (WarehouseModel.domain_name == domain))
        if subject:
            query = query.filter((WarehouseModel.subject_code == subject) | (WarehouseModel.subject_name == subject))
        if q:
            like = f"%{q}%"
            query = query.filter((WarehouseModel.qualified_name.like(like)) | (WarehouseModel.table_name.like(like)))
        rows = query.order_by(WarehouseModel.layer, WarehouseModel.domain_name, WarehouseModel.subject_name, WarehouseModel.qualified_name).limit(limit).all()
        return [self._model_dict(x, include_evidence=False) for x in rows]

    def model(self, model_id: int) -> dict | None:
        x = self.db.get(WarehouseModel, model_id)
        return self._model_dict(x, include_evidence=True) if x else None

    def model_by_name(self, table: str) -> dict | None:
        clean = _clean(table)
        x = self.db.query(WarehouseModel).filter(WarehouseModel.qualified_name == clean).first()
        if x is None:
            _, simple = _split_name(clean)
            rows = self.db.query(WarehouseModel).filter(WarehouseModel.table_name == simple).all()
            x = rows[0] if len(rows) == 1 else None
        return self._model_dict(x, include_evidence=True) if x else None

    def lineage(self, table: str) -> dict:
        clean = _clean(table)
        model = self.model_by_name(clean)
        candidates = {clean}
        _, simple = _split_name(clean)
        candidates.add(simple)
        if model:
            candidates.add(model["qualified_name"])
            candidates.add(model["table_name"])
        edges = self.db.query(CodeLineage).filter(CodeLineage.relation_type == "TABLE_LINEAGE").all()
        related = []
        for edge in edges:
            if edge.source_name in candidates or edge.target_name in candidates:
                related.append({"source": edge.source_name, "target": edge.target_name, "artifact_id": edge.artifact_id})
        return {"table": clean, "model": model, "edges": related[:500]}

    @staticmethod
    def _model_dict(x: WarehouseModel, include_evidence: bool) -> dict:
        data = {
            "id": x.id,
            "qualified_name": x.qualified_name,
            "database": x.database_name,
            "table": x.table_name,
            "layer": x.layer,
            "domain_code": x.domain_code,
            "domain": x.domain_name,
            "subject_code": x.subject_code,
            "subject": x.subject_name,
            "confidence": x.confidence,
            "produced_by_count": x.produced_by_count,
            "consumed_by_count": x.consumed_by_count,
            "upstream_count": x.upstream_count,
            "downstream_count": x.downstream_count,
            "updated_at": x.updated_at,
        }
        if include_evidence:
            try:
                data["evidence"] = json.loads(x.evidence_json or "{}")
            except json.JSONDecodeError:
                data["evidence"] = {}
            try:
                data["task_codes"] = json.loads(x.task_codes_json or "[]")
            except json.JSONDecodeError:
                data["task_codes"] = []
        return data

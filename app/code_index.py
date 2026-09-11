from __future__ import annotations
import re
from sqlalchemy.orm import Session
try:
    import sqlglot
    from sqlglot import exp
except ImportError:
    sqlglot = None
    exp = None
from app.db import CodeLineage, SourceArtifact


def normalize_table(name: str) -> str:
    return name.replace("`", "").strip()


def extract_sql_lineage(sql: str) -> dict:
    raw = sql or ""
    reads, writes = set(), set()
    if sqlglot is not None:
        try:
            for tree in sqlglot.parse(raw, read="mysql"):
                all_tables = [normalize_table(t.sql(dialect="mysql")) for t in tree.find_all(exp.Table)]
                target_names = set()
                if isinstance(tree, exp.Insert) and tree.this is not None: target_names.add(normalize_table(tree.this.sql(dialect="mysql")))
                if isinstance(tree, exp.Create) and tree.this is not None: target_names.add(normalize_table(tree.this.sql(dialect="mysql")))
                writes.update(target_names)
                reads.update(t for t in all_tables if t not in target_names)
        except Exception:
            pass
    if not reads and not writes:
        writes.update(normalize_table(x) for x in re.findall(r"(?is)\b(?:INSERT\s+(?:OVERWRITE\s+)?(?:INTO\s+)?|CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)([`\w.]+)", raw))
        reads.update(normalize_table(x) for x in re.findall(r"(?is)\b(?:FROM|JOIN)\s+([`\w.]+)", raw))
    return {"reads": sorted(reads), "writes": sorted(writes)}


class CodeIndexService:
    def __init__(self, db: Session): self.db = db

    def rebuild(self) -> dict:
        artifacts = self.db.query(SourceArtifact).all()
        self.db.query(CodeLineage).filter(CodeLineage.relation_type == "TABLE_LINEAGE").delete(synchronize_session=False)
        edges = 0
        for artifact in artifacts:
            info = extract_sql_lineage(artifact.sql_text or "")
            targets = info["writes"] or [None]
            for source in info["reads"]:
                for target in targets:
                    self.db.add(CodeLineage(artifact_id=artifact.id, relation_type="TABLE_LINEAGE", source_name=source, target_name=target)); edges += 1
        self.db.commit()
        return {"artifacts": len(artifacts), "table_lineage_edges": edges}

    def search(self, query: str, limit: int = 50) -> list[SourceArtifact]:
        q = f"%{query}%"
        return self.db.query(SourceArtifact).filter((SourceArtifact.task_name.like(q)) | (SourceArtifact.sql_text.like(q)) | (SourceArtifact.file_path.like(q))).order_by(SourceArtifact.id.desc()).limit(limit).all()

    def table_lineage(self, table: str | None = None) -> list[dict]:
        query = self.db.query(CodeLineage).filter(CodeLineage.relation_type == "TABLE_LINEAGE")
        if table: query = query.filter((CodeLineage.source_name == table) | (CodeLineage.target_name == table))
        return [{"source":x.source_name,"target":x.target_name,"artifact_id":x.artifact_id} for x in query.limit(500).all()]

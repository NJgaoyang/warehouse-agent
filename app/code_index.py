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
    """Normalize a SQL table reference to a physical table name only.

    Historical index rows may contain forms such as::

        ods.orders AS o
        ads.report_table (id, dt, amount)

    These are not different physical models.  Keep only catalog/db/table and
    remove aliases / INSERT column lists before persisting lineage.
    """
    value = (name or "").replace("`", "").replace('"', "").strip()
    # INSERT INTO db.table(col1, col2, ...)
    value = re.sub(r"\s*\(.*$", "", value, flags=re.S).strip()
    # FROM db.table AS t
    value = re.sub(r"\s+AS\s+[A-Za-z_][\w$]*$", "", value, flags=re.I).strip()
    # FROM db.table t -- conservative support for a bare alias
    parts = value.split()
    if len(parts) == 2 and re.fullmatch(r"[A-Za-z_][\w$]*", parts[1]):
        value = parts[0]
    return value.strip(" .")


def _physical_table_name(table) -> str:
    """Return catalog.db.table from a sqlglot Table without alias text."""
    if exp is None or table is None:
        return ""
    if isinstance(table, exp.Schema):
        return _physical_table_name(table.this)
    if not isinstance(table, exp.Table):
        nested = table.find(exp.Table) if hasattr(table, "find") else None
        return _physical_table_name(nested)

    parts = []
    # sqlglot properties return unquoted identifiers and intentionally omit aliases.
    for value in (getattr(table, "catalog", None), getattr(table, "db", None), getattr(table, "name", None)):
        if value:
            parts.append(str(value))
    return normalize_table(".".join(parts))


def _target_table_name(tree) -> str:
    """Extract INSERT/CREATE target table, including INSERT column-list syntax."""
    if exp is None:
        return ""
    if isinstance(tree, exp.Insert):
        return _physical_table_name(tree.this)
    if isinstance(tree, exp.Create):
        return _physical_table_name(tree.this)
    if isinstance(tree, exp.Merge):
        return _physical_table_name(tree.this)
    return ""


def extract_sql_lineage(sql: str) -> dict:
    raw = sql or ""
    reads, writes = set(), set()

    if sqlglot is not None:
        try:
            for tree in sqlglot.parse(raw, read="mysql"):
                target = _target_table_name(tree)
                if target:
                    writes.add(target)

                # CTE aliases are logical query names, not physical warehouse tables.
                cte_names = {
                    str(cte.alias_or_name).lower()
                    for cte in tree.find_all(exp.CTE)
                    if getattr(cte, "alias_or_name", None)
                }

                for table in tree.find_all(exp.Table):
                    physical = _physical_table_name(table)
                    if not physical:
                        continue
                    if physical.lower() in cte_names and not getattr(table, "db", None):
                        continue
                    if target and physical.lower() == target.lower():
                        continue
                    reads.add(physical)
        except Exception:
            # Fall through to the regex parser for unsupported dialect fragments.
            pass

    # Supplement/fallback for StarRocks/MySQL syntax that sqlglot cannot parse.
    # Run independently for writes because a failed target parse must never turn
    # "table(col1,...)" into a separate model.
    if not writes:
        for value in re.findall(
            r"(?is)\b(?:INSERT\s+(?:OVERWRITE\s+)?(?:INTO\s+)?|CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)([`\w.]+)",
            raw,
        ):
            physical = normalize_table(value)
            if physical:
                writes.add(physical)

    if not reads:
        for value in re.findall(r"(?is)\b(?:FROM|JOIN)\s+([`\w.]+)", raw):
            physical = normalize_table(value)
            if physical:
                reads.add(physical)

    # Final canonicalization also cleans any values coming from older/fallback paths.
    reads = {normalize_table(x) for x in reads if normalize_table(x)}
    writes = {normalize_table(x) for x in writes if normalize_table(x)}
    reads -= writes
    return {"reads": sorted(reads), "writes": sorted(writes)}


class CodeIndexService:
    def __init__(self, db: Session):
        self.db = db

    def rebuild(self) -> dict:
        artifacts = self.db.query(SourceArtifact).all()
        self.db.query(CodeLineage).filter(
            CodeLineage.relation_type == "TABLE_LINEAGE"
        ).delete(synchronize_session=False)
        edges = 0
        for artifact in artifacts:
            info = extract_sql_lineage(artifact.sql_text or "")
            targets = info["writes"] or [None]
            for source in info["reads"]:
                for target in targets:
                    self.db.add(
                        CodeLineage(
                            artifact_id=artifact.id,
                            relation_type="TABLE_LINEAGE",
                            source_name=source,
                            target_name=target,
                        )
                    )
                    edges += 1
        self.db.commit()
        return {"artifacts": len(artifacts), "table_lineage_edges": edges}

    def search(self, query: str, limit: int = 50) -> list[SourceArtifact]:
        q = f"%{query}%"
        return (
            self.db.query(SourceArtifact)
            .filter(
                (SourceArtifact.task_name.like(q))
                | (SourceArtifact.sql_text.like(q))
                | (SourceArtifact.file_path.like(q))
            )
            .order_by(SourceArtifact.id.desc())
            .limit(limit)
            .all()
        )

    def table_lineage(self, table: str | None = None) -> list[dict]:
        query = self.db.query(CodeLineage).filter(
            CodeLineage.relation_type == "TABLE_LINEAGE"
        )
        if table:
            canonical = normalize_table(table)
            query = query.filter(
                (CodeLineage.source_name == canonical)
                | (CodeLineage.target_name == canonical)
            )
        return [
            {
                "source": x.source_name,
                "target": x.target_name,
                "artifact_id": x.artifact_id,
            }
            for x in query.limit(500).all()
        ]

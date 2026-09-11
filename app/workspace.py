from __future__ import annotations
import json
import shutil
from datetime import datetime
from pathlib import Path
from app.config import settings


class WorkspaceManager:
    def __init__(self):
        cfg = settings()
        self.source_root = Path(cfg.app_source_root).resolve()
        self.workspace_root = Path(cfg.app_workspace_root).resolve()
        self.release_root = Path(cfg.app_release_root).resolve()
        cfg.ensure_directories()

    @staticmethod
    def _safe_child(root: Path, *parts: str) -> Path:
        candidate = root.joinpath(*parts).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError("非法文件路径")
        return candidate

    def create_task_workspace(self, task_no: str, requirement: str, design: dict, sql: str, model_name: str | None) -> Path:
        root = self._safe_child(self.workspace_root, task_no)
        for rel in ["context", "design", "sql/ddl", "sql/etl", "validation", "result"]:
            (root / rel).mkdir(parents=True, exist_ok=True)
        (root / "requirement.md").write_text(f"# {task_no}\n\n{requirement}\n", encoding="utf-8")
        (root / "design" / "model.json").write_text(json.dumps(design, ensure_ascii=False, indent=2), encoding="utf-8")
        sql_path = root / "sql" / "etl" / f"{model_name or 'task'}.sql"
        sql_path.write_text(sql, encoding="utf-8")
        return root

    def save_task_sql(self, task_no: str, model_name: str | None, sql: str) -> Path:
        root = self._safe_child(self.workspace_root, task_no)
        path = root / "sql" / "etl" / f"{model_name or 'task'}.sql"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(sql, encoding="utf-8")
        return path

    def write_result(self, task_no: str, name: str, payload: dict) -> Path:
        root = self._safe_child(self.workspace_root, task_no)
        path = root / "result" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path

    def write_validation(self, task_no: str, payload: list[dict]) -> Path:
        root = self._safe_child(self.workspace_root, task_no)
        path = root / "validation" / "validation-report.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path

    def list_task_files(self, task_no: str) -> list[dict]:
        root = self._safe_child(self.workspace_root, task_no)
        if not root.exists(): return []
        result = []
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            result.append({"path": path.relative_to(root).as_posix(), "size": path.stat().st_size, "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat()})
        return result

    def read_task_file(self, task_no: str, relative_path: str) -> str:
        root = self._safe_child(self.workspace_root, task_no)
        path = self._safe_child(root, relative_path)
        if not path.is_file(): raise FileNotFoundError(relative_path)
        return path.read_text(encoding="utf-8")

    def create_release(self, task, validation_items: list[dict], reviewer: str, note: str | None) -> Path:
        source = self._safe_child(self.workspace_root, task.task_no)
        target = self._safe_child(self.release_root, task.task_no)
        if target.exists(): shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        for rel in ["design", "sql", "validation"]:
            src = source / rel
            if src.exists(): shutil.copytree(src, target / rel, dirs_exist_ok=True)
        manifest = {"task_no":task.task_no,"title":task.title,"domain":task.domain,"subject":task.subject,"model_name":task.model_name,"reviewer":reviewer,"review_note":note,"approved_at":datetime.utcnow().isoformat(),"validation":validation_items,"source":"workspace","publish_to_dolphinscheduler":False}
        (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        (target / "release-note.md").write_text(f"# {task.title}\n\n- 任务：{task.task_no}\n- 主题域：{task.domain or '-'}\n- 主题：{task.subject or '-'}\n- 模型：{task.model_name or '-'}\n- 验收人：{reviewer}\n- 状态：RELEASE_READY\n\n当前版本只生成发布包，不自动写回 DolphinScheduler。\n", encoding="utf-8")
        return target

    def list_releases(self) -> list[dict]:
        result = []
        if not self.release_root.exists(): return result
        for p in sorted(self.release_root.iterdir(), reverse=True):
            if p.is_dir(): result.append({"task_no":p.name,"path":str(p),"files":sum(1 for x in p.rglob("*") if x.is_file())})
        return result

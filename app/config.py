from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Warehouse Agent"
    app_env: str = "dev"
    app_database_url: str = "sqlite:///./data/warehouse_agent.db"
    app_mock_external: bool = True
    app_secret_key: str = "change-me-in-production"
    app_cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    # 业务 SQL 的三个独立数据区。source 只读，workspace 可写，release 仅在人工验收后生成。
    app_source_root: str = "./data/source"
    app_workspace_root: str = "./data/workspaces"
    app_release_root: str = "./data/releases"

    # 从 DolphinScheduler 元数据库同步时，默认只导入 SQL 类型任务。
    app_ds_sql_task_types: str = "SQL"
    app_ds_query_timeout_seconds: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [x.strip() for x in self.app_cors_origins.split(",") if x.strip()]

    @property
    def ds_sql_task_types(self) -> set[str]:
        return {x.strip().upper() for x in self.app_ds_sql_task_types.split(",") if x.strip()}

    def ensure_directories(self) -> None:
        for value in (self.app_source_root, self.app_workspace_root, self.app_release_root, "./data"):
            Path(value).mkdir(parents=True, exist_ok=True)


@lru_cache
def settings() -> Settings:
    return Settings()

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DataSourceCreate(BaseModel):
    name: str
    type: str = Field(pattern="^(MYSQL|STARROCKS)$")
    host: str
    port: int
    username: str
    password: str | None = None
    database_name: str | None = None
    environment: str = "PROD"
    readonly: bool = True


class DataSourceOut(ORM):
    id: int
    name: str
    type: str
    host: str
    port: int
    username: str
    database_name: str | None
    environment: str
    readonly: bool
    enabled: bool
    last_snapshot_at: datetime | None


class DolphinSchedulerConfigIn(BaseModel):
    name: str = "DolphinScheduler"
    host: str
    port: int = 3306
    username: str
    password: str | None = None
    database_name: str = "dolphinscheduler"


class DolphinSchedulerImportRequest(BaseModel):
    project_code: str | None = None
    project_name: str | None = None
    overwrite: bool = True


class TaskCreate(BaseModel):
    title: str
    requirement: str
    owner: str = "Yang"


class TaskOut(ORM):
    id: int
    task_no: str
    title: str
    requirement: str
    domain: str | None
    subject: str | None
    model_name: str | None
    phase: str
    status: str
    workspace_path: str | None
    release_path: str | None
    owner: str
    created_at: datetime
    updated_at: datetime


class SqlUpdate(BaseModel):
    sql: str


class AgentMessage(BaseModel):
    message: str


class ReviewRequest(BaseModel):
    note: str | None = None
    reviewer: str = "Yang"


class SettingsUpdate(BaseModel):
    values: dict[str, str]

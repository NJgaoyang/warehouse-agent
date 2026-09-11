from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import declarative_base, mapped_column, Mapped, sessionmaker
from app.config import settings

cfg = settings()
args = {"check_same_thread": False} if cfg.app_database_url.startswith("sqlite") else {}
engine = create_engine(cfg.app_database_url, future=True, pool_pre_ping=True, connect_args=args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DataSource(Base):
    __tablename__ = "datasource"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(30))
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer)
    username: Mapped[str] = mapped_column(String(100))
    encrypted_password: Mapped[str | None] = mapped_column(Text, nullable=True)
    database_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    environment: Mapped[str] = mapped_column(String(30), default="PROD")
    readonly: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_snapshot_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DolphinSchedulerConfig(Base):
    __tablename__ = "dolphinscheduler_config"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), default="DolphinScheduler")
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=3306)
    username: Mapped[str] = mapped_column(String(100))
    encrypted_password: Mapped[str | None] = mapped_column(Text, nullable=True)
    database_name: Mapped[str] = mapped_column(String(100), default="dolphinscheduler")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SourceArtifact(Base):
    __tablename__ = "source_artifact"
    __table_args__ = (UniqueConstraint("source_type", "external_key", name="uq_source_artifact_external"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(40), default="DOLPHINSCHEDULER")
    external_key: Mapped[str] = mapped_column(String(160), index=True)
    project_code: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    project_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    workflow_code: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    workflow_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    task_code: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    task_name: Mapped[str] = mapped_column(String(180))
    task_type: Mapped[str] = mapped_column(String(50), default="SQL")
    datasource_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_path: Mapped[str] = mapped_column(String(600), index=True)
    metadata_path: Mapped[str | None] = mapped_column(String(600), nullable=True)
    sql_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_params_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CodeLineage(Base):
    __tablename__ = "code_lineage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artifact_id: Mapped[int] = mapped_column(ForeignKey("source_artifact.id"), index=True)
    relation_type: Mapped[str] = mapped_column(String(30))
    source_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    target_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MetadataTable(Base):
    __tablename__ = "metadata_table"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    datasource_id: Mapped[int] = mapped_column(ForeignKey("datasource.id"), index=True)
    database_name: Mapped[str] = mapped_column(String(100), index=True)
    table_name: Mapped[str] = mapped_column(String(180), index=True)
    table_comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    layer: Mapped[str | None] = mapped_column(String(20), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(80), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(80), nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ddl: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MetadataColumn(Base):
    __tablename__ = "metadata_column"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("metadata_table.id"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    data_type: Mapped[str] = mapped_column(String(100))
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Domain(Base):
    __tablename__ = "dw_domain"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    table_count: Mapped[int] = mapped_column(Integer, default=0)


class Subject(Base):
    __tablename__ = "dw_subject"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain_id: Mapped[int] = mapped_column(ForeignKey("dw_domain.id"), index=True)
    code: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(80))


class Task(Base):
    __tablename__ = "agent_task"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(180))
    requirement: Mapped[str] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(String(80), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    phase: Mapped[str] = mapped_column(String(50), default="CONTEXT_ANALYSIS")
    status: Mapped[str] = mapped_column(String(50), default="RUNNING")
    workspace_path: Mapped[str | None] = mapped_column(String(600), nullable=True)
    release_path: Mapped[str | None] = mapped_column(String(600), nullable=True)
    design_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    sql_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str] = mapped_column(String(80), default="Agent")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Execution(Base):
    __tablename__ = "agent_sql_execution"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("agent_task.id"), nullable=True, index=True)
    execution_type: Mapped[str] = mapped_column(String(40), default="SQL")
    datasource_id: Mapped[int | None] = mapped_column(ForeignKey("datasource.id"), nullable=True)
    query_id: Mapped[str] = mapped_column(String(100), index=True)
    sql_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="RUNNING")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scanned_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    affected_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    log_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class ValidationResult(Base):
    __tablename__ = "agent_validation"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("agent_task.id"), index=True)
    rule_name: Mapped[str] = mapped_column(String(180))
    expected_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actual_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    difference_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="PASS")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Review(Base):
    __tablename__ = "agent_review"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("agent_task.id"), index=True)
    action: Mapped[str] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer: Mapped[str] = mapped_column(String(80), default="Yang")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SystemSetting(Base):
    __tablename__ = "system_setting"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True)
    value: Mapped[str] = mapped_column(Text)

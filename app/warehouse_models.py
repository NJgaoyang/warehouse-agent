from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WarehouseModel(Base):
    """A warehouse table inferred from DolphinScheduler SQL and metadata.

    This is intentionally separate from MetadataTable: MetadataTable describes what
    physically exists in a database; WarehouseModel describes what the code tells us
    about the logical warehouse architecture.
    """

    __tablename__ = "warehouse_model"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    qualified_name: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    database_name: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    table_name: Mapped[str] = mapped_column(String(220), index=True)
    layer: Mapped[str] = mapped_column(String(30), default="UNKNOWN", index=True)
    domain_code: Mapped[str] = mapped_column(String(60), default="unknown", index=True)
    domain_name: Mapped[str] = mapped_column(String(100), default="未识别域", index=True)
    subject_code: Mapped[str] = mapped_column(String(80), default="unknown", index=True)
    subject_name: Mapped[str] = mapped_column(String(120), default="未识别主题", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    produced_by_count: Mapped[int] = mapped_column(Integer, default=0)
    consumed_by_count: Mapped[int] = mapped_column(Integer, default=0)
    upstream_count: Mapped[int] = mapped_column(Integer, default=0)
    downstream_count: Mapped[int] = mapped_column(Integer, default=0)
    evidence_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_codes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

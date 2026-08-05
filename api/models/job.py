import enum
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from api.database import Base
from api.models.base import TimestampMixin


class JobState(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    arq_job_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)

    # Event context
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    delivery_id: Mapped[str | None] = mapped_column(String(128), index=True)
    repository_full_name: Mapped[str | None] = mapped_column(String(512), index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)  # raw JSON

    # State machine
    state: Mapped[JobState] = mapped_column(
        Enum(JobState), default=JobState.PENDING, nullable=False, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

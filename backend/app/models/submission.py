from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SubmissionStatus(str, Enum):
    queued = "queued"
    judging = "judging"
    judged = "judged"
    invalid = "invalid"
    runtime_error = "runtime_error"
    timeout = "timeout"
    error = "error"


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problems.id"), index=True, nullable=False
    )
    contest_id: Mapped[int | None] = mapped_column(
        ForeignKey("contests.id", ondelete="SET NULL"), index=True, nullable=True
    )
    graph_json_path: Mapped[str] = mapped_column(String(500), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[SubmissionStatus] = mapped_column(
        SAEnum(SubmissionStatus, name="submission_status"),
        default=SubmissionStatus.queued,
        nullable=False,
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    judge_log: Mapped[str] = mapped_column(Text, default="", nullable=False)
    runtime_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    judge_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    judge_finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    raw_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

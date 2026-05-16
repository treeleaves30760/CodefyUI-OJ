from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ProblemDifficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    statement_md: Mapped[str] = mapped_column(Text, default="", nullable=False)
    difficulty: Mapped[ProblemDifficulty] = mapped_column(
        SAEnum(ProblemDifficulty, name="problem_difficulty"),
        default=ProblemDifficulty.easy,
        nullable=False,
    )
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    starter_template_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    judge_spec: Mapped[dict] = mapped_column(JSON, nullable=False)
    hidden_test_data_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    time_limit_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, default=2048, nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    practice_visible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    @property
    def has_test_data(self) -> bool:
        return self.hidden_test_data_path is not None

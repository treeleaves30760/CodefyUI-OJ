from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ContestVisibility(str, Enum):
    public = "public"
    private = "private"
    invite_only = "invite_only"


class Contest(Base):
    __tablename__ = "contests"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description_md: Mapped[str] = mapped_column(Text, default="", nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    visibility: Mapped[ContestVisibility] = mapped_column(
        SAEnum(ContestVisibility, name="contest_visibility"),
        default=ContestVisibility.public,
        nullable=False,
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ContestProblem(Base):
    __tablename__ = "contest_problems"

    contest_id: Mapped[int] = mapped_column(
        ForeignKey("contests.id", ondelete="CASCADE"), nullable=False
    )
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"), nullable=False
    )
    points: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (PrimaryKeyConstraint("contest_id", "problem_id"),)


class ContestParticipant(Base):
    __tablename__ = "contest_participants"

    contest_id: Mapped[int] = mapped_column(
        ForeignKey("contests.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (PrimaryKeyConstraint("contest_id", "user_id"),)

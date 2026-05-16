from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.problem import ProblemDifficulty
from app.schemas.judge_spec import JudgeSpec


class ProblemBase(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]+$", max_length=80, min_length=1)
    title: str = Field(max_length=200, min_length=1)
    statement_md: str = ""
    difficulty: ProblemDifficulty = ProblemDifficulty.easy
    tags: list[str] = Field(default_factory=list)
    time_limit_seconds: int = Field(default=60, ge=1, le=600)
    memory_limit_mb: int = Field(default=2048, ge=64, le=16384)
    published: bool = False
    practice_visible: bool = False


class ProblemCreate(ProblemBase):
    starter_template_json: dict[str, Any]
    judge_spec: JudgeSpec


class ProblemUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200, min_length=1)
    statement_md: str | None = None
    difficulty: ProblemDifficulty | None = None
    tags: list[str] | None = None
    starter_template_json: dict[str, Any] | None = None
    judge_spec: JudgeSpec | None = None
    time_limit_seconds: int | None = Field(default=None, ge=1, le=600)
    memory_limit_mb: int | None = Field(default=None, ge=64, le=16384)
    published: bool | None = None
    practice_visible: bool | None = None


class ProblemRead(ProblemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    starter_template_json: dict[str, Any]
    judge_spec: dict[str, Any]
    has_test_data: bool
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime


class ProblemListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    difficulty: ProblemDifficulty
    tags: list[str]
    published: bool
    practice_visible: bool
    has_test_data: bool
    created_at: datetime

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.submission import SubmissionStatus


class SubmissionCreate(BaseModel):
    problem_slug: str = Field(min_length=1)
    graph_json: dict[str, Any]
    contest_id: int | None = None


class SubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    problem_id: int
    contest_id: int | None
    submitted_at: datetime
    status: SubmissionStatus
    score: float | None
    runtime_ms: int | None
    judge_started_at: datetime | None
    judge_finished_at: datetime | None


class SubmissionDetail(SubmissionRead):
    judge_log: str
    raw_result: dict[str, Any] | None


class SubmissionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    problem_id: int
    contest_id: int | None
    submitted_at: datetime
    status: SubmissionStatus
    score: float | None
    runtime_ms: int | None

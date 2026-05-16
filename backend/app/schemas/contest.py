from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.contest import ContestVisibility


ContestRuntimeStatus = Literal["upcoming", "active", "past"]


class ContestProblemEntry(BaseModel):
    problem_slug: str = Field(min_length=1)
    points: int = Field(default=100, ge=1, le=10000)
    display_order: int = Field(default=0, ge=0)


class ContestProblemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    problem_id: int
    problem_slug: str
    problem_title: str
    points: int
    display_order: int


class ContestBase(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]+$", max_length=80, min_length=1)
    title: str = Field(max_length=200, min_length=1)
    description_md: str = ""
    start_at: datetime
    end_at: datetime
    visibility: ContestVisibility = ContestVisibility.public

    @model_validator(mode="after")
    def end_after_start(self) -> "ContestBase":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class ContestCreate(ContestBase):
    problems: list[ContestProblemEntry] = Field(default_factory=list)


class ContestUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200, min_length=1)
    description_md: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    visibility: ContestVisibility | None = None


class ContestRead(ContestBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime
    runtime_status: ContestRuntimeStatus
    problems: list[ContestProblemRead] = Field(default_factory=list)
    participant_count: int = 0
    joined: bool = False


class ContestListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    start_at: datetime
    end_at: datetime
    visibility: ContestVisibility
    runtime_status: ContestRuntimeStatus
    problem_count: int


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    display_name: str
    total_score: float
    per_problem: dict[int, float]


class Leaderboard(BaseModel):
    contest_id: int
    contest_slug: str
    generated_at: datetime
    entries: list[LeaderboardEntry]

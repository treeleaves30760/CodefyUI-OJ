from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.permissions import require_teacher
from app.core.security import current_active_user
from app.core.storage import ensure_dir, get_test_data_dir
from app.db import get_async_session
from app.models.problem import Problem
from app.models.user import User, UserRole
from app.schemas.problem import (
    ProblemCreate,
    ProblemListItem,
    ProblemRead,
    ProblemUpdate,
)

router = APIRouter()


def _student_visible_only(user: User) -> bool:
    return user.role == UserRole.student and not user.is_superuser


def _validate_template(template: dict, required_ids: list[str]) -> None:
    nodes = template.get("nodes")
    if not isinstance(nodes, list):
        raise HTTPException(
            status_code=400,
            detail="starter_template_json must contain a 'nodes' array",
        )
    if not isinstance(template.get("edges"), list):
        raise HTTPException(
            status_code=400,
            detail="starter_template_json must contain an 'edges' array",
        )
    existing = {n.get("id") for n in nodes if isinstance(n, dict)}
    missing = set(required_ids) - existing
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"starter_template missing required node IDs: {sorted(missing)}",
        )


async def _get_problem_or_404(slug: str, db: AsyncSession) -> Problem:
    stmt = select(Problem).where(Problem.slug == slug)
    result = await db.execute(stmt)
    problem = result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return problem


@router.get("", response_model=list[ProblemListItem])
async def list_problems(
    published_only: Annotated[bool, Query()] = True,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    is_practice = get_settings().app_mode == "practice"
    stmt = select(Problem).order_by(Problem.created_at.desc())
    if published_only or _student_visible_only(user):
        stmt = stmt.where(Problem.published.is_(True))
    if is_practice:
        stmt = stmt.where(Problem.practice_visible.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{slug}", response_model=ProblemRead)
async def get_problem(
    slug: str,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    problem = await _get_problem_or_404(slug, db)
    if not problem.published and _student_visible_only(user):
        raise HTTPException(status_code=404, detail="Problem not found")
    if get_settings().app_mode == "practice" and not problem.practice_visible:
        raise HTTPException(status_code=404, detail="Problem not found")
    return problem


@router.post("", response_model=ProblemRead, status_code=status.HTTP_201_CREATED)
async def create_problem(
    body: ProblemCreate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_teacher),
):
    existing = await db.execute(select(Problem).where(Problem.slug == body.slug))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Slug already exists")

    _validate_template(body.starter_template_json, body.judge_spec.required_node_ids)

    problem = Problem(
        slug=body.slug,
        title=body.title,
        statement_md=body.statement_md,
        difficulty=body.difficulty,
        tags=body.tags,
        starter_template_json=body.starter_template_json,
        judge_spec=body.judge_spec.model_dump(mode="json"),
        time_limit_seconds=body.time_limit_seconds,
        memory_limit_mb=body.memory_limit_mb,
        published=body.published,
        created_by_user_id=user.id,
    )
    db.add(problem)
    await db.commit()
    await db.refresh(problem)
    return problem


@router.put("/{slug}", response_model=ProblemRead)
async def update_problem(
    slug: str,
    body: ProblemUpdate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_teacher),
):
    problem = await _get_problem_or_404(slug, db)
    updates = body.model_dump(exclude_unset=True)

    new_template = updates.get("starter_template_json", problem.starter_template_json)
    new_spec = updates.get("judge_spec")
    if isinstance(new_spec, dict):
        required_ids = new_spec.get("required_node_ids", problem.judge_spec.get("required_node_ids", []))
    else:
        required_ids = problem.judge_spec.get("required_node_ids", [])
    if "starter_template_json" in updates or "judge_spec" in updates:
        _validate_template(new_template, required_ids)

    if "judge_spec" in updates and isinstance(new_spec, dict):
        updates["judge_spec"] = new_spec

    for key, value in updates.items():
        setattr(problem, key, value)

    await db.commit()
    await db.refresh(problem)
    return problem


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_problem(
    slug: str,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_teacher),
):
    problem = await _get_problem_or_404(slug, db)
    await db.delete(problem)
    await db.commit()


@router.get("/{slug}/template")
async def download_template(
    slug: str,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    problem = await _get_problem_or_404(slug, db)
    if not problem.published and _student_visible_only(user):
        raise HTTPException(status_code=404, detail="Problem not found")
    if get_settings().app_mode == "practice" and not problem.practice_visible:
        raise HTTPException(status_code=404, detail="Problem not found")
    return problem.starter_template_json


@router.post("/{slug}/test-data", status_code=status.HTTP_204_NO_CONTENT)
async def upload_test_data(
    slug: str,
    file: UploadFile,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_teacher),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    if not file.filename.lower().endswith((".zip", ".tar.gz", ".tgz")):
        raise HTTPException(status_code=400, detail="Test data must be .zip / .tar.gz")

    settings = get_settings()
    content = await file.read()
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Test data exceeds 100 MB limit")

    problem = await _get_problem_or_404(slug, db)

    test_dir = ensure_dir(get_test_data_dir(slug))
    target = test_dir / file.filename
    target.write_bytes(content)

    problem.hidden_test_data_path = str(target.resolve())
    await db.commit()

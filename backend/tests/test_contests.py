import os

os.environ.setdefault("OJ_JUDGE_DISABLED", "true")

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import update

from app.models.user import User, UserRole


VALID_TEMPLATE = {
    "name": "x",
    "description": "",
    "nodes": [
        {"id": "__INPUT__", "type": "CSVReader", "data": {"params": {"path": "x"}}},
        {"id": "__SUBMIT__", "type": "Print", "data": {"params": {}}},
    ],
    "edges": [],
}

VALID_JUDGE_SPEC = {
    "required_node_ids": ["__INPUT__", "__SUBMIT__"],
    "input_patches": [],
    "output_reads": [{"node_id": "__SUBMIT__", "port": "v", "save_as": "y_pred"}],
    "scoring": {
        "method": "accuracy",
        "target_output": "y_pred",
        "ground_truth": "{hidden_test_data}/y.csv",
        "full_score": 100,
    },
}


def _utc(s: str) -> str:
    return s + "Z" if not s.endswith("Z") else s


async def _register_login(client: AsyncClient, email: str, pw: str = "password123") -> str:
    r = await client.post(
        "/api/auth/register",
        json={"email": email, "password": pw, "display_name": email.split("@")[0]},
    )
    assert r.status_code == 201
    r = await client.post(
        "/api/auth/jwt/login",
        data={"username": email, "password": pw},
    )
    return r.json()["access_token"]


async def _set_role(engine, email: str, role: UserRole) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        await session.execute(update(User).where(User.email == email).values(role=role))
        await session.commit()


@pytest_asyncio.fixture
async def teacher_token(client: AsyncClient, test_engine) -> str:
    token = await _register_login(client, "t@codefy.dev")
    await _set_role(test_engine, "t@codefy.dev", UserRole.teacher)
    r = await client.post(
        "/api/auth/jwt/login", data={"username": "t@codefy.dev", "password": "password123"}
    )
    return r.json()["access_token"]


@pytest_asyncio.fixture
async def problem_slug(client: AsyncClient, teacher_token: str) -> str:
    r = await client.post(
        "/api/problems",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "slug": "p1",
            "title": "P1",
            "starter_template_json": VALID_TEMPLATE,
            "judge_spec": VALID_JUDGE_SPEC,
            "published": True,
        },
    )
    assert r.status_code == 201, r.text
    return "p1"


@pytest.mark.asyncio
async def test_create_contest_and_get(client, teacher_token, problem_slug):
    now = datetime.now(timezone.utc)
    body = {
        "slug": "winter-cup",
        "title": "Winter Cup",
        "description_md": "## Welcome",
        "start_at": (now - timedelta(hours=1)).isoformat(),
        "end_at": (now + timedelta(hours=2)).isoformat(),
        "visibility": "public",
        "problems": [{"problem_slug": problem_slug, "points": 100, "display_order": 0}],
    }
    r = await client.post(
        "/api/contests",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json=body,
    )
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["slug"] == "winter-cup"
    assert created["runtime_status"] == "active"
    assert len(created["problems"]) == 1
    assert created["problems"][0]["problem_slug"] == problem_slug

    r = await client.get(
        "/api/contests/winter-cup",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Winter Cup"


@pytest.mark.asyncio
async def test_student_can_join_contest(client, teacher_token, problem_slug):
    now = datetime.now(timezone.utc)
    body = {
        "slug": "open-cup",
        "title": "Open",
        "start_at": (now - timedelta(hours=1)).isoformat(),
        "end_at": (now + timedelta(hours=1)).isoformat(),
        "problems": [{"problem_slug": problem_slug}],
    }
    r = await client.post(
        "/api/contests",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json=body,
    )
    assert r.status_code == 201

    student = await _register_login(client, "s@codefy.dev")
    r = await client.post(
        "/api/contests/open-cup/join",
        headers={"Authorization": f"Bearer {student}"},
    )
    assert r.status_code == 200
    assert r.json()["joined"] is True
    assert r.json()["participant_count"] == 1


@pytest.mark.asyncio
async def test_list_contests_filters_by_status(client, teacher_token, problem_slug):
    now = datetime.now(timezone.utc)
    contests = [
        ("past", -3, -1),
        ("active", -1, 1),
        ("upcoming", 1, 3),
    ]
    for slug, sh, eh in contests:
        r = await client.post(
            "/api/contests",
            headers={"Authorization": f"Bearer {teacher_token}"},
            json={
                "slug": slug,
                "title": slug,
                "start_at": (now + timedelta(hours=sh)).isoformat(),
                "end_at": (now + timedelta(hours=eh)).isoformat(),
                "problems": [{"problem_slug": problem_slug}],
            },
        )
        assert r.status_code == 201, r.text

    r = await client.get(
        "/api/contests?status=active",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert r.status_code == 200
    slugs = {c["slug"] for c in r.json()}
    assert slugs == {"active"}


@pytest.mark.asyncio
async def test_leaderboard_empty(client, teacher_token, problem_slug):
    now = datetime.now(timezone.utc)
    r = await client.post(
        "/api/contests",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "slug": "empty-lb",
            "title": "Empty",
            "start_at": (now - timedelta(hours=1)).isoformat(),
            "end_at": (now + timedelta(hours=1)).isoformat(),
            "problems": [{"problem_slug": problem_slug}],
        },
    )
    assert r.status_code == 201

    r = await client.get(
        "/api/contests/empty-lb/leaderboard",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["entries"] == []
    assert body["contest_slug"] == "empty-lb"


@pytest.mark.asyncio
async def test_leaderboard_computes_max_per_problem(
    client, teacher_token, problem_slug, test_engine
):
    """Insert fake judged submissions directly and verify aggregation."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models import Problem, Submission, SubmissionStatus, User

    now = datetime.now(timezone.utc)
    r = await client.post(
        "/api/contests",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "slug": "agg",
            "title": "Agg",
            "start_at": (now - timedelta(hours=1)).isoformat(),
            "end_at": (now + timedelta(hours=1)).isoformat(),
            "problems": [{"problem_slug": problem_slug}],
        },
    )
    assert r.status_code == 201
    contest = r.json()

    alice = await _register_login(client, "alice@codefy.dev")
    bob = await _register_login(client, "bob@codefy.dev")

    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        problem = (await session.execute(
            __import__("sqlalchemy").select(Problem).where(Problem.slug == problem_slug)
        )).scalar_one()

        alice_obj = (await session.execute(
            __import__("sqlalchemy").select(User).where(User.email == "alice@codefy.dev")
        )).scalar_one()
        bob_obj = (await session.execute(
            __import__("sqlalchemy").select(User).where(User.email == "bob@codefy.dev")
        )).scalar_one()

        session.add_all([
            Submission(
                user_id=alice_obj.id, problem_id=problem.id, contest_id=contest["id"],
                graph_json_path="", status=SubmissionStatus.judged, score=70.0,
            ),
            Submission(
                user_id=alice_obj.id, problem_id=problem.id, contest_id=contest["id"],
                graph_json_path="", status=SubmissionStatus.judged, score=90.0,
            ),
            Submission(
                user_id=bob_obj.id, problem_id=problem.id, contest_id=contest["id"],
                graph_json_path="", status=SubmissionStatus.judged, score=80.0,
            ),
        ])
        await session.commit()

    r = await client.get(
        "/api/contests/agg/leaderboard",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert r.status_code == 200
    entries = r.json()["entries"]
    assert len(entries) == 2
    assert entries[0]["display_name"] == "alice"
    assert entries[0]["total_score"] == 90.0
    assert entries[0]["rank"] == 1
    assert entries[1]["display_name"] == "bob"
    assert entries[1]["total_score"] == 80.0
    assert entries[1]["rank"] == 2


@pytest.mark.asyncio
async def test_contest_submission_records_contest_id(
    client, teacher_token, problem_slug
):
    now = datetime.now(timezone.utc)
    r = await client.post(
        "/api/contests",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "slug": "submit-contest",
            "title": "C",
            "start_at": (now - timedelta(hours=1)).isoformat(),
            "end_at": (now + timedelta(hours=1)).isoformat(),
            "problems": [{"problem_slug": problem_slug}],
        },
    )
    assert r.status_code == 201
    contest = r.json()

    student = await _register_login(client, "joiner@codefy.dev")

    # Must join before submitting
    r = await client.post(
        "/api/submissions",
        headers={"Authorization": f"Bearer {student}"},
        json={
            "problem_slug": problem_slug,
            "graph_json": VALID_TEMPLATE,
            "contest_id": contest["id"],
        },
    )
    assert r.status_code == 403

    r = await client.post(
        f"/api/contests/{contest['slug']}/join",
        headers={"Authorization": f"Bearer {student}"},
    )
    assert r.status_code == 200

    r = await client.post(
        "/api/submissions",
        headers={"Authorization": f"Bearer {student}"},
        json={
            "problem_slug": problem_slug,
            "graph_json": VALID_TEMPLATE,
            "contest_id": contest["id"],
        },
    )
    assert r.status_code == 201
    assert r.json()["contest_id"] == contest["id"]

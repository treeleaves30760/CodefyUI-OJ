import os

os.environ.setdefault("OJ_JUDGE_DISABLED", "true")

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import update

from app.models.user import User, UserRole


VALID_TEMPLATE = {
    "name": "iris",
    "description": "",
    "nodes": [
        {"id": "__INPUT__", "type": "CSVReader", "data": {"params": {"path": "x"}}},
        {"id": "__SUBMIT__", "type": "Print", "data": {"params": {}}},
    ],
    "edges": [],
}

VALID_JUDGE_SPEC = {
    "required_node_ids": ["__INPUT__", "__SUBMIT__"],
    "input_patches": [
        {"node_id": "__INPUT__", "param_overrides": {"path": "{hidden_test_data}/X.csv"}}
    ],
    "output_reads": [{"node_id": "__SUBMIT__", "port": "value", "save_as": "y_pred"}],
    "scoring": {
        "method": "accuracy",
        "target_output": "y_pred",
        "ground_truth": "{hidden_test_data}/y.csv",
        "full_score": 100,
    },
}


async def _register_login(client: AsyncClient, email: str, pw: str = "password123") -> str:
    r = await client.post(
        "/api/auth/register",
        json={"email": email, "password": pw, "display_name": email.split("@")[0]},
    )
    assert r.status_code == 201, r.text
    r = await client.post(
        "/api/auth/jwt/login",
        data={"username": email, "password": pw},
    )
    return r.json()["access_token"]


async def _make_teacher(test_engine, email: str) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        await session.execute(
            update(User).where(User.email == email).values(role=UserRole.teacher)
        )
        await session.commit()


@pytest_asyncio.fixture
async def teacher_token(client: AsyncClient, test_engine) -> str:
    token = await _register_login(client, "t@codefy.dev")
    await _make_teacher(test_engine, "t@codefy.dev")
    r = await client.post(
        "/api/auth/jwt/login", data={"username": "t@codefy.dev", "password": "password123"}
    )
    return r.json()["access_token"]


@pytest_asyncio.fixture
async def published_problem(client: AsyncClient, teacher_token: str):
    r = await client.post(
        "/api/problems",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "slug": "knn",
            "title": "KNN",
            "starter_template_json": VALID_TEMPLATE,
            "judge_spec": VALID_JUDGE_SPEC,
            "published": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest_asyncio.fixture
async def student_token(client: AsyncClient) -> str:
    return await _register_login(client, "s@codefy.dev")


@pytest.mark.asyncio
async def test_submission_create_returns_queued(client, student_token, published_problem):
    r = await client.post(
        "/api/submissions",
        headers={"Authorization": f"Bearer {student_token}"},
        json={
            "problem_slug": "knn",
            "graph_json": VALID_TEMPLATE,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert body["problem_id"] == published_problem["id"]
    assert body["score"] is None


@pytest.mark.asyncio
async def test_submission_rejects_bad_graph(client, student_token, published_problem):
    r = await client.post(
        "/api/submissions",
        headers={"Authorization": f"Bearer {student_token}"},
        json={
            "problem_slug": "knn",
            "graph_json": {"nodes": "not-a-list", "edges": []},
        },
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_submission_blocks_custom_nodes(client, student_token, published_problem):
    bad = {
        "nodes": [{"id": "x", "type": "custom:malicious", "data": {"params": {}}}],
        "edges": [],
    }
    r = await client.post(
        "/api/submissions",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"problem_slug": "knn", "graph_json": bad},
    )
    assert r.status_code == 400
    assert "custom" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_submission_unknown_problem(client, student_token):
    r = await client.post(
        "/api/submissions",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"problem_slug": "nope", "graph_json": VALID_TEMPLATE},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_my_submissions(client, student_token, published_problem):
    await client.post(
        "/api/submissions",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"problem_slug": "knn", "graph_json": VALID_TEMPLATE},
    )
    await client.post(
        "/api/submissions",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"problem_slug": "knn", "graph_json": VALID_TEMPLATE},
    )
    r = await client.get(
        "/api/submissions",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2


@pytest.mark.asyncio
async def test_get_submission_owner_only(client, student_token, published_problem):
    r = await client.post(
        "/api/submissions",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"problem_slug": "knn", "graph_json": VALID_TEMPLATE},
    )
    sub_id = r.json()["id"]

    other = await _register_login(client, "other@codefy.dev")
    r = await client.get(
        f"/api/submissions/{sub_id}",
        headers={"Authorization": f"Bearer {other}"},
    )
    assert r.status_code == 403

    r = await client.get(
        f"/api/submissions/{sub_id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert r.status_code == 200

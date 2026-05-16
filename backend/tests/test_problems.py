import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import update

from app.models.user import User, UserRole


VALID_TEMPLATE = {
    "name": "Iris KNN template",
    "description": "Fill in the KNN classifier between __INPUT__ and __SUBMIT__",
    "nodes": [
        {
            "id": "__INPUT__",
            "type": "CSVReader",
            "position": {"x": 0, "y": 0},
            "data": {"params": {"path": "iris_train.csv"}},
        },
        {
            "id": "__SUBMIT__",
            "type": "Print",
            "position": {"x": 300, "y": 0},
            "data": {"params": {}},
        },
    ],
    "edges": [],
}

VALID_JUDGE_SPEC = {
    "required_node_ids": ["__INPUT__", "__SUBMIT__"],
    "input_patches": [
        {
            "node_id": "__INPUT__",
            "param_overrides": {"path": "{hidden_test_data}/X_test.csv"},
        }
    ],
    "output_reads": [{"node_id": "__SUBMIT__", "port": "value", "save_as": "y_pred"}],
    "scoring": {
        "method": "accuracy",
        "target_output": "y_pred",
        "ground_truth": "{hidden_test_data}/y_test.csv",
        "threshold": 0.85,
        "full_score": 100,
    },
    "time_limit_seconds": 60,
    "memory_limit_mb": 2048,
}


async def _register_and_login(client: AsyncClient, email: str, password: str = "password123") -> str:
    r = await client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": email.split("@")[0]},
    )
    assert r.status_code == 201, r.text
    r = await client.post(
        "/api/auth/jwt/login",
        data={"username": email, "password": password},
    )
    assert r.status_code == 200, r.text
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
    token = await _register_and_login(client, "teacher@codefy.dev")
    await _make_teacher(test_engine, "teacher@codefy.dev")
    return await _register_and_login(client, "teacher2@codefy.dev")  # fresh teacher for cleanliness


@pytest_asyncio.fixture
async def fresh_teacher_token(client: AsyncClient, test_engine) -> str:
    email = "fresh-teacher@codefy.dev"
    token = await _register_and_login(client, email)
    await _make_teacher(test_engine, email)
    # Re-login so new role is reflected in subsequent /me, though token itself doesn't carry role.
    r = await client.post(
        "/api/auth/jwt/login",
        data={"username": email, "password": "password123"},
    )
    return r.json()["access_token"]


@pytest_asyncio.fixture
async def student_token(client: AsyncClient) -> str:
    return await _register_and_login(client, "student@codefy.dev")


@pytest.mark.asyncio
async def test_student_cannot_create_problem(client, student_token):
    r = await client.post(
        "/api/problems",
        headers={"Authorization": f"Bearer {student_token}"},
        json={
            "slug": "test-1",
            "title": "Test",
            "starter_template_json": VALID_TEMPLATE,
            "judge_spec": VALID_JUDGE_SPEC,
        },
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_teacher_can_create_and_get_problem(client, fresh_teacher_token):
    r = await client.post(
        "/api/problems",
        headers={"Authorization": f"Bearer {fresh_teacher_token}"},
        json={
            "slug": "iris-knn",
            "title": "Iris KNN",
            "statement_md": "Build a KNN classifier.",
            "difficulty": "easy",
            "tags": ["classification", "knn"],
            "starter_template_json": VALID_TEMPLATE,
            "judge_spec": VALID_JUDGE_SPEC,
            "published": True,
        },
    )
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["slug"] == "iris-knn"
    assert created["has_test_data"] is False
    assert "judge_spec" in created

    r = await client.get(
        "/api/problems/iris-knn",
        headers={"Authorization": f"Bearer {fresh_teacher_token}"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Iris KNN"


@pytest.mark.asyncio
async def test_create_rejects_template_missing_required_node(client, fresh_teacher_token):
    bad_template = {"name": "x", "description": "", "nodes": [], "edges": []}
    r = await client.post(
        "/api/problems",
        headers={"Authorization": f"Bearer {fresh_teacher_token}"},
        json={
            "slug": "bad-1",
            "title": "Bad",
            "starter_template_json": bad_template,
            "judge_spec": VALID_JUDGE_SPEC,
        },
    )
    assert r.status_code == 400
    assert "missing required node IDs" in r.json()["detail"]


@pytest.mark.asyncio
async def test_student_only_sees_published(client, fresh_teacher_token, student_token):
    # Teacher creates one published and one unpublished
    for slug, published in [("pub-1", True), ("draft-1", False)]:
        r = await client.post(
            "/api/problems",
            headers={"Authorization": f"Bearer {fresh_teacher_token}"},
            json={
                "slug": slug,
                "title": slug,
                "starter_template_json": VALID_TEMPLATE,
                "judge_spec": VALID_JUDGE_SPEC,
                "published": published,
            },
        )
        assert r.status_code == 201, r.text

    r = await client.get(
        "/api/problems",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert r.status_code == 200
    slugs = {p["slug"] for p in r.json()}
    assert "pub-1" in slugs
    assert "draft-1" not in slugs

    # Direct access to unpublished problem 404s for student
    r = await client.get(
        "/api/problems/draft-1",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_template_download(client, fresh_teacher_token):
    r = await client.post(
        "/api/problems",
        headers={"Authorization": f"Bearer {fresh_teacher_token}"},
        json={
            "slug": "dl-1",
            "title": "Download me",
            "starter_template_json": VALID_TEMPLATE,
            "judge_spec": VALID_JUDGE_SPEC,
            "published": True,
        },
    )
    assert r.status_code == 201

    r = await client.get(
        "/api/problems/dl-1/template",
        headers={"Authorization": f"Bearer {fresh_teacher_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Iris KNN template"
    assert any(n["id"] == "__INPUT__" for n in body["nodes"])


@pytest.mark.asyncio
async def test_judge_spec_validates_target_output_declared(client, fresh_teacher_token):
    bad_spec = {**VALID_JUDGE_SPEC}
    bad_spec["scoring"] = {**bad_spec["scoring"], "target_output": "not_declared"}
    r = await client.post(
        "/api/problems",
        headers={"Authorization": f"Bearer {fresh_teacher_token}"},
        json={
            "slug": "bad-spec",
            "title": "Bad spec",
            "starter_template_json": VALID_TEMPLATE,
            "judge_spec": bad_spec,
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_update_and_delete_problem(client, fresh_teacher_token):
    r = await client.post(
        "/api/problems",
        headers={"Authorization": f"Bearer {fresh_teacher_token}"},
        json={
            "slug": "upd-1",
            "title": "Old title",
            "starter_template_json": VALID_TEMPLATE,
            "judge_spec": VALID_JUDGE_SPEC,
            "published": False,
        },
    )
    assert r.status_code == 201

    r = await client.put(
        "/api/problems/upd-1",
        headers={"Authorization": f"Bearer {fresh_teacher_token}"},
        json={"title": "New title", "published": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "New title"
    assert r.json()["published"] is True

    r = await client.delete(
        "/api/problems/upd-1",
        headers={"Authorization": f"Bearer {fresh_teacher_token}"},
    )
    assert r.status_code == 204

    r = await client.get(
        "/api/problems/upd-1",
        headers={"Authorization": f"Bearer {fresh_teacher_token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_test_data_upload_sets_has_test_data(client, fresh_teacher_token):
    r = await client.post(
        "/api/problems",
        headers={"Authorization": f"Bearer {fresh_teacher_token}"},
        json={
            "slug": "td-1",
            "title": "Has test data",
            "starter_template_json": VALID_TEMPLATE,
            "judge_spec": VALID_JUDGE_SPEC,
            "published": True,
        },
    )
    assert r.status_code == 201

    fake_zip = b"PK\x03\x04fake-zip-bytes-for-test"
    r = await client.post(
        "/api/problems/td-1/test-data",
        headers={"Authorization": f"Bearer {fresh_teacher_token}"},
        files={"file": ("test.zip", fake_zip, "application/zip")},
    )
    assert r.status_code == 204, r.text

    r = await client.get(
        "/api/problems/td-1",
        headers={"Authorization": f"Bearer {fresh_teacher_token}"},
    )
    assert r.status_code == 200
    assert r.json()["has_test_data"] is True

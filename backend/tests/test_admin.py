"""Tests for the admin-only /api/admin endpoints.

These cover the four admin console responsibilities:
- stats: system overview counts
- users: list + role/active updates with self-protection and last-admin guard
- submissions: global submissions feed (admin sees all users')
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.user import User, UserRole


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


async def _promote(test_engine, email: str, *, role: UserRole, superuser: bool = False) -> int:
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        await session.execute(
            update(User)
            .where(User.email == email)
            .values(role=role, is_superuser=superuser),
        )
        await session.commit()
        # Fetch the id for return
        from sqlalchemy import select
        r = await session.execute(select(User.id).where(User.email == email))
        return int(r.scalar_one())


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient, test_engine) -> str:
    email = "admin@codefy.dev"
    await _register_and_login(client, email)
    await _promote(test_engine, email, role=UserRole.admin, superuser=True)
    # re-login so the JWT reflects current state
    r = await client.post(
        "/api/auth/jwt/login",
        data={"username": email, "password": "password123"},
    )
    return r.json()["access_token"]


@pytest_asyncio.fixture
async def student_token(client: AsyncClient) -> str:
    return await _register_and_login(client, "student@codefy.dev")


@pytest_asyncio.fixture
async def teacher_token(client: AsyncClient, test_engine) -> str:
    email = "teacher@codefy.dev"
    await _register_and_login(client, email)
    await _promote(test_engine, email, role=UserRole.teacher)
    r = await client.post(
        "/api/auth/jwt/login",
        data={"username": email, "password": "password123"},
    )
    return r.json()["access_token"]


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_student_cannot_access_admin_stats(client, student_token):
    r = await client.get(
        "/api/admin/stats",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_teacher_cannot_access_admin_users(client, teacher_token):
    r = await client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_admin_can_access_stats(client, admin_token):
    r = await client.get(
        "/api/admin/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_reports_user_role_breakdown(
    client, admin_token, teacher_token, student_token
):
    # All three fixtures are now created
    r = await client.get(
        "/api/admin/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["users_total"] >= 3
    assert body["users_by_role"]["admin"] >= 1
    assert body["users_by_role"]["teacher"] >= 1
    assert body["users_by_role"]["student"] >= 1
    assert "problems_total" in body
    assert "problems_published" in body
    assert "contests_total" in body
    assert "contests_active" in body
    assert "submissions_total" in body
    assert "submissions_last_24h" in body


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_lists_users(client, admin_token, student_token):
    r = await client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    users = r.json()
    assert isinstance(users, list)
    emails = {u["email"] for u in users}
    assert "admin@codefy.dev" in emails
    assert "student@codefy.dev" in emails
    student = next(u for u in users if u["email"] == "student@codefy.dev")
    assert student["role"] == "student"
    assert student["is_active"] is True


@pytest.mark.asyncio
async def test_admin_promotes_student_to_teacher(client, admin_token, student_token):
    r = await client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    student = next(u for u in r.json() if u["email"] == "student@codefy.dev")
    sid = student["id"]

    r = await client.patch(
        f"/api/admin/users/{sid}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "teacher"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "teacher"


@pytest.mark.asyncio
async def test_admin_deactivates_user(client, admin_token, student_token):
    r = await client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    student = next(u for u in r.json() if u["email"] == "student@codefy.dev")
    sid = student["id"]

    r = await client.patch(
        f"/api/admin/users/{sid}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": False},
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False


@pytest.mark.asyncio
async def test_admin_cannot_deactivate_self(client, admin_token):
    r = await client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    me = next(u for u in r.json() if u["email"] == "admin@codefy.dev")

    r = await client.patch(
        f"/api/admin/users/{me['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": False},
    )
    assert r.status_code == 400, r.text
    assert "self" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_cannot_demote_self_when_last_admin(client, admin_token):
    r = await client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    me = next(u for u in r.json() if u["email"] == "admin@codefy.dev")

    r = await client.patch(
        f"/api/admin/users/{me['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "student"},
    )
    assert r.status_code == 400, r.text
    detail = r.json()["detail"].lower()
    assert "last" in detail or "self" in detail


@pytest.mark.asyncio
async def test_patch_user_not_found_returns_404(client, admin_token):
    r = await client.patch(
        "/api/admin/users/99999",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "teacher"},
    )
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# Global submissions feed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_submissions_endpoint_returns_list(client, admin_token):
    r = await client.get(
        "/api/admin/submissions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)

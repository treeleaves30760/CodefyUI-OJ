# Admin Console Design

**Date**: 2026-05-17
**Status**: Draft

## Goal

Give admins a single, focused console at `/admin` that covers four
responsibilities visible from the goal statement:

1. **Problem management** — create, edit, list (including unpublished), upload
   hidden test data, toggle publish / practice-visible.
2. **Contest management** — create, edit, list, manage attached problems
   (points & order), see participant count and runtime status.
3. **User management** — list users, change role (student/teacher/admin),
   activate/deactivate, see who joined when.
4. **System status** — at-a-glance dashboard: counts (users by role, problems,
   contests, submissions), recent submissions feed, active contests.

The goal is **observability and control** for an admin running the OJ. It is
*not* an attempt to replace the per-user views (problem detail, contest
detail, submission detail), which stay where they are.

## Out of scope

- Per-user submission re-judging UI (no judge worker control surface yet).
- Editing the JSON for a starter template via a graph UI — we render the JSON
  in a `<textarea>` for v1.
- Bulk import/export of problems.
- Email verification / SSO (already noted as not implemented).

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (React)                                       │
│                                                         │
│   /admin                  AdminLayout (sidebar)         │
│     ├─ /admin             → DashboardPage (default)     │
│     ├─ /admin/problems    → ProblemsPage                │
│     │    ├─ list (incl. unpublished)                    │
│     │    └─ new / edit form (modal or inline)           │
│     ├─ /admin/contests    → ContestsPage                │
│     │    ├─ list                                        │
│     │    └─ new / edit form + problem attachments       │
│     └─ /admin/users       → UsersPage                   │
│          └─ list + role/active toggles                  │
│                                                         │
│   AdminRoute guard: requires user.role === 'admin'      │
│   or user.is_superuser                                  │
└──────────────┬──────────────────────────────────────────┘
               │ HTTP (JWT, axios)
┌──────────────▼──────────────────────────────────────────┐
│  Backend (FastAPI)                                      │
│                                                         │
│   /api/admin                                            │
│     GET    /stats                  → SystemOverview     │
│     GET    /users                  → list (paginated)   │
│     PATCH  /users/{id}             → update role/active │
│     GET    /submissions            → all submissions    │
│                                                         │
│   Existing routers (reused):                            │
│     /api/problems  (POST/PUT/DELETE already teacher+)   │
│     /api/contests  (POST/PUT/DELETE already teacher+)   │
│     /api/system/status  (existing health)               │
│                                                         │
│   Guard: require_admin (existing)                       │
└─────────────────────────────────────────────────────────┘
```

The admin frontend reuses existing problem and contest CRUD endpoints (they
are already gated by `require_teacher`, which admins satisfy). It adds a new
`/api/admin` router for the admin-only concerns (user role changes, global
stats, global submissions feed).

## Components

### Backend — new module `app/api/admin.py`

A single router. All endpoints depend on `require_admin`.

| Method | Path                  | Returns               | Notes                                       |
|--------|-----------------------|-----------------------|---------------------------------------------|
| GET    | `/stats`              | `AdminStats`          | counts + recent activity, see schema below  |
| GET    | `/users`              | `list[AdminUserRead]` | pagination via `?limit&offset`, sort by id  |
| PATCH  | `/users/{id}`         | `AdminUserRead`       | body: `role?`, `is_active?` (admin can't demote/disable themselves) |
| GET    | `/submissions`        | `list[AdminSubmissionRow]` | latest N global submissions with user+problem labels |

Self-protection rule: a request that would set the caller's own `is_active`
to false or change their own role away from admin returns 400. Last-admin
protection: refuse to demote/deactivate the last remaining admin (count
admins after applying the change; must remain ≥ 1).

#### Schemas

```python
class AdminStats(BaseModel):
    users_total: int
    users_by_role: dict[str, int]    # {"student": N, "teacher": N, "admin": N}
    problems_total: int
    problems_published: int
    contests_total: int
    contests_active: int
    submissions_total: int
    submissions_last_24h: int

class AdminUserRead(BaseModel):
    id: int
    email: str
    display_name: str
    role: UserRole
    is_active: bool
    is_superuser: bool
    created_at: datetime

class AdminUserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None

class AdminSubmissionRow(BaseModel):
    id: int
    user_id: int
    user_email: str
    problem_id: int
    problem_slug: str
    contest_id: int | None
    status: SubmissionStatus
    score: float | None
    submitted_at: datetime
```

### Frontend — new files

```
src/api/admin.ts                  ← typed client for /api/admin/*
src/auth/AdminRoute.tsx           ← role guard (extends ProtectedRoute)
src/pages/admin/AdminLayout.tsx   ← sidebar + outlet
src/pages/admin/Dashboard.tsx     ← stats widgets + recent submissions
src/pages/admin/Problems.tsx      ← list + create/edit form + test data upload
src/pages/admin/Contests.tsx      ← list + create/edit form + attached problems
src/pages/admin/Users.tsx         ← list + role/active toggles
```

`router.tsx` registers `/admin` as a `Routes` tree with `AdminLayout` and
child routes. Navbar gets an "管理員 / Admin" link visible only when
`user.role === 'admin' || user.is_superuser`.

i18n keys live under `admin.*` in both locale files.

### Visual style

The console matches the existing palette (Tailwind, `bg-surface`,
`border-border`, `text-text-muted`, `accent`). Sidebar lists the four tabs
and a "← 回首頁 / Back to app" link.

## Data flow

- Dashboard issues one `GET /api/admin/stats` and one `GET /api/admin/submissions?limit=10`.
- Problems page reuses `GET /api/problems?published_only=false` to include
  drafts; create/edit go through existing `POST/PUT /api/problems`; test-data
  upload uses the existing `POST /api/problems/{slug}/test-data`.
- Contests page reuses existing contest CRUD and the per-slug problem attach
  endpoint.
- Users page: `GET /api/admin/users`, then `PATCH /api/admin/users/{id}` on
  each role / active toggle.

## Error handling

- Server returns standard HTTPException with detail string; frontend surfaces
  it in a red banner per page.
- `require_admin` will 403 a non-admin; `AdminRoute` keeps non-admins from
  ever reaching the pages, so 403s should only happen if a session is mid-way
  through being demoted.
- Self-protection 400s ("can't deactivate yourself", "can't demote the last
  admin") are shown inline next to the offending row.

## Testing

### Backend

New `backend/tests/test_admin.py`:

- non-admin gets 403 on every `/api/admin/*` endpoint
- stats returns expected counts after seeding fixtures
- list/update users: promote student → teacher, deactivate, etc.
- self-protection: can't demote self, can't deactivate self
- last-admin protection: with one admin only, demote attempt returns 400

### Frontend

Lint + typecheck must pass (`pnpm tsc -b --noEmit && pnpm lint`). No new
unit test infra; the user-visible coverage comes from the Chrome E2E walk.

### Chrome E2E (claude-in-chrome MCP)

Walkthrough in the running stack at http://localhost:8080 :

1. Login as admin → land on `/`.
2. Navbar shows "Admin"; click it → `/admin` shows dashboard with stat cards
   and recent submissions table.
3. `/admin/problems` → list shows all (incl. unpublished). Create a new
   problem ("test-problem"), verify it appears.
4. `/admin/contests` → list. Create a new contest with the new problem
   attached, verify it appears in the list with `problem_count = 1`.
5. `/admin/users` → list shows seeded/admin users. Promote a student to
   teacher; confirm UI updates. Attempt to deactivate self → expect a
   visible error.
6. Capture screenshots / console logs at each step for the report.

## Migration / rollout

No database schema changes — all new endpoints read existing tables or write
fields that already exist on `User` (`role`, `is_active`). No alembic
migration needed.

Frontend ships with a new admin route tree behind a role guard; existing
routes are untouched.

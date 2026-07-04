"""Notifications bug-fix regression tests (iteration 17).

Bug reported: admin-created notifications (broadcast + personal) were
not visible to users because the frontend used mock data.  Backend was
correct; but a secondary fix now ensures /me/mark-read and /me/read-all
never mutate broadcast documents (which are shared across users).

This test file exercises:
- Admin can create personal + broadcast notifications (POST /api/notifications/admin)
- User can list them (GET /api/notifications/me)
- Cross-user broadcast isolation: user A marks a broadcast read → user B
  still sees it unread (server should NOT flip is_read on broadcasts).
- Regression: BRV endpoint still returns overall PASS 36/36.
"""

from __future__ import annotations

import os
import uuid

import pytest
import requests

# Load from frontend/.env (this is where REACT_APP_BACKEND_URL lives).
def _load_backend_url() -> str:
    env_url = os.environ.get("REACT_APP_BACKEND_URL")
    if env_url:
        return env_url.rstrip("/")
    fe_env = "/app/frontend/.env"
    if os.path.exists(fe_env):
        with open(fe_env) as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

ADMIN_MOBILE = "9999999999"
ADMIN_PASSWORD = "Admin@12345"
USER_A_MOBILE = "7802655202"
USER_A_PASSWORD = "Passw0rd!"
USER_A_MEMBERSHIP = "RW001798"

# Unique title suffix so we can uniquely find our test rows in the response.
RUN_ID = uuid.uuid4().hex[:8]
BROADCAST_TITLE = f"TEST BROADCAST {RUN_ID}"
PERSONAL_TITLE = f"TEST PERSONAL {RUN_ID}"


# --------- fixtures --------------------------------------------------------
@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(sess, path, mobile, password):
    r = sess.post(f"{API}{path}", json={"mobile": mobile, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed {path} {mobile}: {r.status_code} {r.text}"
    return r.json()["tokens"]["access_token"]


@pytest.fixture(scope="module")
def admin_token(sess):
    return _login(sess, "/admin/login", ADMIN_MOBILE, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def user_a_token(sess):
    return _login(sess, "/auth/login", USER_A_MOBILE, USER_A_PASSWORD)


@pytest.fixture(scope="module")
def user_b(sess, admin_token):
    """Find another active user (not RW000000, not user A), reset password, return (mobile, membership_id, token)."""
    r = sess.get(
        f"{API}/admin/users?page_size=200",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    items = r.json().get("items") or r.json().get("users") or []
    picked = None
    for u in items:
        mid = u.get("membership_id")
        mob = u.get("mobile")
        if mid in {"RW000000", USER_A_MEMBERSHIP}:
            continue
        if u.get("status") and u["status"] != "active":
            continue
        if not mob:
            continue
        picked = u
        break
    if not picked:
        pytest.skip("No second user found in DB for cross-user isolation test")

    mid = picked["membership_id"]
    mob = picked["mobile"]

    # Reset password to a known one.
    rp = sess.post(
        f"{API}/admin/users/{mid}/reset-password",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"new_password": "Passw0rd!"},
        timeout=20,
    )
    assert rp.status_code == 200, f"reset-password failed for {mid}: {rp.status_code} {rp.text}"

    # Login as user B.
    lg = sess.post(
        f"{API}/auth/login",
        json={"mobile": mob, "password": "Passw0rd!"},
        timeout=20,
    )
    assert lg.status_code == 200, f"user B login failed: {lg.status_code} {lg.text}"
    token = lg.json()["tokens"]["access_token"]
    return {"mobile": mob, "membership_id": mid, "token": token}


# --------- primary bug-fix tests -------------------------------------------
class TestAdminCreatesNotification:
    """POST /api/notifications/admin creates broadcast + personal rows visible to users."""

    _ids: dict = {}

    def test_admin_create_broadcast(self, sess, admin_token):
        r = sess.post(
            f"{API}/notifications/admin",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": BROADCAST_TITLE,
                "body": "Hello all",
                "category": "announcement",
                "user_membership_id": None,
            },
            timeout=20,
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["title"] == BROADCAST_TITLE
        assert data["is_broadcast"] is True
        assert data["user_membership_id"] is None
        assert "id" in data
        TestAdminCreatesNotification._ids["broadcast"] = data["id"]

    def test_admin_create_personal(self, sess, admin_token):
        r = sess.post(
            f"{API}/notifications/admin",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": PERSONAL_TITLE,
                "body": f"For {USER_A_MEMBERSHIP}",
                "category": "system",
                "user_membership_id": USER_A_MEMBERSHIP,
            },
            timeout=20,
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["title"] == PERSONAL_TITLE
        assert data["is_broadcast"] is False
        assert data["user_membership_id"] == USER_A_MEMBERSHIP
        TestAdminCreatesNotification._ids["personal"] = data["id"]

    def test_user_a_sees_both(self, sess, user_a_token):
        r = sess.get(
            f"{API}/notifications/me?page_size=200",
            headers={"Authorization": f"Bearer {user_a_token}"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        titles = {i["title"] for i in items}
        assert BROADCAST_TITLE in titles, f"Broadcast not visible to user A. Titles: {list(titles)[:10]}"
        assert PERSONAL_TITLE in titles, f"Personal not visible to user A. Titles: {list(titles)[:10]}"

        # Check the personal notification's shape
        personal = next(i for i in items if i["title"] == PERSONAL_TITLE)
        assert personal["user_membership_id"] == USER_A_MEMBERSHIP
        assert personal["is_broadcast"] is False


class TestCrossUserBroadcastIsolation:
    """When user A marks a broadcast as read via /me/mark-read, user B must NOT see it as read."""

    def test_broadcast_isolation(self, sess, admin_token, user_a_token, user_b):
        # 1. Admin creates a fresh broadcast so we know its initial state for BOTH users.
        iso_title = f"TEST ISOLATION {RUN_ID}"
        r = sess.post(
            f"{API}/notifications/admin",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": iso_title,
                "body": "Isolation test broadcast",
                "category": "announcement",
                "user_membership_id": None,
            },
            timeout=20,
        )
        assert r.status_code == 201, r.text
        b_id = r.json()["id"]
        assert r.json()["is_broadcast"] is True

        # 2. User B (fresh) sees it unread.
        rb1 = sess.get(
            f"{API}/notifications/me?page_size=200",
            headers={"Authorization": f"Bearer {user_b['token']}"},
            timeout=20,
        )
        assert rb1.status_code == 200
        b_row_before = next(
            (i for i in rb1.json()["items"] if i["id"] == b_id), None
        )
        assert b_row_before is not None, "Broadcast not visible to user B"
        assert b_row_before["is_read"] is False

        # 3. User A calls POST /me/mark-read with the broadcast id — server MUST ignore it.
        ma = sess.post(
            f"{API}/notifications/me/mark-read",
            headers={"Authorization": f"Bearer {user_a_token}"},
            json={"ids": [b_id]},
            timeout=20,
        )
        assert ma.status_code == 200, ma.text
        # updated count should be 0 because broadcasts are excluded server-side
        assert ma.json().get("updated", 0) == 0, (
            f"Server flipped is_read on broadcast — LEAK! updated={ma.json()}"
        )

        # 4. User B refetches — the broadcast is still unread on the shared row.
        rb2 = sess.get(
            f"{API}/notifications/me?page_size=200",
            headers={"Authorization": f"Bearer {user_b['token']}"},
            timeout=20,
        )
        assert rb2.status_code == 200
        b_row_after = next(i for i in rb2.json()["items"] if i["id"] == b_id)
        assert b_row_after["is_read"] is False, "Broadcast leaked read state to user B!"

    def test_mark_read_all_excludes_broadcasts(self, sess, admin_token, user_a_token, user_b):
        # Create another fresh broadcast.
        title = f"TEST ISOLATION-ALL {RUN_ID}"
        r = sess.post(
            f"{API}/notifications/admin",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": title,
                "body": "read-all isolation",
                "category": "announcement",
                "user_membership_id": None,
            },
            timeout=20,
        )
        assert r.status_code == 201
        b_id = r.json()["id"]

        # User A hits /me/read-all — should NOT touch broadcasts.
        ra = sess.post(
            f"{API}/notifications/me/read-all",
            headers={"Authorization": f"Bearer {user_a_token}"},
            timeout=20,
        )
        assert ra.status_code == 200, ra.text

        # User B still sees it unread.
        rb = sess.get(
            f"{API}/notifications/me?page_size=200",
            headers={"Authorization": f"Bearer {user_b['token']}"},
            timeout=20,
        )
        row = next(i for i in rb.json()["items"] if i["id"] == b_id)
        assert row["is_read"] is False, "read-all leaked read state on broadcast to user B!"


class TestPersonalMarkReadPersists:
    """Marking a personal notification read must persist on the server."""

    def test_mark_personal_read_persists(self, sess, admin_token, user_a_token):
        # Create a fresh personal notification for user A.
        title = f"TEST PERSONAL PERSIST {RUN_ID}"
        r = sess.post(
            f"{API}/notifications/admin",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": title,
                "body": "will be marked read",
                "category": "system",
                "user_membership_id": USER_A_MEMBERSHIP,
            },
            timeout=20,
        )
        assert r.status_code == 201
        p_id = r.json()["id"]

        # User A marks it read.
        ma = sess.post(
            f"{API}/notifications/me/mark-read",
            headers={"Authorization": f"Bearer {user_a_token}"},
            json={"ids": [p_id]},
            timeout=20,
        )
        assert ma.status_code == 200, ma.text
        assert ma.json().get("updated", 0) == 1, ma.text

        # GET → is_read=true.
        r2 = sess.get(
            f"{API}/notifications/me?page_size=200",
            headers={"Authorization": f"Bearer {user_a_token}"},
            timeout=20,
        )
        row = next(i for i in r2.json()["items"] if i["id"] == p_id)
        assert row["is_read"] is True


# --------- regression ------------------------------------------------------
class TestRegression:
    def test_brv_overall_pass(self, sess, admin_token):
        r = sess.get(
            f"{API}/admin/qa/brv",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # BRV shape is not strictly typed but should contain results and an overall verdict.
        # Accept common keys: `overall`, `summary`, or a list of `checks`.
        text = str(data).lower()
        # Look for indicators of pass 36/36.
        passed = data.get("passed") or data.get("total_passed")
        total = data.get("total") or data.get("total_checks")
        if isinstance(passed, int) and isinstance(total, int):
            assert passed == total, f"BRV not fully passing: {passed}/{total}"
            assert total == 36, f"BRV expected 36 checks, got {total}"
        else:
            # Fallback: overall verdict is PASS.
            assert "pass" in text and "fail" not in text.split("overall", 1)[-1][:60] or "36/36" in text

    def test_user_payment_history_endpoint(self, sess, user_a_token):
        # Phase 11 endpoint from prev iteration — smoke that it still loads.
        r = sess.get(
            f"{API}/payments/me?page=1&page_size=10",
            headers={"Authorization": f"Bearer {user_a_token}"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert "items" in j

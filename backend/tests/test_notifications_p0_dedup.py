"""P0 bug regression: admin broadcast must produce EXACTLY ONE notification per user.

Bug tracked (iter 18): user was seeing 99+ notifications when admin sent a single
broadcast. Root cause: /api/notifications/me had an $or clause that also queried
{is_broadcast: True}, returning every user's copy of every broadcast. Fix:
list_my_notifications, unread_count filter strictly by user_membership_id, since
the admin route already materialises one row per user. This suite verifies:

1. Admin sends 1 broadcast → each user sees exactly 1 new row with that title.
2. /me/unread-count is exact-per-user (not inflated).
3. Two broadcasts produce exactly two new rows (not 2*N).
4. Targeted notification only appears for target user.
5. read-all zeroes user A's unread without affecting user B.
6. mark-read on a broadcast row now succeeds (materialised per-user) and does
   NOT affect the other user's row for the same broadcast.
"""
from __future__ import annotations

import os
import random
import time
import uuid

import pytest
import requests


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
COMPANY_REFERRAL = "RW000000"

RUN_ID = uuid.uuid4().hex[:8]


# --------- helpers ---------------------------------------------------------
def _random_mobile() -> str:
    # Indian 6-9 leading digit, 10 total
    return f"{random.choice(['6', '7', '8', '9'])}{random.randint(10**8, 10**9 - 1)}"


def _register_user(sess: requests.Session, name: str) -> dict:
    """Register a fresh test user via OTP-register flow. Returns {mobile, membership_id, token}."""
    mobile = _random_mobile()
    # Loop to avoid mobile collision
    for _ in range(5):
        r_send = sess.post(f"{API}/auth/send-otp", json={"mobile": mobile, "purpose": "register"}, timeout=20)
        if r_send.status_code == 409:
            mobile = _random_mobile()
            continue
        assert r_send.status_code == 200, f"send-otp failed: {r_send.status_code} {r_send.text}"
        break
    else:
        pytest.skip("Could not send OTP for any random mobile")

    r_verify = sess.post(
        f"{API}/auth/verify-otp",
        json={"mobile": mobile, "purpose": "register", "code": "123456"},
        timeout=20,
    )
    assert r_verify.status_code == 200, f"verify-otp failed: {r_verify.status_code} {r_verify.text}"

    r_reg = sess.post(
        f"{API}/auth/register",
        json={
            "full_name": name,
            "mobile": mobile,
            "state": "Karnataka",
            "city": "Bangalore",
            "referral_id": COMPANY_REFERRAL,
            "password": "Passw0rd!",
            "confirm_password": "Passw0rd!",
        },
        timeout=20,
    )
    assert r_reg.status_code == 200, f"register failed: {r_reg.status_code} {r_reg.text}"
    j = r_reg.json()
    return {
        "mobile": mobile,
        "membership_id": j["user"]["membership_id"],
        "token": j["tokens"]["access_token"],
    }


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(sess, path, mobile, password):
    r = sess.post(f"{API}{path}", json={"mobile": mobile, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed {path} {mobile}: {r.status_code} {r.text}"
    return r.json()["tokens"]["access_token"]


# --------- fixtures --------------------------------------------------------
@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(sess):
    return _login(sess, "/admin/login", ADMIN_MOBILE, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def users(sess):
    """Register 3 fresh users so the dedup bug (if present) would be visible."""
    return [
        _register_user(sess, f"TEST User A {RUN_ID}"),
        _register_user(sess, f"TEST User B {RUN_ID}"),
        _register_user(sess, f"TEST User C {RUN_ID}"),
    ]


def _titles_for(sess, token: str) -> list[str]:
    r = sess.get(f"{API}/notifications/me?page_size=200", headers=_auth(token), timeout=20)
    assert r.status_code == 200, r.text
    return [i["title"] for i in r.json()["items"]]


def _find_rows(sess, token: str, title: str) -> list[dict]:
    r = sess.get(f"{API}/notifications/me?page_size=200", headers=_auth(token), timeout=20)
    assert r.status_code == 200, r.text
    return [i for i in r.json()["items"] if i["title"] == title]


def _unread_count(sess, token: str) -> int:
    r = sess.get(f"{API}/notifications/me/unread-count", headers=_auth(token), timeout=20)
    assert r.status_code == 200, r.text
    return int(r.json()["unread"])


# --------- BUG-FIX TESTS ---------------------------------------------------
class TestBroadcastNoDuplication:
    """The P0: one admin broadcast → exactly one notification per user, not N."""

    def test_health(self, sess):
        r = sess.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "healthy"

    def test_single_broadcast_produces_exactly_one_row_per_user(self, sess, admin_token, users):
        title = f"P0 BROADCAST {RUN_ID}"

        # Baseline: what does each user see today?
        pre_counts = [len(_find_rows(sess, u["token"], title)) for u in users]
        assert all(c == 0 for c in pre_counts), f"Pre-broadcast rows must be 0, got {pre_counts}"

        # Admin sends ONE broadcast.
        r = sess.post(
            f"{API}/admin/notifications",
            headers=_auth(admin_token),
            json={
                "title": title,
                "body": "single broadcast p0 fix",
                "category": "announcement",
                "is_broadcast": True,
            },
            timeout=30,
        )
        assert r.status_code == 201, r.text
        payload = r.json()
        # Should have delivered to all active users; at minimum 3 (our test users).
        assert payload["delivered_count"] >= 3, f"delivered_count={payload['delivered_count']}"

        # Give the DB a moment to settle.
        time.sleep(0.5)

        # THE BUG: each user should see EXACTLY 1 row with this title (not N).
        for u in users:
            rows = _find_rows(sess, u["token"], title)
            assert len(rows) == 1, (
                f"User {u['membership_id']} sees {len(rows)} rows for a single broadcast — "
                f"P0 DUPLICATION BUG! Expected 1."
            )
            row = rows[0]
            assert row["is_read"] is False
            assert row["user_membership_id"] == u["membership_id"]
            assert row["is_broadcast"] is True

    def test_unread_count_is_exact(self, sess, admin_token, users):
        """/me/unread-count for user A must reflect only user A's rows (not N-times inflated)."""
        title = f"P0 UNREAD {RUN_ID}"
        # snapshot user A unread before
        before_a = _unread_count(sess, users[0]["token"])
        before_b = _unread_count(sess, users[1]["token"])

        r = sess.post(
            f"{API}/admin/notifications",
            headers=_auth(admin_token),
            json={"title": title, "body": "x", "category": "announcement", "is_broadcast": True},
            timeout=30,
        )
        assert r.status_code == 201, r.text
        time.sleep(0.5)

        after_a = _unread_count(sess, users[0]["token"])
        after_b = _unread_count(sess, users[1]["token"])
        assert after_a - before_a == 1, (
            f"Unread went from {before_a} → {after_a} after 1 broadcast — should be +1 exactly."
        )
        assert after_b - before_b == 1, (
            f"Unread went from {before_b} → {after_b} for user B — should be +1 exactly."
        )

    def test_two_broadcasts_produce_two_rows(self, sess, admin_token, users):
        t1 = f"P0 TWO-A {RUN_ID}"
        t2 = f"P0 TWO-B {RUN_ID}"
        for title in (t1, t2):
            r = sess.post(
                f"{API}/admin/notifications",
                headers=_auth(admin_token),
                json={"title": title, "body": "x", "category": "announcement", "is_broadcast": True},
                timeout=30,
            )
            assert r.status_code == 201, r.text
        time.sleep(0.5)

        for u in users:
            titles = _titles_for(sess, u["token"])
            assert titles.count(t1) == 1, f"user {u['membership_id']}: t1 appeared {titles.count(t1)}x"
            assert titles.count(t2) == 1, f"user {u['membership_id']}: t2 appeared {titles.count(t2)}x"


class TestTargetedNotification:
    def test_targeted_only_for_target(self, sess, admin_token, users):
        title = f"P0 TARGET {RUN_ID}"
        target = users[0]
        other = users[1]

        r = sess.post(
            f"{API}/admin/notifications",
            headers=_auth(admin_token),
            json={
                "title": title,
                "body": "only for target",
                "category": "system",
                "is_broadcast": False,
                "target_membership_ids": [target["membership_id"]],
            },
            timeout=20,
        )
        assert r.status_code == 201, r.text
        assert r.json()["delivered_count"] == 1
        time.sleep(0.3)

        target_rows = _find_rows(sess, target["token"], title)
        other_rows = _find_rows(sess, other["token"], title)
        assert len(target_rows) == 1
        assert target_rows[0]["is_broadcast"] is False
        assert target_rows[0]["user_membership_id"] == target["membership_id"]
        assert len(other_rows) == 0, "Targeted notification LEAKED to another user"


class TestReadStateIsolation:
    def test_read_all_isolates_users(self, sess, admin_token, users):
        title = f"P0 READALL {RUN_ID}"
        r = sess.post(
            f"{API}/admin/notifications",
            headers=_auth(admin_token),
            json={"title": title, "body": "x", "category": "announcement", "is_broadcast": True},
            timeout=30,
        )
        assert r.status_code == 201, r.text
        time.sleep(0.3)

        a, b = users[0], users[1]
        b_unread_before = _unread_count(sess, b["token"])

        # User A: read-all
        ra = sess.post(f"{API}/notifications/me/read-all", headers=_auth(a["token"]), timeout=20)
        assert ra.status_code == 200
        assert ra.json()["success"] is True

        # Verify user A unread == 0
        assert _unread_count(sess, a["token"]) == 0

        # Verify user B unread unaffected (broadcast for B is still unread)
        b_unread_after = _unread_count(sess, b["token"])
        assert b_unread_after == b_unread_before, (
            f"User B unread changed from {b_unread_before} → {b_unread_after} after A hit /me/read-all — LEAK"
        )
        # And row for user B is still unread=false
        b_rows = _find_rows(sess, b["token"], title)
        assert len(b_rows) == 1 and b_rows[0]["is_read"] is False

    def test_mark_read_broadcast_only_affects_owner(self, sess, admin_token, users):
        title = f"P0 MARKREAD {RUN_ID}"
        r = sess.post(
            f"{API}/admin/notifications",
            headers=_auth(admin_token),
            json={"title": title, "body": "x", "category": "announcement", "is_broadcast": True},
            timeout=30,
        )
        assert r.status_code == 201, r.text
        time.sleep(0.3)

        c, b = users[2], users[1]
        c_rows = _find_rows(sess, c["token"], title)
        b_rows = _find_rows(sess, b["token"], title)
        assert len(c_rows) == 1
        assert len(b_rows) == 1
        assert c_rows[0]["id"] != b_rows[0]["id"], "user C and user B share the SAME broadcast row — bug!"

        # User C marks read using C's own broadcast row id.
        mr = sess.post(
            f"{API}/notifications/me/mark-read",
            headers=_auth(c["token"]),
            json={"ids": [c_rows[0]["id"]]},
            timeout=20,
        )
        assert mr.status_code == 200, mr.text
        assert mr.json().get("updated") == 1, f"Expected 1 row updated for own broadcast row; got {mr.json()}"

        # C row now is_read=true; B row untouched.
        c_rows2 = _find_rows(sess, c["token"], title)
        assert c_rows2[0]["is_read"] is True

        b_rows2 = _find_rows(sess, b["token"], title)
        assert b_rows2[0]["is_read"] is False, "User B broadcast row leaked read state from user C!"

    def test_user_a_cannot_mark_other_users_row(self, sess, users):
        """Sanity: /me/mark-read scopes by user_membership_id. Passing another user's row id → 0 updated."""
        a, b = users[0], users[1]
        # Grab any B notification id (need at least one). Send a fresh personal to B if none.
        b_list = sess.get(f"{API}/notifications/me?page_size=1", headers=_auth(b["token"]), timeout=20).json()
        if not b_list["items"]:
            pytest.skip("User B has no notifications to test cross-user mark-read")
        b_id = b_list["items"][0]["id"]

        mr = sess.post(
            f"{API}/notifications/me/mark-read",
            headers=_auth(a["token"]),
            json={"ids": [b_id]},
            timeout=20,
        )
        assert mr.status_code == 200
        assert mr.json().get("updated") == 0, (
            "User A managed to mark another user's row read — auth-scoping BROKEN"
        )

"""P0 – Module Player bug fix regression tests.

Scenario: user with an active purchase must be able to open
GET /api/programs/{program_id}    AND
GET /api/modules/{module_id}
and get back the real admin-uploaded media URLs (video / audio / pdf) so the
frontend `ModulePlayer` page renders content instead of the old
"no module found" error.

Also validates: (a) module.program_id round-trips correctly, (b) modules with
no media still return 200, (c) `/modules/me/by-program/{id}` correctly marks
module 1 as unlocked and module 2 as locked (sequential-unlock guard).
"""

from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_MOBILE = "9999999999"
ADMIN_PASSWORD = "Admin@12345"
DEV_OTP = "123456"
REFERRAL_ROOT = "RW000000"

VIDEO_URL = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
AUDIO_URL = "https://file-examples.com/storage/fe/audio.mp3"
PDF_URL = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"


# --------------------------- fixtures ------------------------------------
@pytest.fixture(scope="module")
def admin_token() -> str:
    r = requests.post(
        f"{API}/admin/login",
        json={"mobile": ADMIN_MOBILE, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()["tokens"]["access_token"]


@pytest.fixture(scope="module")
def admin_h(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def user_ctx(admin_h: dict) -> dict:
    """Registers a fresh user, returns {mobile, membership_id, token, h}."""
    mobile = "9" + str(uuid.uuid4().int)[:9]
    # send OTP + verify + register
    r = requests.post(f"{API}/auth/send-otp", json={"mobile": mobile, "purpose": "register"}, timeout=15)
    assert r.status_code == 200, r.text
    r = requests.post(
        f"{API}/auth/verify-otp",
        json={"mobile": mobile, "purpose": "register", "code": DEV_OTP},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    r = requests.post(
        f"{API}/auth/register",
        json={
            "mobile": mobile,
            "full_name": "TEST_ModulePlayer User",
            "state": "MH",
            "city": "Pune",
            "referral_id": REFERRAL_ROOT,
            "password": "Passw0rd!",
            "confirm_password": "Passw0rd!",
            "otp_code": DEV_OTP,
        },
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    tokens = body.get("tokens") or body.get("token") or {}
    token = tokens.get("access_token") if isinstance(tokens, dict) else tokens
    if not token:
        # try explicit login as fallback
        r = requests.post(f"{API}/auth/login", json={"mobile": mobile, "password": "Passw0rd!"}, timeout=15)
        assert r.status_code == 200, r.text
        token = r.json()["tokens"]["access_token"]
    # profile → membership id
    r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert r.status_code == 200, r.text
    me = r.json()
    membership_id = me.get("membership_id") or me.get("user", {}).get("membership_id")
    assert membership_id, me
    return {
        "mobile": mobile,
        "membership_id": membership_id,
        "token": token,
        "h": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    }


@pytest.fixture(scope="module")
def program_ctx(admin_h: dict) -> dict:
    """Creates a fresh program + 4 modules (video / audio / pdf / empty).

    Yields dict of ids and cleans up (soft delete) at teardown.
    """
    slug = f"test-modplayer-{uuid.uuid4().hex[:8]}"
    r = requests.post(
        f"{API}/programs/admin",
        json={
            "name": f"TEST_ModulePlayer {slug}",
            "slug": slug,
            "price": 999,
            "validity_days": 30,
            "gst_percent": 18,
            "description": "regression program",
        },
        headers=admin_h,
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text
    program = r.json()
    pid = program["id"]

    modules: dict[str, str] = {}
    for i, (key, extra) in enumerate(
        [
            ("video", {"video_url": VIDEO_URL}),
            ("audio", {"audio_url": AUDIO_URL}),
            ("pdf", {"pdf_url": PDF_URL}),
            ("empty", {}),
        ],
        start=1,
    ):
        payload = {
            "program_id": pid,
            "module_number": i,
            "name": f"TEST_Mod_{key}",
            "description": f"regression module {key}",
            "order_index": i,
            **extra,
        }
        r = requests.post(f"{API}/modules/admin", json=payload, headers=admin_h, timeout=15)
        assert r.status_code in (200, 201), f"module {key}: {r.text}"
        modules[key] = r.json()["id"]

    yield {"program_id": pid, "modules": modules}

    # teardown
    for mid in modules.values():
        requests.delete(f"{API}/modules/admin/{mid}", headers=admin_h, timeout=10)
    requests.delete(f"{API}/programs/admin/{pid}", headers=admin_h, timeout=10)


@pytest.fixture(scope="module")
def purchase_ctx(admin_h: dict, user_ctx: dict, program_ctx: dict) -> dict:
    """Grants the fresh user access to the fresh program (30d)."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=30)
    inv = f"TEST-INV-{uuid.uuid4().hex[:10].upper()}"
    r = requests.post(
        f"{API}/purchases/admin",
        json={
            "user_membership_id": user_ctx["membership_id"],
            "program_id": program_ctx["program_id"],
            "price_paid": 999,
            "discount": 0,
            "gst_amount": 180,
            "total": 1179,
            "invoice_number": inv,
            "purchase_date": now.isoformat(),
            "expiry_date": exp.isoformat(),
            "status": "active",
        },
        headers=admin_h,
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text
    purchase = r.json()
    yield purchase
    requests.delete(f"{API}/purchases/admin/{purchase['id']}", headers=admin_h, timeout=10)


# ---------------------------- tests --------------------------------------


class TestModulePlayerP0:
    """Real bug repro: user opens /app/programs/:id/module/:moduleId."""

    def test_program_get_returns_program(self, user_ctx, program_ctx, purchase_ctx):
        r = requests.get(
            f"{API}/programs/{program_ctx['program_id']}",
            headers={"Authorization": f"Bearer {user_ctx['token']}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["id"] == program_ctx["program_id"]
        assert p.get("name", "").startswith("TEST_ModulePlayer")

    def test_video_module_returns_url(self, user_ctx, program_ctx, purchase_ctx):
        mid = program_ctx["modules"]["video"]
        r = requests.get(
            f"{API}/modules/{mid}",
            headers={"Authorization": f"Bearer {user_ctx['token']}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        m = r.json()
        assert m["id"] == mid
        assert m["program_id"] == program_ctx["program_id"]
        assert m.get("video_url") == VIDEO_URL
        # Only video (no audio / pdf)
        assert not m.get("audio_url")
        assert not m.get("pdf_url")

    def test_audio_module_returns_url(self, user_ctx, program_ctx, purchase_ctx):
        mid = program_ctx["modules"]["audio"]
        r = requests.get(
            f"{API}/modules/{mid}",
            headers={"Authorization": f"Bearer {user_ctx['token']}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        m = r.json()
        assert m["program_id"] == program_ctx["program_id"]
        assert m.get("audio_url") == AUDIO_URL
        assert not m.get("video_url")
        assert not m.get("pdf_url")

    def test_pdf_module_returns_url(self, user_ctx, program_ctx, purchase_ctx):
        mid = program_ctx["modules"]["pdf"]
        r = requests.get(
            f"{API}/modules/{mid}",
            headers={"Authorization": f"Bearer {user_ctx['token']}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        m = r.json()
        assert m["program_id"] == program_ctx["program_id"]
        assert m.get("pdf_url") == PDF_URL
        assert not m.get("video_url")
        assert not m.get("audio_url")

    def test_empty_module_still_200(self, user_ctx, program_ctx, purchase_ctx):
        mid = program_ctx["modules"]["empty"]
        r = requests.get(
            f"{API}/modules/{mid}",
            headers={"Authorization": f"Bearer {user_ctx['token']}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        m = r.json()
        assert not m.get("video_url")
        assert not m.get("audio_url")
        assert not m.get("pdf_url")

    def test_module_not_found_returns_404(self, user_ctx):
        r = requests.get(
            f"{API}/modules/does-not-exist-{uuid.uuid4().hex}",
            headers={"Authorization": f"Bearer {user_ctx['token']}"},
            timeout=15,
        )
        assert r.status_code == 404

    def test_get_module_unauthenticated_rejected(self, program_ctx):
        mid = program_ctx["modules"]["video"]
        r = requests.get(f"{API}/modules/{mid}", timeout=15)
        assert r.status_code in (401, 403)


class TestSequentialUnlockGuard:
    """Regression: /modules/me/by-program/{id} → module1 unlocked, module2 locked."""

    def test_by_program_shows_unlock_flags(self, user_ctx, program_ctx, purchase_ctx):
        r = requests.get(
            f"{API}/modules/me/by-program/{program_ctx['program_id']}",
            headers={"Authorization": f"Bearer {user_ctx['token']}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["has_access"] is True
        modules = body["modules"]
        assert len(modules) >= 4
        # Sort by module_number to be safe
        modules.sort(key=lambda m: m["module_number"])
        # Module 1 must be unlocked (first module, has_access true)
        assert modules[0]["is_unlocked"] is True, modules[0]
        # Module 2 must be locked (sequential-unlock, module1 not completed)
        assert modules[1]["is_unlocked"] is False, modules[1]
        # Raw video/audio/pdf urls should NOT leak from this enriched endpoint
        for m in modules:
            assert "video_url" not in m
            assert "audio_url" not in m
            assert "pdf_url" not in m
            assert "has_video" in m
            assert "has_audio" in m
            assert "has_pdf" in m

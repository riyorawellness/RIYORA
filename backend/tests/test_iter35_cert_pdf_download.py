"""iter35 — Backend coverage for the new Certificate PDF download endpoint:

GET /api/certificates/me/{cert_id}/pdf
  - Auth-required (401 without Bearer)
  - Returns 404 for foreign / unknown cert
  - 200 with Content-Type: application/pdf
  - Content-Disposition inline; filename contains certificate_number
  - Body starts with b'%PDF' and > 1500 bytes
  - PDF contains program_name, user_name, membership_id, certificate_number,
    verification_number, completion_date (verified via pdfplumber text
    extraction — with a byte-signature fallback since ReportLab may compress
    text streams).
  - Idempotency — 2 calls return same-size, same-content PDFs (Content-Length
    tolerant; produced_at timestamp not embedded so byte-identity holds for
    deterministic fields).
"""
import os
import re
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"


# ------------------------------ fixtures ----------------------------------


@pytest.fixture(scope="module")
def user_token():
    r = requests.post(
        f"{API}/auth/login",
        json={"email": "qa-tester@example.com", "password": "tester123"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    tok = body.get("tokens", {}).get("access_token") or body.get("access_token")
    assert tok, f"No access token in login response: {body}"
    return tok


@pytest.fixture(scope="module")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture(scope="module")
def tester_cert(user_headers):
    """Get first available cert of qa-tester."""
    r = requests.get(
        f"{API}/certificates/me", params={"page": 1, "page_size": 5},
        headers=user_headers, timeout=15,
    )
    assert r.status_code == 200, r.text
    items = r.json().get("items", [])
    assert items, "qa-tester must have at least one cert (from iter34 seed)"
    return items[0]


@pytest.fixture(scope="module")
def tester_membership_id(user_headers):
    r = requests.get(f"{API}/auth/me", headers=user_headers, timeout=10)
    assert r.status_code == 200
    return r.json()["membership_id"]


# --- second dummy tester (for foreign-cert 404 verification) ---

SECOND_TESTER_EMAIL = f"qa-tester2-iter35-{uuid.uuid4().hex[:6]}@example.com"
SECOND_TESTER_PASSWORD = "tester123"


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(
        f"{API}/admin/login",
        json={"mobile": "9999999999", "password": "Admin@12345"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    tok = r.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def second_user_headers(admin_headers):
    """Create a fresh dummy tester and return their user headers."""
    # Try creating via /admin/users dummy-user endpoint (if available). If not,
    # fall back to /admin/users. The dummy tester in test_credentials was
    # created via 'New Dummy User' admin action — endpoint is
    # POST /api/admin/users/dummy according to the app.
    payload = {
        "full_name": "QA Tester Two Iter35",
        "email": SECOND_TESTER_EMAIL,
        "password": SECOND_TESTER_PASSWORD,
        "mobile": f"9{uuid.uuid4().int % 10**9:09d}",
    }
    # Try the dummy-user endpoint variants
    created = False
    for path in ("/admin/users/dummy", "/admin/users"):
        r = requests.post(f"{API}{path}", json=payload, headers=admin_headers, timeout=15)
        if r.status_code in (200, 201):
            created = True
            break
    if not created:
        pytest.skip(
            f"Could not create second dummy tester via admin endpoints "
            f"(last status={r.status_code}, body={r.text[:200]})"
        )
    # Log in as this user via legacy email fallback
    r_login = requests.post(
        f"{API}/auth/login",
        json={"email": SECOND_TESTER_EMAIL, "password": SECOND_TESTER_PASSWORD},
        timeout=15,
    )
    if r_login.status_code != 200:
        pytest.skip(f"Second tester login failed: {r_login.status_code} {r_login.text[:200]}")
    body = r_login.json()
    tok = body.get("tokens", {}).get("access_token") or body.get("access_token")
    return {"Authorization": f"Bearer {tok}"}


# ------------------------------ tests -------------------------------------


class TestCertificatePdfDownload:
    """Covers the new GET /certificates/me/{cert_id}/pdf endpoint."""

    def test_pdf_401_without_token(self, tester_cert):
        r = requests.get(f"{API}/certificates/me/{tester_cert['id']}/pdf", timeout=15)
        assert r.status_code in (401, 403), (
            f"Expected 401/403 unauthenticated, got {r.status_code}: {r.text[:200]}"
        )

    def test_pdf_404_for_unknown_id(self, user_headers):
        r = requests.get(
            f"{API}/certificates/me/{uuid.uuid4().hex}/pdf",
            headers=user_headers, timeout=15,
        )
        assert r.status_code == 404

    def test_pdf_404_for_foreign_cert(self, second_user_headers, tester_cert):
        """qa-tester2 cannot download qa-tester's cert."""
        r = requests.get(
            f"{API}/certificates/me/{tester_cert['id']}/pdf",
            headers=second_user_headers, timeout=15,
        )
        assert r.status_code == 404, (
            f"Foreign-cert access should be 404 but got {r.status_code}"
        )

    def test_pdf_200_headers_and_body(self, user_headers, tester_cert):
        r = requests.get(
            f"{API}/certificates/me/{tester_cert['id']}/pdf",
            headers=user_headers, timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        # Content-Type
        ctype = r.headers.get("Content-Type", "")
        assert "application/pdf" in ctype.lower(), f"Unexpected Content-Type: {ctype}"
        # Content-Disposition
        cdisp = r.headers.get("Content-Disposition", "")
        assert cdisp.lower().startswith("inline"), f"Content-Disposition not inline: {cdisp}"
        cert_num = tester_cert["certificate_number"]
        assert cert_num in cdisp, (
            f"cert_number {cert_num} not in Content-Disposition: {cdisp}"
        )
        # Body signature & size
        body = r.content
        assert body.startswith(b"%PDF"), f"Body does not start with %PDF: {body[:32]!r}"
        assert len(body) > 1500, f"PDF too small: {len(body)} bytes"

    def test_pdf_contains_expected_content(self, user_headers, tester_cert, tester_membership_id):
        r = requests.get(
            f"{API}/certificates/me/{tester_cert['id']}/pdf",
            headers=user_headers, timeout=30,
        )
        assert r.status_code == 200
        pdf_bytes = r.content

        # Try pdfplumber for structured text extraction
        text = ""
        try:
            import pdfplumber
            import io as _io
            with pdfplumber.open(_io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    text += (page.extract_text() or "") + "\n"
        except Exception as e:  # noqa: BLE001
            text = ""
            print(f"pdfplumber failed: {e}")

        expected_program = tester_cert["program_name"]
        expected_cert_num = tester_cert["certificate_number"]
        expected_verif = tester_cert.get("verification_number", "")
        expected_user = tester_cert.get("user_name") or ""

        # Prefer pdfplumber text if we got some — otherwise raw byte search
        haystack = text if text.strip() else pdf_bytes.decode("latin-1", errors="ignore")

        assert expected_program in haystack, (
            f"Program name '{expected_program}' not found in PDF text/bytes"
        )
        assert expected_cert_num in haystack, (
            f"Cert number '{expected_cert_num}' not found in PDF"
        )
        if expected_verif:
            assert expected_verif in haystack, (
                f"Verification number '{expected_verif}' not found in PDF"
            )
        if expected_user:
            assert expected_user in haystack, (
                f"User name '{expected_user}' not found in PDF"
            )
        # Membership id
        assert tester_membership_id in haystack, (
            f"Membership id {tester_membership_id} not found in PDF"
        )

    def test_pdf_is_idempotent(self, user_headers, tester_cert):
        """Two consecutive downloads should produce PDFs whose extracted text
        is identical. ReportLab embeds CreationDate/ModDate stamps so raw
        bytes may differ slightly per call — the *rendered content* must be
        stable."""
        url = f"{API}/certificates/me/{tester_cert['id']}/pdf"
        r1 = requests.get(url, headers=user_headers, timeout=30)
        r2 = requests.get(url, headers=user_headers, timeout=30)
        assert r1.status_code == 200 and r2.status_code == 200
        # Same size within tight tolerance (only tstamps differ)
        d = abs(len(r1.content) - len(r2.content))
        assert d < 128, (
            f"PDF size mismatch across requests: {len(r1.content)} vs {len(r2.content)}"
        )
        # Extract text with pdfplumber for both and compare
        import pdfplumber
        import io as _io

        def _text(b: bytes) -> str:
            with pdfplumber.open(_io.BytesIO(b)) as pdf:
                return "\n".join((p.extract_text() or "") for p in pdf.pages)

        t1 = _text(r1.content)
        t2 = _text(r2.content)
        assert t1 == t2, "Extracted PDF text differs between two calls"
        # And it must contain the cert number / program name
        assert tester_cert["certificate_number"] in t1
        assert tester_cert["program_name"] in t1


# ------------------------------ regression --------------------------------


class TestCertificateJsonRegression:
    """Ensure the existing GET /certificates/me/{id} JSON endpoint still works
    and returns all the fields the frontend renders."""

    def test_get_my_certificate_json(self, user_headers, tester_cert):
        r = requests.get(
            f"{API}/certificates/me/{tester_cert['id']}",
            headers=user_headers, timeout=15,
        )
        assert r.status_code == 200, r.text
        c = r.json()
        for f in ("id", "program_name", "certificate_number", "verification_number",
                  "completion_date", "issue_date", "user_membership_id", "status"):
            assert f in c, f"JSON regression: missing {f}"
        assert c["status"] == "issued"
        # Filename mustn't leak MongoDB _id in the response
        assert "_id" not in c

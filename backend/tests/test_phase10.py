"""Phase 10 — Legal & Support CMS pages + public system info + admin edit + regression."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_MOBILE = "9999999999"
ADMIN_PASSWORD = "Admin@12345"


# ------------------ Fixtures ------------------

@pytest.fixture(scope="session")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(api_client):
    r = api_client.post(f"{API}/admin/login", json={"mobile": ADMIN_MOBILE, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    data = r.json()
    tok = data.get("tokens", {}).get("access_token") or data.get("access_token")
    assert tok, f"No token in admin login response: {data}"
    return tok


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Content-Type": "application/json", "Authorization": f"Bearer {admin_token}"}


# ------------------ Public CMS GET tests ------------------

class TestPublicCMSPages:

    def test_privacy_page(self, api_client):
        r = api_client.get(f"{API}/cms/pages/privacy")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("title") == "Privacy Policy"
        assert data.get("is_published") is True
        assert len(data.get("body", "")) > 1000, f"privacy body too short: {len(data.get('body', ''))}"

    def test_terms_page(self, api_client):
        r = api_client.get(f"{API}/cms/pages/terms")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("title") == "Terms of Service"
        body = data.get("body", "")
        assert ("3-level referral" in body) or ("Membership ID" in body), \
            f"terms body missing required keywords: {body[:200]}"

    def test_data_security_page(self, api_client):
        r = api_client.get(f"{API}/cms/pages/data-security")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("title") == "Data & Security"
        assert len(data.get("body", "").strip()) > 0

    def test_faq_page(self, api_client):
        r = api_client.get(f"{API}/cms/pages/faq")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("title") == "Help & FAQ"
        assert len(data.get("body", "").strip()) > 0

    def test_contact_page(self, api_client):
        r = api_client.get(f"{API}/cms/pages/contact")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "info@riyorawellness.com" in data.get("body", "")


# ------------------ Public system settings ------------------

class TestPublicSystemSettings:

    def test_system_public(self, api_client):
        r = api_client.get(f"{API}/system/public")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("support_email") == "info@riyorawellness.com"
        assert data.get("application_version") == "1.0.0"
        assert data.get("company_name") == "RIYORA Wellness"

    def test_system_public_no_auth_needed(self, api_client):
        # confirm no auth is enforced
        s = requests.Session()
        r = s.get(f"{API}/system/public")
        assert r.status_code == 200


# ------------------ Admin CMS edit + revert ------------------

class TestAdminCMSEdit:

    def test_admin_can_edit_and_revert_privacy(self, api_client, admin_headers):
        # capture original
        orig = api_client.get(f"{API}/cms/pages/privacy").json()
        original_body = orig["body"]
        original_title = orig["title"]
        original_desc = orig.get("meta_description")
        original_pub = orig.get("is_published", True)

        # edit
        edit_body = "Test edit " + "x" * 5
        r = api_client.put(
            f"{API}/admin/cms/pages/privacy",
            headers=admin_headers,
            json={"title": "Privacy Policy", "body": edit_body, "is_published": True},
        )
        assert r.status_code == 200, r.text
        updated = r.json()
        assert updated.get("body") == edit_body

        # verify public reflects immediately (no cache)
        r2 = api_client.get(f"{API}/cms/pages/privacy")
        assert r2.status_code == 200
        assert r2.json().get("body") == edit_body

        # revert
        r3 = api_client.put(
            f"{API}/admin/cms/pages/privacy",
            headers=admin_headers,
            json={
                "title": original_title,
                "body": original_body,
                "is_published": original_pub,
                "meta_description": original_desc,
            },
        )
        assert r3.status_code == 200
        assert r3.json().get("body") == original_body

        # confirm reverted
        r4 = api_client.get(f"{API}/cms/pages/privacy")
        assert r4.json().get("body") == original_body

    def test_admin_can_edit_application_version(self, api_client, admin_headers):
        # edit
        r = api_client.put(
            f"{API}/admin/system/settings",
            headers=admin_headers,
            json={"application_version": "1.0.1"},
        )
        assert r.status_code == 200, r.text

        # verify public reflects
        r2 = api_client.get(f"{API}/system/public")
        assert r2.json().get("application_version") == "1.0.1"

        # revert
        r3 = api_client.put(
            f"{API}/admin/system/settings",
            headers=admin_headers,
            json={"application_version": "1.0.0"},
        )
        assert r3.status_code == 200
        r4 = api_client.get(f"{API}/system/public")
        assert r4.json().get("application_version") == "1.0.0"

    def test_admin_list_pages_includes_all_slugs(self, api_client, admin_headers):
        r = api_client.get(f"{API}/admin/cms/pages", headers=admin_headers)
        assert r.status_code == 200
        items = r.json().get("items", [])
        slugs = {i.get("slug") for i in items}
        required = {"about", "privacy", "terms", "refund", "contact", "faq", "support", "data-security"}
        missing = required - slugs
        assert not missing, f"Admin CMS list missing slugs: {missing}. Got: {slugs}"


# ------------------ Regression ------------------

class TestRegression:

    def test_brv_still_pass(self, api_client, admin_headers):
        r = api_client.get(f"{API}/admin/qa/brv", headers=admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("overall") == "PASS", f"BRV verdict: {data.get('overall')}"
        rules = data.get("rules", [])
        # accept either 'rules' or 'summary' shape
        total = data.get("total") or len(rules)
        passed = data.get("passed") or sum(1 for x in rules if x.get("status") == "PASS")
        assert passed == 36 or (passed == total and total >= 36), \
            f"Expected 36/36 rules PASS, got {passed}/{total}"

    def test_admin_login_still_works(self, api_client):
        r = api_client.post(f"{API}/admin/login", json={"mobile": ADMIN_MOBILE, "password": ADMIN_PASSWORD})
        assert r.status_code == 200

"""Doc → response DTO helpers. Never leak _id or password_hash."""


def user_to_public(doc: dict) -> dict:
    return {
        "id": str(doc.get("_id")),
        "full_name": doc["full_name"],
        "mobile": doc["mobile"],
        "state": doc.get("state") or "",
        "district": doc.get("district") or "",
        "city": doc.get("city") or "",
        "pincode": doc.get("pincode") or "",
        "role": doc.get("role", "user"),
        "membership_id": doc["membership_id"],
        "referral_id": doc["membership_id"],  # own referral id == own membership id
        "sponsor_membership_id": doc["sponsor_membership_id"],
        "sponsor_name": doc.get("sponsor_name"),
        "is_active": doc.get("is_active", True),
        "is_dummy": bool(doc.get("is_dummy", False)),
        "firebase_uid": doc.get("firebase_uid"),
        "email": doc.get("email"),
        "email_verified": bool(doc.get("email_verified", False)),
        "login_method": doc.get("login_method"),
        "photo_url": doc.get("photo_url"),
        "last_login_at": doc.get("last_login_at"),
        "created_at": doc["created_at"],
        "updated_at": doc["updated_at"],
        # Editable extended profile — surfaced so the /auth/me response feeds
        # the profile edit screen without a second round-trip.
        "dob": doc.get("dob"),
        "gender": doc.get("gender"),
        "address": doc.get("address"),
        "profession": doc.get("profession"),
        "blood_group": doc.get("blood_group"),
        "emergency_contact": doc.get("emergency_contact"),
        "name_pronunciation": doc.get("name_pronunciation"),
        "about_me": doc.get("about_me"),
        "joining_date": doc.get("joining_date") or doc.get("created_at"),
    }


def admin_to_public(doc: dict) -> dict:
    return {
        "id": str(doc.get("_id")),
        "name": doc["name"],
        "mobile": doc["mobile"],
        "role": "admin",
    }

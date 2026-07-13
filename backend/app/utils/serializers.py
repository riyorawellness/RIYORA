"""Doc → response DTO helpers. Never leak _id or password_hash."""


def user_to_public(doc: dict) -> dict:
    return {
        "id": str(doc.get("_id")),
        "full_name": doc["full_name"],
        "mobile": doc["mobile"],
        "state": doc["state"],
        "city": doc["city"],
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
    }


def admin_to_public(doc: dict) -> dict:
    return {
        "id": str(doc.get("_id")),
        "name": doc["name"],
        "mobile": doc["mobile"],
        "role": "admin",
    }

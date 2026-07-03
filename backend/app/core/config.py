"""Central configuration loaded from environment variables.

Follows 12-factor: all secrets/paths come from env. Never hardcode.
"""
import os
from functools import lru_cache


class Settings:
    # Mongo
    MONGO_URL: str = os.environ["MONGO_URL"]
    DB_NAME: str = os.environ["DB_NAME"]

    # CORS
    CORS_ORIGINS: str = os.environ.get("CORS_ORIGINS", "*")

    # JWT
    JWT_SECRET: str = os.environ["JWT_SECRET"]
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TTL_MIN: int = int(os.environ.get("JWT_ACCESS_TTL_MIN", "15"))
    JWT_REFRESH_TTL_DAYS: int = int(os.environ.get("JWT_REFRESH_TTL_DAYS", "7"))

    # OTP
    OTP_TTL_MIN: int = int(os.environ.get("OTP_TTL_MIN", "5"))
    OTP_RESEND_LIMIT_PER_HOUR: int = int(os.environ.get("OTP_RESEND_LIMIT_PER_HOUR", "5"))
    OTP_DEV_MODE: bool = os.environ.get("OTP_DEV_MODE", "true").lower() == "true"
    OTP_DEV_CODE: str = os.environ.get("OTP_DEV_CODE", "123456")

    # Admin seed
    ADMIN_MOBILE: str = os.environ["ADMIN_MOBILE"]
    ADMIN_PASSWORD: str = os.environ["ADMIN_PASSWORD"]
    ADMIN_NAME: str = os.environ.get("ADMIN_NAME", "Admin")

    # Company (referral tree root)
    COMPANY_MEMBERSHIP_ID: str = os.environ.get("COMPANY_MEMBERSHIP_ID", "RW000000")
    COMPANY_NAME: str = os.environ.get("COMPANY_NAME", "RIYORA Wellness")

    # Storage / files
    EMERGENT_LLM_KEY: str = os.environ.get("EMERGENT_LLM_KEY", "")
    APP_NAME: str = os.environ.get("APP_NAME", "riyora-wellness")
    FILE_TOKEN_TTL_SEC: int = int(os.environ.get("FILE_TOKEN_TTL_SEC", "300"))

    # Commerce defaults (also stored in cms_settings and can be overridden by admin)
    DEFAULT_GST_PERCENT: float = float(os.environ.get("DEFAULT_GST_PERCENT", "18"))
    DEFAULT_VALIDITY_DAYS: int = int(os.environ.get("DEFAULT_VALIDITY_DAYS", "365"))
    COMMISSION_L1_PERCENT: float = float(os.environ.get("COMMISSION_L1_PERCENT", "10"))
    COMMISSION_L2_PERCENT: float = float(os.environ.get("COMMISSION_L2_PERCENT", "5"))
    COMMISSION_L3_PERCENT: float = float(os.environ.get("COMMISSION_L3_PERCENT", "2"))
    ACTIVITY_SESSIONS_REQUIRED: int = int(os.environ.get("ACTIVITY_SESSIONS_REQUIRED", "4"))

    # Razorpay (mocked by default)
    RAZORPAY_MOCK_MODE: bool = os.environ.get("RAZORPAY_MOCK_MODE", "true").lower() == "true"
    RAZORPAY_KEY_ID: str = os.environ.get("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET: str = os.environ.get("RAZORPAY_KEY_SECRET", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()

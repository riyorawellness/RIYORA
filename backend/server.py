"""RIYORA WELLNESS - Backend Entry (FastAPI).

Phase 1: project foundation + authentication + user/admin/membership APIs.
Programs, payments, referral engine, activity meter, reports, notifications
are intentionally out of scope for this phase.
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from pymongo.errors import DuplicateKeyError  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.seed_legal import seed_legal_pages  # noqa: E402
from app.db.mongo import (  # noqa: E402
    create_indexes,
    get_client,
    seed_admin,
    seed_app_settings,
    seed_company_account,
    seed_program_categories,
    seed_referral_tree_root,
)
from app.routes import admin as admin_routes  # noqa: E402
from app.routes import auth as auth_routes  # noqa: E402
from app.routes import firebase_auth_routes  # noqa: E402
from app.routes import membership as membership_routes  # noqa: E402
from app.routes import user as user_routes  # noqa: E402

# Phase 2 route modules
from app.routes import activity_log as activity_log_routes  # noqa: E402
from app.routes import assessments as assessments_routes  # noqa: E402
from app.routes import bank_details as bank_details_routes  # noqa: E402
from app.routes import categories as categories_routes  # noqa: E402
from app.routes import certificates as certificates_routes  # noqa: E402
from app.routes import content as content_routes  # noqa: E402
from app.routes import modules as modules_routes  # noqa: E402
from app.routes import notifications as notifications_routes  # noqa: E402
from app.routes import profiles as profiles_routes  # noqa: E402
from app.routes import programs as programs_routes  # noqa: E402
from app.routes import progress as progress_routes  # noqa: E402
from app.routes import purchases as purchases_routes  # noqa: E402
from app.routes import referral_tree as referral_tree_routes  # noqa: E402
from app.routes import settings as settings_routes  # noqa: E402
from app.routes import payments as payments_routes  # noqa: E402
from app.routes import referrals as referrals_routes  # noqa: E402
from app.routes import activity as activity_routes  # noqa: E402
from app.routes import commissions as commissions_routes  # noqa: E402
from app.routes import payouts as payouts_routes  # noqa: E402
from app.routes import reports as reports_routes  # noqa: E402
from app.routes import admin_dashboard as admin_dashboard_routes  # noqa: E402
from app.routes import admin_users as admin_users_routes  # noqa: E402
from app.routes import admin_preview as admin_preview_routes  # noqa: E402
from app.routes import admin_backups as admin_backups_routes  # noqa: E402
from app.routes import cms as cms_routes  # noqa: E402
from app.routes import admin_phase7 as admin_phase7_routes  # noqa: E402
from app.routes import analytics as analytics_routes  # noqa: E402
from app.routes import admin_reports as admin_reports_routes  # noqa: E402
from app.routes import health as health_routes  # noqa: E402
from app.routes import qa as qa_routes  # noqa: E402
from app.routes import manual_payments as manual_payments_routes  # noqa: E402
from app.routes import admin_danger as admin_danger_routes  # noqa: E402
from app.routes import profile_editing as profile_editing_routes  # noqa: E402
from app.core.security_mw import SecurityHeadersMiddleware, limiter  # noqa: E402
from app.core.logging_mw import RequestIdMiddleware  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from slowapi import _rate_limit_exceeded_handler  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("riyora")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting RIYORA WELLNESS backend ...")
    await create_indexes()
    await seed_company_account()
    await seed_referral_tree_root()
    await seed_program_categories()
    await seed_app_settings()
    await seed_admin()
    # Phase 10 — legal & support placeholder CMS pages
    from app.db.mongo import get_db  # local import to avoid cycle
    await seed_legal_pages(get_db())
    # Nightly background scheduler (validity-expiring scan @ 03:00 IST)
    from app.services import scheduler as _scheduler
    _scheduler.start(get_db())
    logger.info("Startup complete.")
    yield
    from app.services import scheduler as _scheduler_stop
    _scheduler_stop.stop()
    get_client().close()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="RIYORA WELLNESS API",
    description="Heal. Learn. Earn. - Phase 1 Foundation (Auth + Membership + Admin)",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    # Strip whitespace so `"a, b"` in .env doesn't produce a leading-space
    # origin that never matches the browser's Origin header. Filter empties
    # in case of trailing commas.
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIdMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    # Flatten pydantic errors so React can render `detail` as a string.
    msgs = []
    for e in exc.errors():
        loc = ".".join(str(p) for p in e.get("loc", []) if p != "body")
        msgs.append(f"{loc}: {e.get('msg')}" if loc else e.get("msg", "invalid"))
    return JSONResponse(status_code=422, content={"detail": "; ".join(msgs)})


@app.exception_handler(DuplicateKeyError)
async def duplicate_key_handler(_request: Request, exc: DuplicateKeyError):
    """Return a friendly 409 whenever a MongoDB unique index rejects a write.

    Without this, ``motor`` bubbles the raw ``DuplicateKeyError`` up as a
    500 — and 500s from CORS-protected origins land in the browser as an
    opaque "Network error" instead of a readable message.

    We do our best to extract the conflicting field name from the driver's
    ``details.keyPattern`` so the message tells the admin what to change.
    """
    field = None
    try:
        key_pattern = (getattr(exc, "details", None) or {}).get("keyPattern") or {}
        if key_pattern:
            field = next(iter(key_pattern.keys()), None)
    except Exception:
        field = None
    label = (field or "value").replace("_", " ")
    return JSONResponse(
        status_code=409,
        content={"detail": f"A record with this {label} already exists."},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all so uncaught exceptions still return JSON with CORS headers.

    Without this, Starlette's built-in 500 handler generates a plain
    ``Internal Server Error`` text response that doesn't go through the
    CORS middleware — the browser then reports it as a generic
    "Network error" and the frontend toast is useless.
    """
    logger.exception(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Server error. Please try again in a moment."},
    )


# ---- API v1 router (mounted under /api) ------------------------------------
from fastapi import APIRouter  # noqa: E402

api_router = APIRouter(prefix="/api")


@api_router.get("/", tags=["Health"])
async def root():
    return {
        "app": "RIYORA WELLNESS",
        "tagline": "Heal. Learn. Earn.",
        "version": "1.0.0",
        "status": "ok",
    }


@api_router.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}


api_router.include_router(auth_routes.router)
api_router.include_router(firebase_auth_routes.router)
api_router.include_router(user_routes.router)
api_router.include_router(membership_routes.router)
api_router.include_router(admin_routes.router)

# Phase 2 routers
api_router.include_router(profiles_routes.router)
api_router.include_router(categories_routes.router)
api_router.include_router(programs_routes.router)
api_router.include_router(modules_routes.router)
api_router.include_router(assessments_routes.router)
api_router.include_router(purchases_routes.router)
api_router.include_router(progress_routes.router)
api_router.include_router(certificates_routes.router)
api_router.include_router(referral_tree_routes.router)
api_router.include_router(bank_details_routes.router)
api_router.include_router(settings_routes.router)
api_router.include_router(notifications_routes.router)
api_router.include_router(activity_log_routes.router)
api_router.include_router(content_routes.router)
api_router.include_router(payments_routes.router)
api_router.include_router(referrals_routes.router)
api_router.include_router(activity_routes.router)
api_router.include_router(commissions_routes.router)
api_router.include_router(payouts_routes.router)
api_router.include_router(reports_routes.router)
api_router.include_router(admin_dashboard_routes.router)
api_router.include_router(admin_users_routes.router)
api_router.include_router(admin_preview_routes.router)
api_router.include_router(admin_backups_routes.router)
api_router.include_router(cms_routes.router)
api_router.include_router(cms_routes.admin_router)
api_router.include_router(admin_phase7_routes.router)
api_router.include_router(analytics_routes.router)
api_router.include_router(admin_reports_routes.router)
api_router.include_router(health_routes.router)
api_router.include_router(qa_routes.router)
api_router.include_router(manual_payments_routes.user_router)
api_router.include_router(manual_payments_routes.admin_router)
api_router.include_router(manual_payments_routes.serve_router)
api_router.include_router(admin_danger_routes.router)
api_router.include_router(profile_editing_routes.router)
api_router.include_router(profile_editing_routes.admin_router)

app.include_router(api_router)

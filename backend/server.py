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
from fastapi.responses import JSONResponse  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

from app.core.config import get_settings  # noqa: E402
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
    logger.info("Startup complete.")
    yield
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
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


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

app.include_router(api_router)

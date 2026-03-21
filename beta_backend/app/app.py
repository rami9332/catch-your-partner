from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.db import build_engine, build_session_factory, init_db
from app.errors import install_error_handlers
from app.events import EventBus
from app.feature_flags import FeatureFlagStore
from app.logging import configure_logging, log_request
from app.middleware import RateLimiter
from app.routers import auth, companion, core, health, identity, modules
from app.services.companion_service import CompanionService
from app.services.core_service import CoreService
from app.services.identity_service import IdentityService
from app.services.module_service import ModuleService


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title=settings.app_name, version="0.4.0")

    logger = configure_logging(settings.log_level)
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)

    if settings.auto_create_tables:
        init_db(engine)

    app.state.settings = settings
    app.state.logger = logger
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.events = EventBus()
    app.state.rate_limiter = RateLimiter(settings)
    app.state.feature_flags = FeatureFlagStore(settings)
    app.state.module_service = ModuleService(app.state.feature_flags)
    app.state.core_service = CoreService(settings, app.state.events)
    app.state.identity_service = IdentityService(app.state.events)
    app.state.companion_service = CompanionService(app.state.events)
    settings.profile_photo_upload_path.mkdir(parents=True, exist_ok=True)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[*settings.cors_origins, "null"],
        allow_origin_regex=r"^(null|https?://(([a-z0-9-]+\.)?onrender\.com|localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?)$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        app.state.rate_limiter.check(request)
        return await call_next(request)

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        return await log_request(app.state.logger, request, call_next)

    install_error_handlers(app)
    app.mount("/media/profile-photos", StaticFiles(directory=str(settings.profile_photo_upload_path)), name="profile-photos")
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(modules.router)
    app.include_router(identity.router)
    app.include_router(companion.router)
    app.include_router(core.router)
    return app


app = create_app()

from contextlib import asynccontextmanager
import re
import uuid

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from api.routes import admin, ai, auth, clinician, devices, organizations, patients, realtime, sessions
from core.config import settings
from core.database_security import assert_postgresql_runtime_isolation
from db.database import SessionLocal, init_db
from services.ai_pipeline import assert_ai_pipeline_ready


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_DB:
        init_db()
    if settings.ENVIRONMENT == "production" and settings.REQUIRE_POSTGRES_RLS:
        db = SessionLocal()
        try:
            assert_postgresql_runtime_isolation(db)
        finally:
            db.close()
    if settings.AI_PIPELINE_MODE != "disabled":
        db = SessionLocal()
        try:
            assert_ai_pipeline_ready(db)
        finally:
            db.close()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for the FETAL-GUARD smart maternity belt prototype.",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
    redoc_url=None if settings.ENVIRONMENT == "production" else "/redoc",
    openapi_url=None if settings.ENVIRONMENT == "production" else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Organization-ID"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)


_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


@app.middleware("http")
async def add_security_headers(request, call_next):
    supplied_request_id = request.headers.get("X-Request-ID", "")
    request_id = (
        supplied_request_id
        if _REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
        else str(uuid.uuid4())
    )
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Request-ID"] = request_id
    response.headers["Vary"] = "Origin, Authorization, X-Organization-ID"
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(patients.router, prefix="/patients", tags=["patients"])
app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
app.include_router(clinician.router, prefix="/clinician", tags=["clinician"])
app.include_router(devices.router, prefix="/devices", tags=["devices"])
app.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
app.include_router(realtime.router, prefix="/realtime", tags=["realtime"])
app.include_router(ai.router, prefix="/ai", tags=["ai"])


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Welcome to FETAL-GUARD API"}


@app.get("/health/live", include_in_schema=False)
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
def health_ready(response: Response) -> dict[str, str]:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        if settings.ENVIRONMENT == "production" and settings.REQUIRE_POSTGRES_RLS:
            assert_postgresql_runtime_isolation(db)
        assert_ai_pipeline_ready(db)
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable"}
    finally:
        db.close()
    return {"status": "ready"}

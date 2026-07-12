from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import admin, ai, auth, clinician, devices, patients, sessions
from core.config import settings
from db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_DB:
        init_db()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for the FETAL-GUARD smart maternity belt prototype.",
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(patients.router, prefix="/patients", tags=["patients"])
app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
app.include_router(clinician.router, prefix="/clinician", tags=["clinician"])
app.include_router(devices.router, prefix="/devices", tags=["devices"])
app.include_router(ai.router, prefix="/ai", tags=["ai"])


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Welcome to FETAL-GUARD API"}

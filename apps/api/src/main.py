from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.storage import ensure_bucket
from .routes import auth, parts, projects, analysis, jobs

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    ensure_bucket()
    yield
    # Shutdown


app = FastAPI(
    title="MoldMind API",
    description="Manufacturing intelligence platform for injection mold design",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(parts.router, prefix="/api/parts", tags=["parts"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}

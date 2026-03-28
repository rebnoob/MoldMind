from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.storage import ensure_bucket
from .core.database import init_db
from .routes import auth, parts, projects, analysis, jobs

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
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


@app.get("/api/files/{path:path}")
async def serve_file(path: str):
    """Serve files from local storage (dev mode). In prod, use S3 presigned URLs."""
    from .core.storage import download_file
    try:
        data = download_file(path)
        content_type = "model/gltf-binary" if path.endswith(".glb") else "application/octet-stream"
        return Response(content=data, media_type=content_type)
    except FileNotFoundError:
        return Response(status_code=404, content="File not found")

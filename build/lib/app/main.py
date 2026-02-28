from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

from app.api.v1 import routes_hanzi, routes_assignments

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Hanzi Project migrated to FastAPI"
)

# CORS Middleware
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(routes_hanzi.router, prefix="/api/v1/hanzi", tags=["hanzi"])
app.include_router(routes_assignments.router, prefix="/api/v1/assignments", tags=["assignments"])


@app.get("/")
def read_root():
    return {"message": "Welcome to Hanzi Project API"}


@app.get("/health")
def health_check():
    return {"status": "ok"}

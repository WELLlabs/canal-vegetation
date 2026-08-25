from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import setup_logging
from app.models.db import get_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    get_settings()
    get_engine()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    wildcard = origins == ["*"] or not origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if wildcard else origins,
        allow_credentials=not wildcard,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    def app_error_handler(_request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()

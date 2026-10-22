import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .api import router
from .core.config import get_settings
from .core.signing import GrantSigner
from .db import session_factory
from .services import DomainError


def create_app(settings=None):
    settings = settings or get_settings()
    engine, sessions = session_factory(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(title="API Lisensi ChessLab", version="1.0.0", lifespan=lifespan,
                  description="API lisensi dan administrasi. Sesi admin menggunakan cookie dan token CSRF.")
    app.state.settings, app.state.sessions = settings, sessions
    app.state.engine, app.state.signer = engine, GrantSigner(settings)

    @app.exception_handler(DomainError)
    async def domain_error(request, error):
        return JSONResponse({"error": {"code": error.code, "message": error.message}}, status_code=error.status,
                            headers={"Retry-After": "900"} if error.status == 429 else {})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Jangan echo body karena dapat mengandung password atau license_key.
        return JSONResponse({"error": {"code": "INVALID_REQUEST", "message": "Data permintaan tidak valid.",
                              "fields": [".".join(map(str, e["loc"])) for e in error.errors()]}}, status_code=422)

    @app.exception_handler(IntegrityError)
    async def conflict(request, error):
        return JSONResponse({"error": {"code": "CONFLICT", "message": "Data sudah ada atau melanggar batas basis data."}}, status_code=409)

    @app.exception_handler(Exception)
    async def unexpected(request, error):
        logging.getLogger("chesslab.license").error("Kesalahan internal API (%s)", type(error).__name__)
        return JSONResponse({"error": {"code": "INTERNAL_ERROR", "message": "Layanan sementara bermasalah."}}, status_code=500)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/healthz")
    def health():
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            connection.execute(text("SELECT version_num FROM alembic_version"))
        return {"status": "ok"}

    app.include_router(router)
    return app

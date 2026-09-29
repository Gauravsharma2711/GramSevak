import os
import sys

# Ensure repository root is on sys.path for robust cloud deployment
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import logging
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.core.logging import setup_logging
from backend.app.core.database import check_db_connection
from backend.app.api.v1.router import api_router

# Initialize structured application logging
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="SIH26074: Downscaling of Weather Forecasts from Block Level to Panchayat Level for Agro-Meteorological Advisory Services",
    version="1.0.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Also expose OpenAPI schema at /api/v1/openapi.json and documentation at /api/v1/docs
@app.get("/api/v1/openapi.json", include_in_schema=False)
def get_v1_openapi():
    return app.openapi()


@app.get("/api/v1/docs", include_in_schema=False)
def get_v1_docs():
    from fastapi.openapi.docs import get_swagger_ui_html
    return get_swagger_ui_html(openapi_url="/api/v1/openapi.json", title=f"{settings.PROJECT_NAME} - Swagger UI")


@app.get("/api/v1/redoc", include_in_schema=False)
def get_v1_redoc():
    from fastapi.openapi.docs import get_redoc_html
    return get_redoc_html(openapi_url="/api/v1/openapi.json", title=f"{settings.PROJECT_NAME} - ReDoc")

# Configure CORS Middleware for deployed web frontends and mobile clients
origins = settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [str(settings.CORS_ORIGINS)]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True if "*" not in origins else False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

from sqlalchemy.exc import SQLAlchemyError

# Structured database exception handler: guarantees zero leakage of SQL queries, table schemas, or DB credentials
@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error(
        f"Database exception on {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A database error occurred while processing the request. Please try again later."},
    )


# Structured unhandled exception handler: logs error server-side, never exposes stack trace or secrets to clients
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled server exception on {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


# Root health endpoint directly at /health
@app.get("/health", tags=["Health"])
def root_health():
    """
    Direct root health check endpoint.
    Returns {"status": "ok"}
    """
    return {"status": "ok"}


# Direct database health check endpoint at /health/db
@app.get("/health/db", tags=["Health"])
def root_db_health(response: Response):
    """
    Direct root database health check endpoint.
    """
    db_info = check_db_connection()
    if not db_info.get("connected"):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if db_info.get("connected") else "error",
        "service": settings.PROJECT_NAME,
        "database": db_info,
    }


# Include API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG,
    )

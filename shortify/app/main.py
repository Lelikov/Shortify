from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus

import sentry_sdk
import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import RedirectResponse
from starlette.templating import Jinja2Templates, _TemplateResponse
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from shortify.app import api
from shortify.app.admin.deps import AdminAuthError
from shortify.app.admin.router import router as admin_router
from shortify.app.core.config import settings
from shortify.app.core.logging import configure_logging
from shortify.app.core.rate_limit import limiter
from shortify.app.db import init_db
from shortify.app.schemas.error import APIValidationError, CommonHTTPError


logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    await init_db.init()
    yield


if settings.SENTRY_DSN:
    logger.info(f"Initializing Sentry with DSN: {settings.SENTRY_DSN}")
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        send_default_pii=True,
        environment="dev" if settings.DEBUG else "production",
        debug=settings.DEBUG,
    )

tags_metadata = [
    {
        "name": "Authentication",
        "description": "Get authentication token",
    },
    {
        "name": "Users",
        "description": "User registration and management",
    },
    {
        "name": "URLs",
        "description": "Shorten and manage URLs",
    },
]

# Common response codes
responses: set[int] = {
    status.HTTP_400_BAD_REQUEST,
    status.HTTP_401_UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN,
    status.HTTP_404_NOT_FOUND,
    status.HTTP_500_INTERNAL_SERVER_ERROR,
}

app = FastAPI(
    debug=settings.DEBUG,
    title=settings.PROJECT_NAME,
    description="Fast and reliable URL shortener powered by FastAPI and MongoDB.",
    openapi_url=f"/api/{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None,
    docs_url=None,
    redoc_url=None,
    default_response_class=ORJSONResponse,
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    license_info={
        "name": "GNU General Public License v3.0",
        "url": "https://www.gnu.org/licenses/gpl-3.0.en.html",
    },
    responses={
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Validation Error",
            "model": APIValidationError,  # Adds OpenAPI schema for 422 errors
        },
        **{
            code: {
                "description": HTTPStatus(code).phrase,
                "model": CommonHTTPError,
            }
            for code in responses
        },
    },
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

templates = Jinja2Templates(directory="shortify/app/templates")

app.mount("/static", StaticFiles(directory="shortify/app/static"), name="static")

app.include_router(api.router)
app.include_router(api.redirect.router)
app.include_router(admin_router, prefix=settings.ADMIN_PATH)
if not settings.DEBUG:
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")


@app.exception_handler(AdminAuthError)
async def admin_auth_exception_handler(_: Request, __: AdminAuthError) -> RedirectResponse:
    return RedirectResponse(url=f"{settings.ADMIN_PATH}/login", status_code=status.HTTP_302_FOUND)


if settings.CORS_ORIGINS:
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

if settings.USE_CORRELATION_ID:
    from shortify.app.middlewares.correlation import CorrelationMiddleware

    app.add_middleware(CorrelationMiddleware)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> _TemplateResponse | ORJSONResponse:
    if exc.status_code == HTTPStatus.NOT_FOUND:
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            context={"detail": exc.detail},
            status_code=HTTPStatus.NOT_FOUND,
        )

    return ORJSONResponse(
        content={
            "message": exc.detail,
        },
        status_code=exc.status_code,
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def custom_validation_exception_handler(
    _: Request,
    exc: RequestValidationError,
) -> ORJSONResponse:
    return ORJSONResponse(
        content=APIValidationError.from_pydantic(exc).dict(exclude_none=True),
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )

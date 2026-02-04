import base64
import contextlib
import datetime
import io
from typing import Annotated

import pyotp
import qrcode
from beanie import PydanticObjectId
from fastapi import APIRouter, Form, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from shortify.app.admin.deps import AdminAuthError, CurrentAdminUser, get_current_admin_user
from shortify.app.core import security
from shortify.app.core.config import settings
from shortify.app.core.rate_limit import limiter
from shortify.app.models import ShortUrl, User


router = APIRouter()
templates = Jinja2Templates(directory="shortify/app/templates")


@router.get("/login", include_in_schema=False, response_model=None)
async def login_page(request: Request) -> Response:
    token = request.cookies.get("access_token")
    if token:
        with contextlib.suppress(AdminAuthError):
            await get_current_admin_user(request)
            return RedirectResponse(url=f"{settings.ADMIN_PATH}/", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        request=request,
        name="admin/login.html",
        context={},
    )


@router.post("/login", include_in_schema=False, response_model=None)
@limiter.limit("5/minute")
async def login_action(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    totp_code: Annotated[str | None, Form()] = None,
) -> Response:
    user = await User.authenticate(username=username, password=password)
    if not user or not user.is_active or not user.is_superuser:
        return templates.TemplateResponse(
            request=request,
            name="admin/login.html",
            context={"error": "Invalid credentials or insufficient permissions"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if user.totp_secret:
        if not totp_code:
            return templates.TemplateResponse(
                request=request,
                name="admin/login.html",
                context={"error": "TOTP code required", "username_value": username},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(totp_code):
            return templates.TemplateResponse(
                request=request,
                name="admin/login.html",
                context={"error": "Invalid TOTP code", "username_value": username},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

    response = RedirectResponse(url=f"{settings.ADMIN_PATH}/", status_code=status.HTTP_302_FOUND)
    access_token = security.create_access_token(user.id)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=not settings.DEBUG,
    )
    return response


@router.get("/logout", include_in_schema=False)
async def logout() -> RedirectResponse:
    response = RedirectResponse(url=f"{settings.ADMIN_PATH}/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("access_token")
    return response


@router.get("/setup-totp", include_in_schema=False, response_model=None)
async def setup_totp_page(
    request: Request,
    user: CurrentAdminUser,
) -> Response:
    if user.totp_secret:
        return RedirectResponse(url=f"{settings.ADMIN_PATH}/", status_code=status.HTTP_302_FOUND)

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=user.email, issuer_name="Shortify Admin")

    img = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return templates.TemplateResponse(
        request=request,
        name="admin/totp_setup.html",
        context={"user": user, "secret": secret, "qr_code": img_b64},
    )


@router.post("/setup-totp", include_in_schema=False, response_model=None)
async def setup_totp_action(
    request: Request,
    user: CurrentAdminUser,
    secret: Annotated[str, Form()],
    code: Annotated[str, Form()],
) -> Response:
    totp = pyotp.TOTP(secret)
    if not totp.verify(code):
        return templates.TemplateResponse(
            request=request,
            name="admin/totp_setup.html",
            context={
                "user": user,
                "secret": secret,
                "error": "Invalid code",
                "qr_code": "",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user.totp_secret = secret
    await user.save()
    return RedirectResponse(url=f"{settings.ADMIN_PATH}/", status_code=status.HTTP_302_FOUND)


@router.get("/", include_in_schema=False, response_model=None)
async def dashboard(
    request: Request,
    user: CurrentAdminUser,
) -> Response:
    if not user.totp_secret:
        return RedirectResponse(url=f"{settings.ADMIN_PATH}/setup-totp", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context={"user": user},
    )


@router.get("/users", include_in_schema=False, response_model=None)
async def list_users(
    request: Request,
    user: CurrentAdminUser,
    q: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> Response:
    if not user.totp_secret:
        return RedirectResponse(url=f"{settings.ADMIN_PATH}/setup-totp", status_code=status.HTTP_302_FOUND)

    skip = (page - 1) * limit
    query = {}
    if q:
        query = {
            "$or": [
                {"username": {"$regex": q, "$options": "i"}},
                {"email": {"$regex": q, "$options": "i"}},
            ],
        }

    users = await User.find(query).skip(skip).limit(limit).to_list()
    total_count = await User.find(query).count()
    total_pages = (total_count + limit - 1) // limit

    return templates.TemplateResponse(
        request=request,
        name="admin/users.html",
        context={
            "request": request,
            "user": user,
            "users": users,
            "q": q,
            "page": page,
            "total_pages": total_pages,
        },
    )


@router.post("/users/delete/{user_id}", include_in_schema=False)
async def delete_user(
    user_id: PydanticObjectId,
) -> RedirectResponse:
    user_to_delete = await User.get(user_id)
    if user_to_delete:
        await user_to_delete.delete()

    return RedirectResponse(url=f"{settings.ADMIN_PATH}/users", status_code=status.HTTP_302_FOUND)


@router.get("/urls", include_in_schema=False, response_model=None)
async def list_urls(
    request: Request,
    user: CurrentAdminUser,
    q: str | None = None,
    page: int = 1,
    limit: int = 20,
    sort_by: str = "created_at",
    order: str = "desc",
) -> Response:
    if not user.totp_secret:
        return RedirectResponse(url=f"{settings.ADMIN_PATH}/setup-totp", status_code=status.HTTP_302_FOUND)

    skip = (page - 1) * limit
    query = {}
    if q:
        query = {
            "$or": [
                {"ident": {"$regex": q, "$options": "i"}},
                {"external_id": {"$regex": q, "$options": "i"}},
                {"origin": {"$regex": q, "$options": "i"}},
            ],
        }

    # Validate sort_by
    if sort_by not in ["created_at", "expires_at", "views"]:
        sort_by = "created_at"

    sort_direction = -1 if order == "desc" else 1

    urls = await ShortUrl.find(query).sort((sort_by, sort_direction)).skip(skip).limit(limit).to_list()
    total_count = await ShortUrl.find(query).count()
    total_pages = (total_count + limit - 1) // limit

    return templates.TemplateResponse(
        request=request,
        name="admin/urls.html",
        context={
            "request": request,
            "user": user,
            "urls": urls,
            "q": q,
            "page": page,
            "total_pages": total_pages,
            "sort_by": sort_by,
            "order": order,
            "now": datetime.datetime.now(datetime.UTC).replace(tzinfo=None),
        },
    )


@router.post("/urls/batch-delete", include_in_schema=False)
async def batch_delete_urls(
    url_ids: Annotated[list[str] | None, Form()] = None,
) -> RedirectResponse:
    if url_ids is None:
        url_ids = []
    if url_ids:
        ids = []
        for uid in url_ids:
            with contextlib.suppress(Exception):
                ids.append(PydanticObjectId(uid))

        if ids:
            await ShortUrl.find({"_id": {"$in": ids}}).delete()

    return RedirectResponse(url=f"{settings.ADMIN_PATH}/urls", status_code=status.HTTP_302_FOUND)


@router.post("/urls/delete/{url_id}", include_in_schema=False)
async def delete_url(
    url_id: PydanticObjectId,
) -> RedirectResponse:
    url_to_delete = await ShortUrl.get(url_id)
    if url_to_delete:
        await url_to_delete.delete()

    return RedirectResponse(url=f"{settings.ADMIN_PATH}/urls", status_code=status.HTTP_302_FOUND)


@router.get("/urls/{ident}", include_in_schema=False, response_model=None)
async def url_detail(
    request: Request,
    ident: str,
    user: CurrentAdminUser,
) -> Response:
    if not user.totp_secret:
        return RedirectResponse(url=f"{settings.ADMIN_PATH}/setup-totp", status_code=status.HTTP_302_FOUND)

    short_url = await ShortUrl.get_by_ident(ident=ident)
    if not short_url:
        return RedirectResponse(url=f"{settings.ADMIN_PATH}/urls", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        request=request,
        name="admin/url_detail.html",
        context={
            "request": request,
            "user": user,
            "url": short_url,
            "now": datetime.datetime.now(datetime.UTC).replace(tzinfo=None),
            "settings": settings,
        },
    )


@router.post("/urls/{ident}", include_in_schema=False)
async def url_update(
    ident: str,
    origin: Annotated[str, Form()],
    external_id: Annotated[str | None, Form()] = None,
    expires_at: Annotated[str | None, Form()] = None,
) -> RedirectResponse:
    short_url = await ShortUrl.get_by_ident(ident=ident)
    if not short_url:
        return RedirectResponse(url=f"{settings.ADMIN_PATH}/urls", status_code=status.HTTP_302_FOUND)

    short_url.origin = origin
    short_url.external_id = external_id or None

    if expires_at:
        with contextlib.suppress(ValueError):
            short_url.expires_at = datetime.datetime.strptime(expires_at, "%Y-%m-%dT%H:%M")  # noqa: DTZ007

    else:
        short_url.expires_at = None

    await short_url.save()

    return RedirectResponse(url=f"{settings.ADMIN_PATH}/urls/{ident}", status_code=status.HTTP_302_FOUND)

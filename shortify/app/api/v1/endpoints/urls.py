import datetime
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from shortify.app import schemas
from shortify.app.api.v1.deps import (
    get_current_active_superuser,
    get_current_active_user,
)
from shortify.app.models import ShortUrl, User
from shortify.app.utils import cbv, paginate


if TYPE_CHECKING:
    from shortify.app.utils.types import PaginationDict

router = APIRouter()


def short_url_not_found(ident: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Short URL with identifier {ident!r} not found",
    )


def short_url_by_external_id_not_found(external_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Short URL with external_id {external_id!r} not found",
    )


@cbv(router)
class BasicUserViews:
    user: User = Depends(get_current_active_user)

    @router.post("/shorten", response_model=schemas.ShortUrl, status_code=status.HTTP_201_CREATED)
    async def shorten_url(self, payload: schemas.ShortUrlCreate) -> ShortUrl:
        return await ShortUrl.shorten(
            url=payload.url,
            external_id=payload.external_id,
            expires_at=payload.expires_at,
            user_id=self.user.id,
        )


@cbv(router)
class SuperuserViews:
    superuser: User = Depends(get_current_active_superuser)

    @router.get("/", response_model=schemas.Paginated[schemas.ShortUrl])
    async def get_urls(
        self,
        paging: Annotated[schemas.PaginationParams, Depends()],
        sorting: Annotated[schemas.SortingParams, Depends()],
    ) -> "PaginationDict":
        return await paginate(ShortUrl, paging, sorting)

    @router.get("/ident/{ident}", response_model=schemas.ShortUrl)
    async def get_short_url(self, ident: str) -> ShortUrl:
        short_url = await ShortUrl.get_by_ident(ident=ident)
        if not short_url:
            raise short_url_not_found(ident)
        return short_url

    @router.patch("/ident/{ident}", response_model=schemas.ShortUrl)
    async def update_short_url(
        self,
        ident: str,
        payload: schemas.ShortUrlUpdate,
    ) -> ShortUrl:
        short_url = await ShortUrl.get_by_ident(ident=ident)
        if not short_url:
            raise short_url_not_found(ident)
        return await self._update_short_url(short_url, payload)

    @router.delete("/ident/{ident}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_short_url(self, ident: str) -> None:
        short_url = await ShortUrl.get_by_ident(ident=ident)
        if not short_url:
            raise short_url_not_found(ident)
        await short_url.delete()

    @router.get("/external/{external_id}", response_model=schemas.ShortUrl)
    async def get_short_url_by_external_id(self, external_id: str) -> ShortUrl:
        short_url = await ShortUrl.get_by_external_id(external_id=external_id)
        if not short_url:
            raise short_url_by_external_id_not_found(external_id)
        return short_url

    @router.patch("/external/{external_id}", response_model=schemas.ShortUrl)
    async def update_short_url_by_external_id(
        self,
        external_id: str,
        payload: schemas.ShortUrlUpdate,
    ) -> ShortUrl:
        short_url = await ShortUrl.get_by_external_id(external_id=external_id)
        if not short_url:
            raise short_url_by_external_id_not_found(external_id)
        return await self._update_short_url(short_url, payload)

    @router.delete("/external/{external_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_short_url_by_external_id(self, external_id: str) -> None:
        short_url = await ShortUrl.get_by_external_id(external_id=external_id)
        if not short_url:
            raise short_url_by_external_id_not_found(external_id)
        await short_url.delete()

    @staticmethod
    async def _update_short_url(
        short_url: ShortUrl,
        payload: schemas.ShortUrlUpdate,
    ) -> ShortUrl:
        update_data = payload.dict(exclude_unset=True)
        if "url" in update_data:
            short_url.origin = str(update_data["url"])
        if "external_id" in update_data:
            short_url.external_id = update_data["external_id"]
        if "expires_at" in update_data:
            short_url.expires_at = update_data["expires_at"]

        short_url.updated_at = datetime.datetime.now(datetime.UTC)
        await short_url.save()
        return short_url

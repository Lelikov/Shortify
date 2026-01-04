import datetime
import random
import string
from typing import TYPE_CHECKING, Optional

from beanie import Document, Indexed, PydanticObjectId
from pydantic import AnyUrl, Field

from shortify.app.core.config import settings


if TYPE_CHECKING:
    from shortify.app.schemas import PaginationParams, SortingParams


def generate_ident(length: int) -> str:
    return "-".join("".join(random.choices(string.ascii_lowercase, k=3)) for _ in range(length))


class ShortUrl(Document):
    ident: Indexed(str, unique=True)  # type: ignore[valid-type]
    external_id: Indexed(str, unique=True, partialFilterExpression={"external_id": {"$type": "string"}}) | None = None
    origin: str
    views: int = 0
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC),
    )
    updated_at: datetime.datetime | None = None
    expires_at: Indexed(datetime.datetime, expireAfterSeconds=0) | None = None
    last_visit_at: datetime.datetime | None = None
    user_id: PydanticObjectId | None = None

    @classmethod
    async def shorten(
        cls,
        *,
        url: AnyUrl,
        external_id: str | None = None,
        expires_at: float | None = None,
        user_id: PydanticObjectId | None = None,
    ) -> "ShortUrl":
        return await cls(
            ident=generate_ident(settings.URL_IDENT_LENGTH),
            origin=url.encoded_string(),
            external_id=external_id,
            expires_at=expires_at,
            user_id=user_id,
        ).insert()

    @classmethod
    async def get_by_ident(
        cls,
        *,
        ident: str,
        is_check_expires_at: bool = False,
    ) -> Optional["ShortUrl"]:
        if is_check_expires_at:
            return await cls.find_one(
                cls.ident == ident,
                cls.expires_at > datetime.datetime.now(datetime.UTC),
            )
        return await cls.find_one(cls.ident == ident)

    @classmethod
    async def get_by_external_id(cls, *, external_id: str) -> Optional["ShortUrl"]:
        return await cls.find_one(cls.external_id == external_id)

    @classmethod
    async def get_by_user(
        cls,
        *,
        user_id: PydanticObjectId,
        paging: "PaginationParams",
        sorting: "SortingParams",
    ) -> list["ShortUrl"]:
        return (
            await cls.find(cls.user_id == user_id)
            .skip(paging.skip)
            .limit(paging.limit)
            .sort(
                (sorting.sort, sorting.order.direction),
            )
            .to_list()
        )

    @classmethod
    async def visit(cls, *, instance: "ShortUrl") -> None:
        instance.views += 1
        instance.last_visit_at = datetime.datetime.now(datetime.UTC)
        await instance.save_changes()

    class Settings:
        name = "urls"
        use_state_management = True

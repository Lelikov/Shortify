from datetime import datetime

from pydantic import AnyUrl, BaseModel


class ShortUrlCreate(BaseModel):
    url: AnyUrl
    external_id: str | None = None
    expires_at: datetime | None = None


class ShortUrlUpdate(BaseModel):
    url: AnyUrl | None = None
    external_id: str | None = None
    expires_at: datetime | None = None


class ShortUrl(BaseModel):
    ident: str
    origin: AnyUrl
    views: int
    created_at: datetime
    updated_at: datetime | None = None
    external_id: str | None = None
    expires_at: datetime | None = None
    last_visit_at: datetime | None = None

    class Config:
        from_attributes = True

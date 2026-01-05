from beanie import PydanticObjectId
from pydantic import BaseModel


class AuthTokenPayload(BaseModel):
    sub: PydanticObjectId | None = None


class AuthToken(BaseModel):
    access_token: str
    token_type: str

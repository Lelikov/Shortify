import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, StringConstraints


class ConstrainedUsername(StringConstraints):
    min_length = 3
    max_length = 64
    regex = re.compile(r"^[A-Za-z0-9-_.]+$")
    to_lower = True
    strip_whitespace = True


# Shared properties between user models
class UserBase(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    is_active: bool = True
    is_superuser: bool = False


# Properties to receive on user creation
class UserCreate(UserBase):
    username: ConstrainedUsername
    email: EmailStr
    password: str


# Properties to receive on user update
class UserUpdate(UserBase):
    password: str | None = None


class UserInDBBase(UserBase):
    created_at: datetime
    api_key: str

    class Config:
        from_attributes = True


# Properties to return via API
class User(UserInDBBase):
    pass


# Properties stored in DB
class UserInDB(UserInDBBase):
    hashed_password: str

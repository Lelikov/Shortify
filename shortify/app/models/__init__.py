import sys
from collections.abc import Sequence
from typing import TypeVar

from beanie import Document

# All database models must be imported here to be able to
# initialize them on startup.
from .url import ShortUrl
from .user import User


DocType = TypeVar("DocType", bound=Document)


def gather_documents() -> Sequence[type[DocType]]:
    from inspect import getmembers, isclass  # noqa: PLC0415

    return [
        doc
        for _, doc in getmembers(sys.modules[__name__], isclass)
        if issubclass(doc, Document) and doc.__name__ != "Document"
    ]

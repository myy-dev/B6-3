from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from core.database import get_db
from core.exceptions import AuthenticationRequired
from models import User
from repositories import UserRepository

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user_optional(request: Request, db: DbSession) -> User | None:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        return None
    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        request.session.clear()
    return user


def require_user(
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> User:
    if user is None:
        raise AuthenticationRequired()
    return user


CurrentUser = Annotated[User, Depends(require_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]


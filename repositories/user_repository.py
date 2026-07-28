from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username))

    def get_by_oauth_identity(self, provider: str, subject: str) -> User | None:
        return self.db.scalar(
            select(User).where(
                User.oauth_provider == provider,
                User.oauth_subject == subject,
            )
        )

    def create(
        self,
        *,
        username: str,
        display_name: str,
        password_hash: str | None,
        oauth_provider: str | None = None,
        oauth_subject: str | None = None,
    ) -> User:
        user = User(
            username=username,
            display_name=display_name,
            password_hash=password_hash,
            oauth_provider=oauth_provider,
            oauth_subject=oauth_subject,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user


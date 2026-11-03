from __future__ import annotations

import re

from passlib.context import CryptContext
from passlib.utils import MAX_PASSWORD_SIZE
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from exceptions import AppError
from models import User
from repositories import UserRepository


USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{3,50}$")
password_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class AuthService:
    def __init__(self, db: Session) -> None:
        self.users = UserRepository(db)

    def register(self, *, username: str, display_name: str, password: str) -> User:
        username = username.strip().lower()
        display_name = display_name.strip()

        if not USERNAME_PATTERN.fullmatch(username):
            raise AppError("아이디는 영문, 숫자, 밑줄을 사용해 3~50자로 입력해 주세요.")
        if not 2 <= len(display_name) <= 80:
            raise AppError("닉네임은 2~80자로 입력해 주세요.")
        if len(password) < 8:
            raise AppError("비밀번호는 8자 이상이어야 합니다.")
        if len(password) > MAX_PASSWORD_SIZE:
            raise AppError(f"비밀번호는 {MAX_PASSWORD_SIZE:,}자 이하여야 합니다.")
        if self.users.get_by_username(username):
            raise AppError("이미 사용 중인 아이디입니다.")

        try:
            return self.users.create(
                username=username,
                display_name=display_name,
                password_hash=password_context.hash(password),
            )
        except IntegrityError as exc:
            if self.users.get_by_username(username):
                raise AppError("이미 사용 중인 아이디입니다.") from exc
            raise

    def authenticate(self, *, username: str, password: str) -> User:
        if len(password) > MAX_PASSWORD_SIZE:
            raise AppError("아이디 또는 비밀번호가 올바르지 않습니다.", status_code=401)
        user = self.users.get_by_username(username.strip().lower())
        if not user or not user.password_hash:
            raise AppError("아이디 또는 비밀번호가 올바르지 않습니다.", status_code=401)
        if not password_context.verify(password, user.password_hash):
            raise AppError("아이디 또는 비밀번호가 올바르지 않습니다.", status_code=401)
        return user

    def get_or_create_oauth_user(
        self,
        *,
        provider: str,
        subject: str,
        suggested_username: str,
        display_name: str,
    ) -> User:
        existing = self.users.get_by_oauth_identity(provider, subject)
        if existing:
            return existing

        base = re.sub(r"[^a-zA-Z0-9_]", "_", suggested_username.lower()).strip("_")
        if len(base) < 3:
            base = f"{provider}_user"
        base = base[:40]
        username = base
        suffix = 1
        while True:
            while self.users.get_by_username(username):
                suffix += 1
                username = f"{base}_{suffix}"[:50]
            try:
                return self.users.create(
                    username=username,
                    display_name=display_name[:80] or username,
                    password_hash=None,
                    oauth_provider=provider,
                    oauth_subject=subject,
                )
            except IntegrityError:
                existing = self.users.get_by_oauth_identity(provider, subject)
                if existing:
                    return existing
                if not self.users.get_by_username(username):
                    raise

    def ensure_test_account(self) -> User:
        existing = self.users.get_by_username("demo")
        if existing:
            return existing
        return self.register(
            username="demo",
            display_name="데모 사용자",
            password="demo1234",
        )


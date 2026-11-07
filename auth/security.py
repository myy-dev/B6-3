from __future__ import annotations

import hmac
import secrets

from fastapi import Request

from core.exceptions import AppError


def start_session(request: Request, user_id: int) -> None:
    request.session.clear()
    request.session["user_id"] = user_id


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not isinstance(token, str):
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def validate_csrf(request: Request, submitted_token: str) -> None:
    expected = request.session.get("csrf_token")
    if not isinstance(expected, str) or not hmac.compare_digest(
        expected.encode("utf-8"), submitted_token.encode("utf-8")
    ):
        raise AppError("요청 검증에 실패했습니다. 페이지를 새로고침해 주세요.", status_code=403)


def safe_next_url(value: str | None, *, default: str = "/app/projects") -> str:
    if not value or not value.startswith("/") or value.startswith("//"):
        return default
    return value


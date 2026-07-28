from __future__ import annotations

import hmac
import secrets

from fastapi import Request

from exceptions import AppError


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not isinstance(token, str):
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def validate_csrf(request: Request, submitted_token: str) -> None:
    expected = request.session.get("csrf_token")
    if not isinstance(expected, str) or not hmac.compare_digest(
        expected, submitted_token
    ):
        raise AppError("요청 검증에 실패했습니다. 페이지를 새로고침해 주세요.", status_code=403)


def safe_next_url(value: str | None, *, default: str = "/app/projects") -> str:
    if not value or not value.startswith("/") or value.startswith("//"):
        return default
    return value


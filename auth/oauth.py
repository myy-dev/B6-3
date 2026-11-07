from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from core.config import settings
from core.exceptions import AppError


GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"


def github_authorize_url(*, state: str) -> str:
    if not settings.github_client_id or not settings.github_client_secret:
        raise AppError(
            "GitHub 로그인이 설정되지 않았습니다. 관리자에게 문의해 주세요.",
            status_code=503,
        )
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode({'client_id': settings.github_client_id, 'state': state, 'scope': 'read:user'})}"


def _json_request(request: Request) -> dict[str, object]:
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed trusted URLs
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AppError("GitHub 인증 서버와 통신하지 못했습니다.", status_code=502) from exc


def fetch_github_user(*, code: str) -> dict[str, str]:
    if not settings.github_client_id or not settings.github_client_secret:
        raise AppError("GitHub 로그인이 설정되지 않았습니다.", status_code=503)

    token_body = urlencode(
        {
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret,
            "code": code,
        }
    ).encode("utf-8")
    token_response = _json_request(
        Request(
            GITHUB_TOKEN_URL,
            data=token_body,
            headers={"Accept": "application/json", "User-Agent": "FlowTask"},
            method="POST",
        )
    )
    access_token = token_response.get("access_token")
    if not isinstance(access_token, str):
        raise AppError("GitHub 인증 코드를 교환하지 못했습니다.", status_code=401)

    profile = _json_request(
        Request(
            GITHUB_USER_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "FlowTask",
            },
        )
    )
    subject = profile.get("id")
    login = profile.get("login")
    name = profile.get("name")
    if not isinstance(subject, int) or not isinstance(login, str):
        raise AppError("GitHub 사용자 정보를 확인하지 못했습니다.", status_code=502)
    return {
        "subject": str(subject),
        "username": login,
        "display_name": name if isinstance(name, str) and name else login,
    }


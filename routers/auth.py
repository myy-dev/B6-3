from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import RedirectResponse

from auth.dependencies import CurrentUser, DbSession, OptionalUser
from auth.oauth import fetch_github_user, github_authorize_url
from auth.security import safe_next_url, validate_csrf
from exceptions import AppError
from services import AuthService
from ui import add_flash, render


router = APIRouter()


@router.get("/login", name="login_form")
def login_form(
    request: Request,
    user: OptionalUser,
    next_url: Annotated[str | None, Query(alias="next")] = None,
):
    if user:
        return RedirectResponse("/app/projects", status_code=303)
    return render(
        request,
        "login.html",
        user=None,
        next_url=safe_next_url(next_url),
        error=None,
    )


@router.post("/login", name="login")
def login(
    request: Request,
    db: DbSession,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    csrf: Annotated[str, Form()],
    next_url: Annotated[str, Form()] = "/app/projects",
):
    validate_csrf(request, csrf)
    try:
        user = AuthService(db).authenticate(username=username, password=password)
    except AppError as exc:
        return render(
            request,
            "login.html",
            user=None,
            status_code=exc.status_code,
            next_url=safe_next_url(next_url),
            error=exc.message,
            username=username,
        )
    request.session.clear()
    request.session["user_id"] = user.id
    add_flash(request, f"{user.display_name}님, 다시 오신 것을 환영합니다.")
    return RedirectResponse(safe_next_url(next_url), status_code=303)


@router.get("/signup", name="signup_form")
def signup_form(request: Request, user: OptionalUser):
    if user:
        return RedirectResponse("/app/projects", status_code=303)
    return render(request, "signup.html", user=None, error=None)


@router.post("/signup", name="signup")
def signup(
    request: Request,
    db: DbSession,
    username: Annotated[str, Form()],
    display_name: Annotated[str, Form()],
    password: Annotated[str, Form()],
    csrf: Annotated[str, Form()],
):
    validate_csrf(request, csrf)
    try:
        user = AuthService(db).register(
            username=username,
            display_name=display_name,
            password=password,
        )
    except AppError as exc:
        return render(
            request,
            "signup.html",
            user=None,
            status_code=exc.status_code,
            error=exc.message,
            username=username,
            display_name=display_name,
        )
    request.session.clear()
    request.session["user_id"] = user.id
    add_flash(request, "회원가입이 완료되었습니다. 첫 프로젝트를 만들어 보세요.")
    return RedirectResponse("/app/projects", status_code=303)


@router.post("/logout", name="logout")
def logout(
    request: Request,
    _user: CurrentUser,
    csrf: Annotated[str, Form()],
):
    validate_csrf(request, csrf)
    request.session.clear()
    request.session["flash"] = {
        "message": "안전하게 로그아웃되었습니다.",
        "category": "success",
    }
    return RedirectResponse("/", status_code=303)


@router.get("/auth/github", name="github_login")
def github_login(request: Request):
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    return RedirectResponse(github_authorize_url(state=state), status_code=302)


@router.get("/auth/github/callback", name="github_callback")
def github_callback(
    request: Request,
    db: DbSession,
    code: str = "",
    state: str = "",
):
    expected_state = request.session.pop("oauth_state", None)
    if not expected_state or not secrets.compare_digest(expected_state, state):
        raise AppError("소셜 로그인 요청 상태가 올바르지 않습니다.", status_code=401)
    if not code:
        raise AppError("GitHub에서 인증 코드를 전달받지 못했습니다.", status_code=401)

    profile = fetch_github_user(code=code)
    user = AuthService(db).get_or_create_oauth_user(
        provider="github",
        subject=profile["subject"],
        suggested_username=profile["username"],
        display_name=profile["display_name"],
    )
    request.session.clear()
    request.session["user_id"] = user.id
    add_flash(request, "GitHub 계정으로 로그인했습니다.")
    return RedirectResponse("/app/projects", status_code=303)

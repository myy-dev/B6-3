from __future__ import annotations

from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from config import settings
from database import SessionLocal, create_tables
from exceptions import AppError, AuthenticationRequired
from routers import auth_router, projects_router, web_router
from services import AuthService
from ui import render


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_tables()
    with SessionLocal() as db:
        AuthService(db).ensure_test_account()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="flowtask_session",
    same_site="lax",
    https_only=settings.session_https_only,
    max_age=60 * 60 * 8,
)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(web_router)
app.include_router(auth_router)
app.include_router(projects_router)


@app.exception_handler(AuthenticationRequired)
async def authentication_required_handler(
    request: Request, _exc: AuthenticationRequired
):
    next_url = quote(request.url.path, safe="/")
    return RedirectResponse(f"/login?next={next_url}", status_code=303)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return render(
        request,
        "error.html",
        status_code=exc.status_code,
        title="요청을 처리할 수 없습니다",
        message=exc.message,
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    message = "요청한 페이지를 찾을 수 없습니다." if exc.status_code == 404 else str(exc.detail)
    return render(
        request,
        "error.html",
        status_code=exc.status_code,
        title=f"오류 {exc.status_code}",
        message=message,
    )

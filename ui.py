from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from auth.security import csrf_token
from models import User


templates = Jinja2Templates(directory="templates")


def add_flash(request: Request, message: str, *, category: str = "success") -> None:
    request.session["flash"] = {"message": message, "category": category}


def render(
    request: Request,
    template_name: str,
    *,
    user: User | None = None,
    status_code: int = 200,
    **context: Any,
) -> HTMLResponse:
    payload = {
        "request": request,
        "app_name": "FlowTask",
        "current_user": user,
        "csrf_token": csrf_token(request),
        "flash": request.session.pop("flash", None),
        **context,
    }
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=payload,
        status_code=status_code,
    )


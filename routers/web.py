from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from auth.dependencies import OptionalUser
from core.ui import render


router = APIRouter()


@router.get("/", name="home")
def home(request: Request, user: OptionalUser):
    return render(request, "home.html", user=user)


@router.get("/health", name="health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})

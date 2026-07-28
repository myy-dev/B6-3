from routers.auth import router as auth_router
from routers.projects import router as projects_router
from routers.web import router as web_router

__all__ = ["auth_router", "projects_router", "web_router"]


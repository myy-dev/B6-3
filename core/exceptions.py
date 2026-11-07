from __future__ import annotations


class AppError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AuthenticationRequired(AppError):
    def __init__(self, message: str = "로그인이 필요한 기능입니다.") -> None:
        super().__init__(message, status_code=401)


class NotFoundError(AppError):
    def __init__(self, message: str = "요청한 데이터를 찾을 수 없습니다.") -> None:
        super().__init__(message, status_code=404)


class ForbiddenError(AppError):
    def __init__(self, message: str = "이 데이터에 접근할 권한이 없습니다.") -> None:
        super().__init__(message, status_code=403)


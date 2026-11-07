class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, extra: dict | None = None, headers: dict | None = None):
        super().__init__(message)
        self.message = message
        self.extra = extra or {}
        self.headers = headers or {}


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"

    def __init__(self, message: str):
        super().__init__(message, headers={"WWW-Authenticate": "Bearer"})


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, retry_after: int):
        super().__init__(
            f"Too many requests. Please wait {retry_after} seconds.",
            extra={"retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


class AssistantUnavailable(AppError):
    status_code = 503
    code = "assistant_unavailable"

    def __init__(self):
        super().__init__("The assistant is not configured yet. Check the API keys in .env.")

import os

from fastapi import HTTPException, Request


ACCESS_COOKIE_NAME = "novaq_access_code"


def get_access_code() -> str:
    return os.getenv("ACCESS_CODE", "novaq-demo-access")


def is_access_enabled() -> bool:
    return os.getenv("ACCESS_CONTROL_ENABLED", "true").lower() in ["1", "true", "yes", "on"]


def validate_access_code(code: str | None) -> bool:
    if not is_access_enabled():
        return True
    if not code:
        return False
    return code == get_access_code()


def get_code_from_request(request: Request) -> str | None:
    header_code = request.headers.get("X-Access-Code")
    if header_code:
        return header_code

    query_code = request.query_params.get("access_code")
    if query_code:
        return query_code

    return request.cookies.get(ACCESS_COOKIE_NAME)


def require_access(request: Request) -> None:
    if not is_access_enabled():
        return None
    if validate_access_code(get_code_from_request(request)):
        return None
    raise HTTPException(status_code=401, detail="Access code required")


def has_access(request: Request) -> bool:
    return validate_access_code(get_code_from_request(request))

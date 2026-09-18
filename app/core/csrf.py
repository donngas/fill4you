import hmac
import secrets

from fastapi import Form, HTTPException, Request

SESSION_KEY = "csrf_token"


def get_csrf_token(request: Request) -> str:
    token = request.session.get(SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[SESSION_KEY] = token
    return token


def require_csrf(request: Request, csrf_token: str = Form("")) -> None:
    expected = request.session.get(SESSION_KEY)
    if not expected or not hmac.compare_digest(expected, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

import os
from fastapi import Request
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

COOKIE_NAME = "news_session"
COOKIE_MAX_AGE = 48 * 3600
_SECRET_KEY = os.environ["SECRET_KEY"]
_signer = URLSafeTimedSerializer(_SECRET_KEY)

templates = Jinja2Templates(directory="app/web/templates")


def make_session_cookie() -> str:
    return _signer.dumps("authenticated")


def check_auth(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False
    try:
        _signer.loads(token, max_age=COOKIE_MAX_AGE)
        return True
    except (SignatureExpired, BadSignature):
        return False

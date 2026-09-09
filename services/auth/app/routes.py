from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pawprints_common.errors import error_response
from pawprints_common.jwt import JWTValidationError, verify_access_token

from app.config import Settings, get_settings
from app.db import get_db
from app.models import RefreshToken, User
from app.passwords import PasswordPolicyError, hash_password, verify_password
from app.tokens import create_access_token, hash_refresh_token, new_refresh_token, public_key_from_private_key, utc_now


router = APIRouter(prefix="/api/v1/auth")
REFRESH_COOKIE_NAME = "refresh_token"


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise ValueError("invalid email")
    return normalized


def user_payload(user: User) -> dict[str, str | None]:
    return {"id": str(user.id), "email": user.email, "display_name": user.display_name}


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    kwargs: dict[str, object] = {
        "key": REFRESH_COOKIE_NAME,
        "value": token,
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "path": "/api/v1/auth",
    }
    if settings.cookie_domain:
        kwargs["domain"] = settings.cookie_domain
    response.set_cookie(**kwargs)


def clear_refresh_cookie(response: Response, settings: Settings) -> None:
    kwargs: dict[str, object] = {
        "key": REFRESH_COOKIE_NAME,
        "value": "",
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "path": "/api/v1/auth",
        "max_age": 0,
    }
    if settings.cookie_domain:
        kwargs["domain"] = settings.cookie_domain
    response.set_cookie(**kwargs)


def session_response(user: User, refresh_token: str, response: Response, settings: Settings, status_code: int = 200):
    no_store(response)
    set_refresh_cookie(response, refresh_token, settings)
    response.status_code = status_code
    return {
        "access_token": create_access_token(user.id, settings),
        "token_type": "Bearer",
        "expires_in": settings.access_token_ttl_minutes * 60,
        "user": user_payload(user),
    }


def make_refresh_session(db: Session, user: User, settings: Settings) -> str:
    token = new_refresh_token()
    now = utc_now()
    db.add(
        RefreshToken(
            id=uuid4(),
            user_id=user.id,
            token_hash=hash_refresh_token(token),
            created_at=now,
            expires_at=now + timedelta(days=settings.refresh_session_ttl_days),
        )
    )
    return token


def auth_error(response: Response, code: str, message: str, status_code: int, request: Request):
    no_store(response)
    result = error_response(code, message, status_code, request.headers.get("X-Request-Id", ""))
    result.headers["Cache-Control"] = "no-store"
    return result


def reject_invalid_credentials(request: Request, response: Response):
    return auth_error(response, "invalid_credentials", "Invalid credentials.", 401, request)


def validate_origin(request: Request, response: Response, settings: Settings):
    origin = request.headers.get("origin")
    if origin not in settings.allowed_origins:
        return auth_error(response, "origin_not_allowed", "Origin is not allowed.", 403, request)
    return None


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    try:
        email = normalize_email(payload.email)
        user = User(id=uuid4(), email=email, password_hash=hash_password(payload.password), display_name=payload.display_name, created_at=utc_now())
        db.add(user)
        refresh_token = make_refresh_session(db, user, settings)
        db.commit()
    except (PasswordPolicyError, ValueError):
        db.rollback()
        return auth_error(response, "validation_failed", "Some fields are invalid.", 422, request)
    except IntegrityError:
        db.rollback()
        return auth_error(response, "email_already_registered", "Email is already registered.", 409, request)
    return session_response(user, refresh_token, response, settings, status.HTTP_201_CREATED)


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    try:
        email = normalize_email(payload.email)
    except ValueError:
        return reject_invalid_credentials(request, response)
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        return reject_invalid_credentials(request, response)
    refresh_token = make_refresh_session(db, user, settings)
    db.commit()
    return session_response(user, refresh_token, response, settings)


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    origin_error = validate_origin(request, response, settings)
    if origin_error is not None:
        return origin_error
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        return auth_error(response, "invalid_refresh_token", "Refresh session is invalid.", 401, request)

    now = utc_now()
    token_hash = hash_refresh_token(token)
    refresh_row = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .with_for_update()
    )
    if refresh_row is None or refresh_row.revoked_at is not None or refresh_row.expires_at <= now:
        db.rollback()
        return auth_error(response, "invalid_refresh_token", "Refresh session is invalid.", 401, request)

    user = db.get(User, refresh_row.user_id)
    if user is None:
        db.rollback()
        return auth_error(response, "invalid_refresh_token", "Refresh session is invalid.", 401, request)

    replacement = new_refresh_token()
    replacement_row = RefreshToken(
        id=uuid4(),
        user_id=user.id,
        token_hash=hash_refresh_token(replacement),
        created_at=now,
        expires_at=refresh_row.expires_at,
    )
    db.add(replacement_row)
    db.flush()
    refresh_row.revoked_at = now
    refresh_row.replaced_by_token_id = replacement_row.id
    db.commit()
    return session_response(user, replacement, response, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    origin_error = validate_origin(request, response, settings)
    if origin_error is not None:
        return origin_error
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if token:
        refresh_row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token)).with_for_update())
        if refresh_row is not None and refresh_row.revoked_at is None:
            refresh_row.revoked_at = utc_now()
            db.commit()
    clear_refresh_cookie(response, settings)
    no_store(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return None


@router.get("/me")
def me(request: Request, authorization: str | None = Header(default=None), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    if not authorization or not authorization.startswith("Bearer "):
        return error_response("not_authenticated", "Authentication is required.", 401, request.headers.get("X-Request-Id", ""))
    try:
        authenticated = verify_access_token(
            authorization.removeprefix("Bearer "),
            public_key_from_private_key(settings),
            settings.jwt_issuer,
            settings.jwt_audience,
        )
        user_id = authenticated.user_id
    except JWTValidationError:
        return error_response("not_authenticated", "Authentication is required.", 401, request.headers.get("X-Request-Id", ""))
    user = db.get(User, user_id)
    if user is None:
        return error_response("not_authenticated", "Authentication is required.", 401, request.headers.get("X-Request-Id", ""))
    return user_payload(user)

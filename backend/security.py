"""Слой безопасности: пароли, JWT, RBAC-зависимости, OTP, rate limiting, CSRF.

Это критический файл системы авторизации — здесь сосредоточена вся логика
проверки токенов, ролей и защита от злоупотреблений.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import RateLimitEvent, RefreshToken, Role, User, VerificationCode

# argon2 — современный, устойчивый к подбору алгоритм хэширования паролей
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# auto_error=False: сами выдаём 401, чтобы сообщения были единообразны
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

REFRESH_COOKIE = "da_refresh"
CSRF_COOKIE = "da_csrf"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
#  ПАРОЛИ
# --------------------------------------------------------------------------
def hash_password(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    return pwd_context.verify(raw, hashed)


# --------------------------------------------------------------------------
#  JWT ACCESS-TOKEN
# --------------------------------------------------------------------------
def create_access_token(user: User) -> str:
    expire = _now() + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "type": "access",
        "iat": int(_now().timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Невалидный или просроченный токен")
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный тип токена")
    return payload


# --------------------------------------------------------------------------
#  REFRESH-TOKEN (непрозрачный, хранится в БД в виде sha256-хэша, с ротацией)
# --------------------------------------------------------------------------
def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def issue_refresh_token(db: Session, user: User, request: Request) -> str:
    raw = secrets.token_urlsafe(48)
    rt = RefreshToken(
        user_id=user.id,
        token_hash=_sha256(raw),
        user_agent=(request.headers.get("user-agent") or "")[:255],
        ip_address=request.client.host if request.client else None,
        expires_at=_now() + timedelta(days=settings.REFRESH_TOKEN_DAYS),
    )
    db.add(rt)
    db.commit()
    return raw


def rotate_refresh_token(db: Session, raw: str, request: Request) -> tuple[User, str]:
    """Проверяет refresh-токен, отзывает старый и выдаёт новый (token rotation)."""
    rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _sha256(raw)))
    if not rt or rt.revoked_at is not None or rt.expires_at < _now().replace(tzinfo=None):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Сессия недействительна, войдите снова")
    user = db.get(User, rt.user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Пользователь недоступен")
    rt.revoked_at = _now().replace(tzinfo=None)
    db.commit()
    new_raw = issue_refresh_token(db, user, request)
    return user, new_raw


def revoke_refresh_token(db: Session, raw: str) -> None:
    rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _sha256(raw)))
    if rt and rt.revoked_at is None:
        rt.revoked_at = _now().replace(tzinfo=None)
        db.commit()


# --------------------------------------------------------------------------
#  OTP / коды подтверждения (хранятся в виде хэша)
# --------------------------------------------------------------------------
def generate_email_token() -> str:
    return secrets.token_urlsafe(32)


def store_verification_code(db: Session, user: User, channel, raw_code: str, ttl_minutes: int = 15) -> None:
    # инвалидируем прежние неиспользованные коды этого канала
    db.execute(
        delete(VerificationCode).where(
            VerificationCode.user_id == user.id,
            VerificationCode.channel == channel,
            VerificationCode.consumed_at.is_(None),
        )
    )
    db.add(VerificationCode(
        user_id=user.id,
        channel=channel,
        code_hash=_sha256(raw_code),
        expires_at=_now().replace(tzinfo=None) + timedelta(minutes=ttl_minutes),
    ))
    db.commit()


def consume_verification_code(db: Session, user: User, channel, raw_code: str) -> bool:
    vc = db.scalar(
        select(VerificationCode)
        .where(
            VerificationCode.user_id == user.id,
            VerificationCode.channel == channel,
            VerificationCode.consumed_at.is_(None),
        )
        .order_by(VerificationCode.id.desc())
    )
    if not vc:
        return False
    if vc.expires_at < _now().replace(tzinfo=None) or vc.attempts >= 5:
        return False
    vc.attempts += 1
    if vc.code_hash != _sha256(raw_code):
        db.commit()
        return False
    vc.consumed_at = _now().replace(tzinfo=None)
    db.commit()
    return True


# --------------------------------------------------------------------------
#  RATE LIMITING (скользящее окно на основе таблицы rate_limit_events)
# --------------------------------------------------------------------------
def rate_limit(db: Session, scope_key: str, max_events: int, window_minutes: int) -> None:
    window_start = _now().replace(tzinfo=None) - timedelta(minutes=window_minutes)
    count = db.scalar(
        select(func.count(RateLimitEvent.id)).where(
            RateLimitEvent.scope_key == scope_key,
            RateLimitEvent.created_at >= window_start,
        )
    ) or 0
    if count >= max_events:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Слишком много запросов. Попробуйте позже.",
        )
    db.add(RateLimitEvent(scope_key=scope_key))
    db.commit()


# --------------------------------------------------------------------------
#  CSRF (double-submit cookie для cookie-эндпоинтов: refresh/logout)
# --------------------------------------------------------------------------
def generate_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def verify_csrf(
    x_csrf_token: str | None = Header(default=None),
    da_csrf: str | None = Cookie(default=None),
) -> None:
    if not da_csrf or not x_csrf_token or not secrets.compare_digest(da_csrf, x_csrf_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF-проверка не пройдена")


# --------------------------------------------------------------------------
#  reCAPTCHA
# --------------------------------------------------------------------------
async def verify_recaptcha(token: str | None) -> None:
    if not settings.RECAPTCHA_ENABLED:
        return
    if not token:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Не пройдена проверка reCAPTCHA")
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": settings.RECAPTCHA_SECRET, "response": token},
        )
    if not resp.json().get("success"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Не пройдена проверка reCAPTCHA")


# --------------------------------------------------------------------------
#  ЗАВИСИМОСТИ: текущий пользователь + RBAC
# --------------------------------------------------------------------------
def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется авторизация")
    payload = decode_access_token(token)
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Пользователь не найден или заблокирован")
    return user


def get_verified_user(user: User = Depends(get_current_user)) -> User:
    """Доступ к кабинетам только после подтверждения email И телефона."""
    if not user.is_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Подтвердите email и телефон, чтобы продолжить",
        )
    return user


def require_role(*roles: Role):
    """Фабрика RBAC-зависимостей. Использование: Depends(require_role(Role.admin))."""
    allowed = set(roles)

    def checker(user: User = Depends(get_verified_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Недостаточно прав для этого действия",
            )
        return user

    return checker

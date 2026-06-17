"""Роутер авторизации: регистрация, вход, refresh, выход, подтверждение, Google OAuth.

Все cookie — httpOnly + SameSite=strict; refresh-токен ротируется при каждом обновлении;
на отправку кодов и вход навешан rate limiting; регистрация защищена reCAPTCHA.
"""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

import security as sec
import services as svc
from config import settings
from database import get_db
from models import Channel, Role, StudentProfile, User
from schemas import LoginIn, MeOut, RegisterIn, TokenOut, VerifyEmailIn

router = APIRouter(prefix="/api/auth", tags=["auth"])


# --------------------------------------------------------------------------
#  Вспомогательные функции для cookie
# --------------------------------------------------------------------------
def _set_auth_cookies(response: Response, refresh_raw: str) -> str:
    csrf = sec.generate_csrf_token()
    response.set_cookie(
        sec.REFRESH_COOKIE, refresh_raw,
        httponly=True, secure=settings.COOKIE_SECURE, samesite="strict",
        max_age=settings.REFRESH_TOKEN_DAYS * 86400, path="/api/auth",
    )
    # CSRF-cookie доступна JS (double-submit): фронт зеркалит её в заголовок X-CSRF-Token
    response.set_cookie(
        sec.CSRF_COOKIE, csrf,
        httponly=False, secure=settings.COOKIE_SECURE, samesite="strict",
        max_age=settings.REFRESH_TOKEN_DAYS * 86400, path="/",
    )
    return csrf


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(sec.REFRESH_COOKIE, path="/api/auth")
    response.delete_cookie(sec.CSRF_COOKIE, path="/")


def _next_student_code(db: Session) -> str:
    count = db.query(StudentProfile).count()
    return f"id_{count + 1:05d}"


def _send_codes(db: Session, user: User) -> None:
    # подтверждение только по email (SMS отключён)
    email_token = sec.generate_email_token()
    sec.store_verification_code(db, user, Channel.email, email_token)
    svc.send_verification_email(user.email, email_token)


# --------------------------------------------------------------------------
#  РЕГИСТРАЦИЯ
# --------------------------------------------------------------------------
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterIn, request: Request, db: Session = Depends(get_db)):
    await sec.verify_recaptcha(data.recaptcha_token)

    ip = request.client.host if request.client else "unknown"
    sec.rate_limit(db, f"register:ip:{ip}", max_events=5, window_minutes=60)

    if db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email уже зарегистрирован")
    if db.scalar(select(User).where(User.phone == data.phone)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Телефон уже зарегистрирован")

    user = User(
        email=data.email,
        phone=data.phone,
        password_hash=sec.hash_password(data.password),
        role=Role.student,
        is_active=False,  # новые регистрации ждут подтверждения администратором
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # профиль студента по умолчанию
    db.add(StudentProfile(
        user_id=user.id, student_code=_next_student_code(db),
        full_name=data.full_name, course=1,
    ))
    db.commit()

    _send_codes(db, user)
    return {
        "detail": "Регистрация принята. Подтвердите email и дождитесь подтверждения администратором.",
        "user_id": user.id,
    }


# --------------------------------------------------------------------------
#  ВХОД
# --------------------------------------------------------------------------
@router.post("/login", response_model=TokenOut)
async def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    await sec.verify_recaptcha(data.recaptcha_token)

    ip = request.client.host if request.client else "unknown"
    sec.rate_limit(db, f"login:ip:{ip}", settings.LOGIN_MAX_PER_15MIN, 15)

    user = db.scalar(select(User).where(User.email == data.email))
    # одинаковая ошибка для несуществующего и неверного пароля (no user enumeration)
    if not user or not sec.verify_password(data.password, user.password_hash):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= 5:
                user.locked_until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=15)
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")

    if user.locked_until and user.locked_until > datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(status.HTTP_423_LOCKED, "Аккаунт временно заблокирован, попробуйте позже")
    if not user.is_active:
        # код ошибки — фронт переведёт на язык пользователя
        raise HTTPException(status.HTTP_403_FORBIDDEN, "pending_approval")
    if not user.is_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Подтвердите email перед входом")

    user.failed_logins = 0
    user.locked_until = None
    db.commit()

    refresh_raw = sec.issue_refresh_token(db, user, request)
    csrf = _set_auth_cookies(response, refresh_raw)
    response.headers["X-CSRF-Token"] = csrf
    return TokenOut(
        access_token=sec.create_access_token(user),
        expires_in=settings.ACCESS_TOKEN_MINUTES * 60,
    )


# --------------------------------------------------------------------------
#  REFRESH (ротация) и LOGOUT — защищены CSRF
# --------------------------------------------------------------------------
@router.post("/refresh", response_model=TokenOut, dependencies=[Depends(sec.verify_csrf)])
def refresh(request: Request, response: Response,
            da_refresh: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    if not da_refresh:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Нет refresh-токена")
    user, new_raw = sec.rotate_refresh_token(db, da_refresh, request)
    csrf = _set_auth_cookies(response, new_raw)
    response.headers["X-CSRF-Token"] = csrf
    return TokenOut(
        access_token=sec.create_access_token(user),
        expires_in=settings.ACCESS_TOKEN_MINUTES * 60,
    )


@router.post("/logout", dependencies=[Depends(sec.verify_csrf)])
def logout(response: Response, da_refresh: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    if da_refresh:
        sec.revoke_refresh_token(db, da_refresh)
    _clear_auth_cookies(response)
    return {"detail": "Вы вышли из системы"}


# --------------------------------------------------------------------------
#  ПОДТВЕРЖДЕНИЕ EMAIL / ТЕЛЕФОНА
# --------------------------------------------------------------------------
@router.post("/verify-email")
def verify_email(data: VerifyEmailIn, db: Session = Depends(get_db)):
    # токен email не привязан к сессии — ищем по всем активным кодам
    from models import VerificationCode
    vc = db.scalar(
        select(VerificationCode)
        .where(VerificationCode.channel == Channel.email,
               VerificationCode.code_hash == sec._sha256(data.token),
               VerificationCode.consumed_at.is_(None))
        .order_by(VerificationCode.id.desc())
    )
    if not vc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Неверный или просроченный токен")
    user = db.get(User, vc.user_id)
    if not sec.consume_verification_code(db, user, Channel.email, data.token):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Токен недействителен")
    user.email_verified = True
    db.commit()
    return {"detail": "Email подтверждён", "email_verified": True, "phone_verified": user.phone_verified}


@router.post("/resend-code")
def resend_code(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    # rate limit на отправку кодов (по пользователю)
    sec.rate_limit(db, f"otp:email:{user.id}", settings.OTP_MAX_PER_HOUR, 60)

    token = sec.generate_email_token()
    sec.store_verification_code(db, user, Channel.email, token)
    svc.send_verification_email(user.email, token)
    return {"detail": "Код отправлен повторно"}


# --------------------------------------------------------------------------
#  GOOGLE OAUTH 2.0
# --------------------------------------------------------------------------
@router.get("/google/login")
def google_login():
    """Старт OAuth: редиректим на Google. state кладём в cookie на ЭТОМ top-level
    переходе — так cookie надёжно доезжает обратно (важно для мобильных/Safari)."""
    if not settings.GOOGLE_CLIENT_ID:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?err=oauth_unconfigured")
    state = secrets.token_urlsafe(16)
    resp = RedirectResponse(url=svc.google_authorize_url(state))
    resp.set_cookie("da_oauth_state", state, httponly=True,
                    secure=settings.COOKIE_SECURE, samesite="lax", max_age=600, path="/api/auth")
    return resp


@router.get("/google/callback")
async def google_callback(code: str, state: str, request: Request,
                          da_oauth_state: str | None = Cookie(default=None),
                          db: Session = Depends(get_db)):
    # ошибки OAuth больше не отдаём сырым JSON — редиректим на /login с понятным кодом
    if not da_oauth_state or not secrets.compare_digest(da_oauth_state, state):
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?err=oauth_failed")

    try:
        info = await svc.google_exchange_code(code)
    except Exception:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?err=oauth_failed")
    email = info.get("email")
    google_id = info.get("sub")
    if not email or not google_id:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?err=oauth_failed")

    user = db.scalar(select(User).where(User.google_id == google_id)) or \
        db.scalar(select(User).where(User.email == email))
    # без авторегистрации: незнакомый аккаунт отправляем на регистрацию (код для фронта)
    if not user:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?err=account_not_found")
    # привязываем Google к существующему аккаунту (первый вход через Google)
    if not user.google_id:
        user.google_id = google_id
        user.email_verified = True
        db.commit()
    # новые/неодобренные аккаунты не пускаем до подтверждения админом
    if not user.is_active:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?err=pending_approval")

    refresh_raw = sec.issue_refresh_token(db, user, request)
    # отдаём на фронт через redirect; фронт затем дёрнет /refresh для получения access
    resp = RedirectResponse(url=f"{settings.FRONTEND_URL}/oauth-done")
    csrf = _set_auth_cookies(resp, refresh_raw)
    resp.headers["X-CSRF-Token"] = csrf
    resp.delete_cookie("da_oauth_state", path="/api/auth")
    return resp


# --------------------------------------------------------------------------
#  ТЕКУЩИЙ ПОЛЬЗОВАТЕЛЬ
# --------------------------------------------------------------------------
@router.get("/me", response_model=MeOut)
def me(user: User = Depends(sec.get_current_user), db: Session = Depends(get_db)):
    from models import TeacherDiscipline
    discipline_ids = []
    if user.role == Role.teacher:
        discipline_ids = list(db.scalars(
            select(TeacherDiscipline.discipline_id).where(TeacherDiscipline.teacher_user_id == user.id)
        ))
    return MeOut(
        user=user,
        student_profile=user.student_profile,
        teacher_profile=user.teacher_profile,
        discipline_ids=discipline_ids,
    )

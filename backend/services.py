"""Сервисы: отправка email, Google OAuth, уведомления, бизнес-логика брони.

В режиме разработки (EMAIL_ENABLED=false) код печатается в консоль —
проект запускается без платных провайдеров.
"""
import smtplib
from email.mime.text import MIMEText
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from models import (
    CourseOffering, Enrollment, EnrollmentStatus, Notification, OfferingStatus, User,
)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


# --------------------------------------------------------------------------
#  EMAIL
# --------------------------------------------------------------------------
def send_email(to: str, subject: str, body: str) -> None:
    if not settings.EMAIL_ENABLED:
        print(f"\n[DEV-EMAIL] To: {to}\nSubject: {subject}\n{body}\n")
        return
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)


def send_verification_email(to: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    send_email(
        to,
        "Подтверждение email — Digital Academy",
        f"Здравствуйте!\n\nПодтвердите ваш email, перейдя по ссылке:\n{link}\n\n"
        f"Ссылка действительна 15 минут.",
    )


# --------------------------------------------------------------------------
#  GOOGLE OAUTH 2.0
# --------------------------------------------------------------------------
def google_authorize_url(state: str) -> str:
    redirect_uri = f"{settings.BACKEND_URL}/api/auth/google/callback"
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def google_exchange_code(code: str) -> dict:
    redirect_uri = f"{settings.BACKEND_URL}/api/auth/google/callback"
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        if token_resp.status_code != 200:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ошибка обмена кода Google")
        access = token_resp.json().get("access_token")
        info_resp = await client.get(
            GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access}"}
        )
    if info_resp.status_code != 200:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Не удалось получить профиль Google")
    return info_resp.json()  # {sub, email, email_verified, name, ...}


# --------------------------------------------------------------------------
#  УВЕДОМЛЕНИЯ
# --------------------------------------------------------------------------
def notify(db: Session, user_id: int, title: str, message: str, type_: str = "info") -> None:
    db.add(Notification(user_id=user_id, title=title, message=message, type=type_))
    db.commit()


# --------------------------------------------------------------------------
#  БРОНИРОВАНИЕ (атомарно: блокируем строку, проверяем места)
# --------------------------------------------------------------------------
def book_offering(db: Session, offering_id: int, student: User) -> Enrollment:
    
    offering = db.scalar(
        select(CourseOffering).where(CourseOffering.id == offering_id).with_for_update()
    )
    if not offering:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Дисциплина для записи не найдена")
    if offering.status != OfferingStatus.open or offering.available_seats <= 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Свободных мест нет")

    # Уникальный индекс на (offering_id, student_user_id): запись может уже существовать
    existing = db.scalar(
        select(Enrollment).where(
            Enrollment.offering_id == offering_id,
            Enrollment.student_user_id == student.id,
        )
    )
    if existing and existing.status == EnrollmentStatus.booked:
        raise HTTPException(status.HTTP_409_CONFLICT, "Вы уже записаны на эту дисциплину")

    offering.available_seats -= 1
    if offering.available_seats == 0:
        offering.status = OfferingStatus.full
    if existing:
        existing.status = EnrollmentStatus.booked  
        enrollment = existing
    else:
        enrollment = Enrollment(offering_id=offering_id, student_user_id=student.id)
        db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    notify(
        db, student.id, "Бронирование подтверждено",
        f"Вы успешно записаны. Осталось мест: {offering.available_seats}.", "booking",
    )
    return enrollment


def cancel_booking(db: Session, offering_id: int, student: User) -> None:
    offering = db.scalar(
        select(CourseOffering).where(CourseOffering.id == offering_id).with_for_update()
    )
    enrollment = db.scalar(
        select(Enrollment).where(
            Enrollment.offering_id == offering_id,
            Enrollment.student_user_id == student.id,
            Enrollment.status == EnrollmentStatus.booked,
        )
    )
    if not offering or not enrollment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Бронь не найдена")
    enrollment.status = EnrollmentStatus.cancelled
    offering.available_seats += 1
    if offering.status == OfferingStatus.full:
        offering.status = OfferingStatus.open
    db.commit()
    notify(db, student.id, "Бронь отменена", "Вы отменили запись на дисциплину.", "booking")

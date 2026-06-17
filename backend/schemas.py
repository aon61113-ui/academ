"""Все Pydantic-схемы (валидация запросов/ответов) в одном файле."""
import re
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from models import EnrollmentStatus, NewsCategory, OfferingStatus, Role

PHONE_RE = re.compile(r"^\+?[1-9]\d{9,14}$")  # E.164


def normalize_phone(v: str) -> str:
    """Приводит номер к виду +7XXXXXXXXXX (ровно 11 цифр).
    8XXXXXXXXXX -> +7XXXXXXXXXX. Любой мусор/неправильная длина — ошибка."""
    digits = re.sub(r"\D", "", v or "")
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if len(digits) != 11 or digits[0] != "7":
        raise ValueError("Номер должен состоять из 11 цифр, например 87011234567 или +77011234567")
    return "+" + digits


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------- AUTH -------------------------
class RegisterIn(BaseModel):
    email: EmailStr
    phone: str
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=150)
    recaptcha_token: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
            raise ValueError("Пароль должен содержать буквы и цифры")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    recaptcha_token: str | None = None


class VerifyEmailIn(BaseModel):
    token: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ------------------------- USERS / PROFILES -------------------------
class UserOut(ORMModel):
    id: int
    email: EmailStr
    phone: str
    role: Role
    email_verified: bool
    phone_verified: bool
    is_active: bool
    created_at: datetime


class StudentProfileOut(ORMModel):
    user_id: int
    student_code: str
    full_name: str
    photo_url: str | None
    gpa: float
    course: int
    birth_year: int | None
    admission_year: int | None
    specialty_id: int | None
    group_id: int | None


class TeacherProfileOut(ORMModel):
    user_id: int
    full_name: str
    photo_url: str | None
    experience_years: int
    academic_degree: str | None
    academic_title: str | None
    bio: str | None


class MeOut(BaseModel):
    user: UserOut
    student_profile: StudentProfileOut | None = None
    teacher_profile: TeacherProfileOut | None = None
    discipline_ids: list[int] = []


# --- admin user management ---
class AdminUserCreate(BaseModel):
    email: EmailStr
    phone: str
    password: str = Field(min_length=8)
    role: Role
    full_name: str

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)


class AdminUserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class AdminProfileUpdate(BaseModel):
    """Редактирование данных пользователя админом (поля опциональны)."""
    email: EmailStr | None = None
    phone: str | None = None
    full_name: str | None = None
    # студент
    gpa: float | None = None
    course: int | None = None
    birth_year: int | None = None
    admission_year: int | None = None
    # преподаватель
    academic_title: str | None = None
    academic_degree: str | None = None
    experience_years: int | None = None
    bio: str | None = None

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        return normalize_phone(v) if v else v


# ------------------------- ACADEMY: schedule / grades -------------------------
class ScheduleEntryOut(ORMModel):
    id: int
    discipline_id: int
    group_id: int
    teacher_user_id: int
    day_of_week: int
    start_time: time
    end_time: time
    room: str | None
    lesson_type: str = "lecture"
    discipline_title: str | None = None
    group_name: str | None = None
    teacher_name: str | None = None


class GradeIn(BaseModel):
    student_user_id: int
    discipline_id: int
    value: float = Field(ge=0, le=100)
    grade_type: str = "current"
    comment: str | None = None


class GradeOut(ORMModel):
    id: int
    student_user_id: int
    discipline_id: int
    teacher_user_id: int
    value: float
    grade_type: str
    comment: str | None
    created_at: datetime
    discipline_title: str | None = None


# ------------------------- NEWS -------------------------
class NewsIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=1)
    category: NewsCategory = NewsCategory.news
    event_date: datetime | None = None
    is_published: bool = True


class NewsOut(ORMModel):
    id: int
    title: str
    body: str
    category: NewsCategory
    author_user_id: int
    event_date: datetime | None
    is_published: bool
    created_at: datetime


# ------------------------- DISCIPLINES / SPECIALTIES -------------------------
class SpecialtyOut(ORMModel):
    id: int
    code: str
    name_ru: str
    name_kz: str
    name_en: str


class DisciplineOut(ORMModel):
    id: int
    title: str
    specialty_id: int
    course: int
    description: str | None


class GroupOut(ORMModel):
    id: int
    name: str
    specialty_id: int
    course: int


# ------------------------- ENROLLMENT (Запись по дисциплинам) -------------------------
class OfferingOut(ORMModel):
    id: int
    discipline_id: int
    teacher_user_id: int
    specialty_id: int
    course: int
    session_date: date
    start_time: time
    room: str | None
    total_seats: int
    available_seats: int
    status: OfferingStatus
    discipline_title: str | None = None
    teacher_name: str | None = None
    specialty_name: str | None = None
    is_booked_by_me: bool = False


class OfferingIn(BaseModel):
    discipline_id: int
    teacher_user_id: int
    specialty_id: int
    course: int
    session_date: date
    start_time: time
    room: str | None = None
    total_seats: int = Field(ge=1, le=500)


class EnrollmentOut(ORMModel):
    id: int
    offering_id: int
    student_user_id: int
    status: EnrollmentStatus
    created_at: datetime


# ------------------------- NOTIFICATIONS -------------------------
class NotificationOut(ORMModel):
    id: int
    title: str
    message: str
    type: str
    is_read: bool
    created_at: datetime

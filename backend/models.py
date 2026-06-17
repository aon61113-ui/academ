"""Все ORM-модели Digital Academy в одном файле (без дробления по сущностям)."""
from datetime import datetime, date, time
from enum import Enum

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, DECIMAL, ForeignKey, Integer,
    SmallInteger, String, Text, Time, UniqueConstraint, func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


# --------------------------------------------------------------------------
#  ENUM'ы (строковые — совпадают с ENUM в schema.sql)
# --------------------------------------------------------------------------
class Role(str, Enum):
    student = "student"
    teacher = "teacher"
    admin = "admin"
    council = "council"


class Channel(str, Enum):
    email = "email"
    phone = "phone"


class NewsCategory(str, Enum):
    news = "news"
    announcement = "announcement"
    event = "event"


class OfferingStatus(str, Enum):
    open = "open"
    full = "full"
    closed = "closed"


class EnrollmentStatus(str, Enum):
    booked = "booked"
    cancelled = "cancelled"


# --------------------------------------------------------------------------
#  СПРАВОЧНИКИ
# --------------------------------------------------------------------------
class Specialty(Base):
    __tablename__ = "specialties"
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name_ru: Mapped[str] = mapped_column(String(120))
    name_kz: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str] = mapped_column(String(120))


class StudentGroup(Base):
    __tablename__ = "student_groups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    specialty_id: Mapped[int] = mapped_column(ForeignKey("specialties.id"))
    course: Mapped[int] = mapped_column(SmallInteger)
    curator_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    specialty: Mapped["Specialty"] = relationship()


# 
#  ЯДРО АВТОРИЗАЦИИ / RBAC
# 
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[Role] = mapped_column(SAEnum(Role), default=Role.student, index=True)
    google_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(SmallInteger, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    student_profile: Mapped["StudentProfile"] = relationship(back_populates="user", uselist=False)
    teacher_profile: Mapped["TeacherProfile"] = relationship(back_populates="user", uselist=False)

    @property
    def is_verified(self) -> bool:
        return self.email_verified  # подтверждение аккаунта только по email (SMS отключён)


class VerificationCode(Base):
    __tablename__ = "verification_codes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel: Mapped[Channel] = mapped_column(SAEnum(Channel))
    code_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RateLimitEvent(Base):
    __tablename__ = "rate_limit_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    scope_key: Mapped[str] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# --------------------------------------------------------------------------
#  ПРОФИЛИ (1:1 c users)
# --------------------------------------------------------------------------
class StudentProfile(Base):
    __tablename__ = "student_profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    student_code: Mapped[str] = mapped_column(String(12), unique=True)
    full_name: Mapped[str] = mapped_column(String(150))
    photo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gpa: Mapped[float] = mapped_column(DECIMAL(3, 2), default=0)
    course: Mapped[int] = mapped_column(SmallInteger)
    birth_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    admission_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    specialty_id: Mapped[int | None] = mapped_column(ForeignKey("specialties.id"), nullable=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("student_groups.id"), nullable=True)

    user: Mapped["User"] = relationship(back_populates="student_profile")
    specialty: Mapped["Specialty"] = relationship()
    group: Mapped["StudentGroup"] = relationship()


class TeacherProfile(Base):
    __tablename__ = "teacher_profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150))
    photo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    experience_years: Mapped[int] = mapped_column(SmallInteger, default=0)
    academic_degree: Mapped[str | None] = mapped_column(String(120), nullable=True)
    academic_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="teacher_profile")



#  УЧЕБНАЯ ЧАСТЬ

class Discipline(Base):
    __tablename__ = "disciplines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    specialty_id: Mapped[int] = mapped_column(ForeignKey("specialties.id"))
    course: Mapped[int] = mapped_column(SmallInteger)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    specialty: Mapped["Specialty"] = relationship()


class TeacherDiscipline(Base):
    __tablename__ = "teacher_disciplines"
    teacher_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id", ondelete="CASCADE"), primary_key=True)


class ScheduleEntry(Base):
    __tablename__ = "schedule_entries"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id"))
    group_id: Mapped[int] = mapped_column(ForeignKey("student_groups.id"))
    teacher_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    day_of_week: Mapped[int] = mapped_column(SmallInteger)  # 1=Пн .. 7=Вс
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    room: Mapped[str | None] = mapped_column(String(40), nullable=True)
    lesson_type: Mapped[str] = mapped_column(String(20), default="lecture")  # lecture|practice|lab

    discipline: Mapped["Discipline"] = relationship()
    group: Mapped["StudentGroup"] = relationship()
    teacher: Mapped["User"] = relationship()


class Grade(Base):
    __tablename__ = "grades"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    student_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id"))
    teacher_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    value: Mapped[float] = mapped_column(DECIMAL(4, 1))
    grade_type: Mapped[str] = mapped_column(String(40), default="current")
    comment: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    discipline: Mapped["Discipline"] = relationship()


# --------------------------------------------------------------------------
#  КОНТЕНТ
# --------------------------------------------------------------------------
class News(Base):
    __tablename__ = "news"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[NewsCategory] = mapped_column(SAEnum(NewsCategory), default=NewsCategory.news, index=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    event_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# --------------------------------------------------------------------------
#  МОДУЛЬ "ЗАПИСЬ ПО ДИСЦИПЛИНАМ"
# --------------------------------------------------------------------------
class CourseOffering(Base):
    __tablename__ = "course_offerings"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id"))
    teacher_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    specialty_id: Mapped[int] = mapped_column(ForeignKey("specialties.id"), index=True)
    course: Mapped[int] = mapped_column(SmallInteger)
    session_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time] = mapped_column(Time)
    room: Mapped[str | None] = mapped_column(String(40), nullable=True)
    total_seats: Mapped[int] = mapped_column(SmallInteger)
    available_seats: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[OfferingStatus] = mapped_column(SAEnum(OfferingStatus), default=OfferingStatus.open)

    discipline: Mapped["Discipline"] = relationship()
    teacher: Mapped["User"] = relationship()
    specialty: Mapped["Specialty"] = relationship()


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("offering_id", "student_user_id", name="uq_offer_student"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    offering_id: Mapped[int] = mapped_column(ForeignKey("course_offerings.id", ondelete="CASCADE"))
    student_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[EnrollmentStatus] = mapped_column(SAEnum(EnrollmentStatus), default=EnrollmentStatus.booked)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    offering: Mapped["CourseOffering"] = relationship()


# --------------------------------------------------------------------------
#  УВЕДОМЛЕНИЯ
# --------------------------------------------------------------------------
class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(150))
    message: Mapped[str] = mapped_column(String(500))
    type: Mapped[str] = mapped_column(String(40), default="info")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

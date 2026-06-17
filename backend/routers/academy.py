"""Роутер учебной части: новости, расписание, справочники, модуль записи по дисциплинам,
уведомления. RBAC применяется на каждом изменяющем эндпоинте."""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

import security as sec
import services as svc
from database import get_db
from models import (
    CourseOffering, Discipline, Enrollment, EnrollmentStatus, News, Notification,
    Role, ScheduleEntry, Specialty, StudentGroup, User,
)
from schemas import (
    DisciplineOut, GroupOut, NewsIn, NewsOut, NotificationOut, OfferingIn,
    OfferingOut, ScheduleEntryOut, SpecialtyOut,
)

router = APIRouter(prefix="/api", tags=["academy"])


# --------------------------------------------------------------------------
#  СПРАВОЧНИКИ (публично)
# --------------------------------------------------------------------------
@router.get("/specialties", response_model=list[SpecialtyOut])
def list_specialties(db: Session = Depends(get_db)):
    return list(db.scalars(select(Specialty).order_by(Specialty.id)))


@router.get("/disciplines", response_model=list[DisciplineOut])
def list_disciplines(
    specialty_id: int | None = Query(default=None),
    course: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(Discipline)
    if specialty_id:
        stmt = stmt.where(Discipline.specialty_id == specialty_id)
    if course:
        stmt = stmt.where(Discipline.course == course)
    return list(db.scalars(stmt.order_by(Discipline.course, Discipline.title)))


@router.get("/groups", response_model=list[GroupOut])
def list_groups(db: Session = Depends(get_db)):
    """Учебные группы (публично) — для фильтра расписания."""
    return list(db.scalars(select(StudentGroup).order_by(StudentGroup.name)))


# --------------------------------------------------------------------------
#  НОВОСТИ / ОБЪЯВЛЕНИЯ / МЕРОПРИЯТИЯ
# --------------------------------------------------------------------------
@router.get("/news", response_model=list[NewsOut])
def list_news(category: str | None = Query(default=None), db: Session = Depends(get_db)):
    stmt = select(News).where(News.is_published.is_(True))
    if category:
        stmt = stmt.where(News.category == category)
    return list(db.scalars(stmt.order_by(News.created_at.desc()).limit(50)))


@router.post("/news", response_model=NewsOut, status_code=status.HTTP_201_CREATED)
def create_news(
    data: NewsIn,
    db: Session = Depends(get_db),
    user: User = Depends(sec.require_role(Role.council, Role.admin)),
):
    news = News(**data.model_dump(), author_user_id=user.id)
    db.add(news)
    db.commit()
    db.refresh(news)
    return news


@router.delete("/news/{news_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_news(
    news_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(sec.require_role(Role.council, Role.admin)),
):
    news = db.get(News, news_id)
    if not news:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Новость не найдена")
    # студсовет может удалять только свои публикации
    if user.role == Role.council and news.author_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Можно удалять только свои публикации")
    db.delete(news)
    db.commit()


# --------------------------------------------------------------------------
#  РАСПИСАНИЕ
# --------------------------------------------------------------------------
def _schedule_to_out(e: ScheduleEntry) -> ScheduleEntryOut:
    out = ScheduleEntryOut.model_validate(e)
    out.discipline_title = e.discipline.title if e.discipline else None
    out.group_name = e.group.name if e.group else None
    out.teacher_name = e.teacher.teacher_profile.full_name if e.teacher and e.teacher.teacher_profile else None
    return out


@router.get("/schedule/public", response_model=list[ScheduleEntryOut])
def schedule_public(
    group_id: int | None = Query(default=None),
    _: User = Depends(sec.get_current_user),  # приватно: доступно только после входа
    db: Session = Depends(get_db),
):
    """Расписание (только для авторизованных). По умолчанию — все группы,
    опционально фильтр по конкретной группе."""
    stmt = select(ScheduleEntry)
    if group_id:
        stmt = stmt.where(ScheduleEntry.group_id == group_id)
    rows = db.scalars(stmt.order_by(ScheduleEntry.day_of_week, ScheduleEntry.start_time)).all()
    return [_schedule_to_out(e) for e in rows]


@router.get("/schedule/today", response_model=list[ScheduleEntryOut])
def schedule_today(user: User = Depends(sec.get_verified_user), db: Session = Depends(get_db)):
    """Студент: «Сегодняшние пары» по своей группе."""
    if user.role != Role.student or not user.student_profile or not user.student_profile.group_id:
        return []
    today = datetime.now().isoweekday()  # 1..7
    rows = db.scalars(select(ScheduleEntry).where(
        ScheduleEntry.group_id == user.student_profile.group_id,
        ScheduleEntry.day_of_week == today,
    ).order_by(ScheduleEntry.start_time)).all()
    return [_schedule_to_out(e) for e in rows]


@router.get("/schedule/week", response_model=list[ScheduleEntryOut])
def schedule_week(user: User = Depends(sec.get_verified_user), db: Session = Depends(get_db)):
    """Преподаватель: своё расписание на неделю. Студент: расписание своей группы."""
    if user.role == Role.teacher:
        stmt = select(ScheduleEntry).where(ScheduleEntry.teacher_user_id == user.id)
    elif user.role == Role.student and user.student_profile and user.student_profile.group_id:
        stmt = select(ScheduleEntry).where(ScheduleEntry.group_id == user.student_profile.group_id)
    else:
        return []
    rows = db.scalars(stmt.order_by(ScheduleEntry.day_of_week, ScheduleEntry.start_time)).all()
    return [_schedule_to_out(e) for e in rows]


# --------------------------------------------------------------------------
#  МОДУЛЬ "ЗАПИСЬ ПО ДИСЦИПЛИНАМ"
# --------------------------------------------------------------------------
def _offering_to_out(o: CourseOffering, my_ids: set[int]) -> OfferingOut:
    out = OfferingOut.model_validate(o)
    out.discipline_title = o.discipline.title if o.discipline else None
    out.specialty_name = o.specialty.name_ru if o.specialty else None
    out.teacher_name = (o.teacher.teacher_profile.full_name
                        if o.teacher and o.teacher.teacher_profile else None)
    out.is_booked_by_me = o.id in my_ids
    return out


@router.get("/offerings", response_model=list[OfferingOut])
def list_offerings(
    specialty_id: int | None = Query(default=None),
    course: int | None = Query(default=None),
    teacher_user_id: int | None = Query(default=None),
    session_date: date | None = Query(default=None),
    student_user_id: int | None = Query(default=None),
    user: User = Depends(sec.get_verified_user),
    db: Session = Depends(get_db),
):
    """Фильтрация по специальности, курсу, преподавателю и дате.
    is_booked_by_me считается относительно текущего пользователя, а для админа —
    относительно выбранного студента (student_user_id)."""
    conds = []
    if specialty_id:
        conds.append(CourseOffering.specialty_id == specialty_id)
    if course:
        conds.append(CourseOffering.course == course)
    if teacher_user_id:
        conds.append(CourseOffering.teacher_user_id == teacher_user_id)
    if session_date:
        conds.append(CourseOffering.session_date == session_date)

    stmt = select(CourseOffering)
    if conds:
        stmt = stmt.where(and_(*conds))
    offerings = db.scalars(stmt.order_by(CourseOffering.session_date, CourseOffering.start_time)).all()

    owner_id = student_user_id if (user.role == Role.admin and student_user_id) else user.id
    my_ids = set(db.scalars(select(Enrollment.offering_id).where(
        Enrollment.student_user_id == owner_id,
        Enrollment.status == EnrollmentStatus.booked,
    )))
    return [_offering_to_out(o, my_ids) for o in offerings]


@router.post("/offerings", response_model=OfferingOut, status_code=status.HTTP_201_CREATED)
def create_offering(
    data: OfferingIn,
    db: Session = Depends(get_db),
    _: User = Depends(sec.require_role(Role.admin)),
):
    offering = CourseOffering(**data.model_dump(), available_seats=data.total_seats)
    db.add(offering)
    db.commit()
    db.refresh(offering)
    return _offering_to_out(offering, set())


def _resolve_student(db: Session, user: User, student_user_id: int | None) -> User:
    """Студент бронирует на себя; админ — на указанного студента (student_user_id)."""
    if user.role == Role.admin:
        if not student_user_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Укажите студента для записи")
        student = db.get(User, student_user_id)
        if not student or student.role != Role.student:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Студент не найден")
        return student
    return user


@router.post("/offerings/{offering_id}/book", response_model=OfferingOut)
def book(
    offering_id: int,
    student_user_id: int | None = Query(default=None),
    user: User = Depends(sec.require_role(Role.student, Role.admin)),
    db: Session = Depends(get_db),
):
    """«Совершить бронь». Студент — на себя, админ — на выбранного студента.
    Места уменьшаются атомарно, студенту шлётся уведомление."""
    student = _resolve_student(db, user, student_user_id)
    svc.book_offering(db, offering_id, student)
    offering = db.get(CourseOffering, offering_id)
    return _offering_to_out(offering, {offering_id})


@router.post("/offerings/{offering_id}/cancel", response_model=OfferingOut)
def cancel(
    offering_id: int,
    student_user_id: int | None = Query(default=None),
    user: User = Depends(sec.require_role(Role.student, Role.admin)),
    db: Session = Depends(get_db),
):
    student = _resolve_student(db, user, student_user_id)
    svc.cancel_booking(db, offering_id, student)
    offering = db.get(CourseOffering, offering_id)
    return _offering_to_out(offering, set())


# --------------------------------------------------------------------------
#  УВЕДОМЛЕНИЯ
# --------------------------------------------------------------------------
@router.get("/notifications", response_model=list[NotificationOut])
def my_notifications(user: User = Depends(sec.get_verified_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Notification).where(Notification.user_id == user.id)
                           .order_by(Notification.created_at.desc()).limit(50)))


@router.post("/notifications/{notif_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(notif_id: int, user: User = Depends(sec.get_verified_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notif_id)
    if not n or n.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Уведомление не найдено")
    n.is_read = True
    db.commit()

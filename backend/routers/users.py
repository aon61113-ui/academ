"""Роутер пользователей: профиль (/me детально), управление пользователями (admin),
выставление оценок (teacher), ограниченный просмотр студентов (council)."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

import security as sec
from database import get_db
from models import (
    CourseOffering, Discipline, Enrollment, Grade, News, Notification, Role, ScheduleEntry,
    StudentGroup, StudentProfile, TeacherDiscipline, TeacherProfile, User,
)
from schemas import (
    AdminProfileUpdate, AdminUserCreate, AdminUserUpdate, GradeIn, GradeOut,
    StudentProfileOut, TeacherProfileOut, UserOut,
)

router = APIRouter(prefix="/api/users", tags=["users"])


# --------------------------------------------------------------------------
#  ПУБЛИЧНЫЙ СПИСОК ПРЕПОДАВАТЕЛЕЙ (для страницы "О преподавателях")
# --------------------------------------------------------------------------
@router.get("/teachers/public", response_model=list[TeacherProfileOut])
def public_teachers(db: Session = Depends(get_db)):
    return list(db.scalars(select(TeacherProfile)))


# --------------------------------------------------------------------------
#  АДМИН: управление пользователями и ролями
# --------------------------------------------------------------------------
@router.get("/admin", response_model=list[UserOut])
def admin_list_users(
    role: Role | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(sec.require_role(Role.admin)),
):
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    return list(db.scalars(stmt.order_by(User.id)))


@router.post("/admin", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    data: AdminUserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(sec.require_role(Role.admin)),
):
    if db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email уже занят")
    user = User(
        email=data.email, phone=data.phone, role=data.role,
        password_hash=sec.hash_password(data.password),
        email_verified=True, phone_verified=True,  # создан админом — считаем проверенным
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # заводим соответствующий профиль
    if data.role == Role.teacher:
        db.add(TeacherProfile(user_id=user.id, full_name=data.full_name))
    elif data.role == Role.student:
        cnt = db.query(StudentProfile).count()
        db.add(StudentProfile(user_id=user.id, student_code=f"id_{cnt + 1:05d}",
                              full_name=data.full_name, course=1))
    db.commit()
    return user


def _profile_payload(u: User) -> dict:
    """Профиль пользователя для админа: сам пользователь + студ./препод. профиль."""
    return {
        "user": UserOut.model_validate(u),
        "student_profile": StudentProfileOut.model_validate(u.student_profile) if u.student_profile else None,
        "teacher_profile": TeacherProfileOut.model_validate(u.teacher_profile) if u.teacher_profile else None,
    }


@router.get("/admin/{user_id}/profile")
def admin_get_profile(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(sec.require_role(Role.admin)),
):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    return _profile_payload(u)


@router.patch("/admin/{user_id}/profile")
def admin_update_profile(
    user_id: int,
    data: AdminProfileUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(sec.require_role(Role.admin)),
):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    d = data.model_dump(exclude_unset=True)

    # данные аккаунта
    if "email" in d and d["email"] != u.email:
        if db.scalar(select(User).where(User.email == d["email"], User.id != u.id)):
            raise HTTPException(status.HTTP_409_CONFLICT, "Email уже занят")
        u.email = d["email"]
    if "phone" in d:
        u.phone = d["phone"]

    # данные профиля по роли
    prof = u.student_profile or u.teacher_profile
    student_fields = ("full_name", "gpa", "course", "birth_year", "admission_year")
    teacher_fields = ("full_name", "academic_title", "academic_degree", "experience_years", "bio")
    fields = student_fields if u.student_profile else teacher_fields if u.teacher_profile else ()
    for f in fields:
        if f in d:
            setattr(prof, f, d[f])

    db.commit()
    db.refresh(u)
    return _profile_payload(u)


@router.patch("/admin/{user_id}", response_model=UserOut)
def admin_update_user(
    user_id: int,
    data: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(sec.require_role(Role.admin)),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        if user.id == admin.id and data.is_active is False:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нельзя деактивировать самого себя")
        user.is_active = data.is_active
    db.commit()
    db.refresh(user)
    return user


@router.delete("/admin/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(sec.require_role(Role.admin)),
):
    """Полное удаление аккаунта со всеми связанными данными (необратимо)."""
    if user_id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нельзя удалить свой аккаунт")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")

    # снимаем кураторство групп (на случай, если FK не SET NULL)
    db.execute(update(StudentGroup).where(StudentGroup.curator_user_id == user_id)
               .values(curator_user_id=None))
    # записи студента на пары
    db.execute(delete(Enrollment).where(Enrollment.student_user_id == user_id))
    # предложения этого преподавателя + записи на них
    offer_ids = list(db.scalars(select(CourseOffering.id).where(CourseOffering.teacher_user_id == user_id)))
    if offer_ids:
        db.execute(delete(Enrollment).where(Enrollment.offering_id.in_(offer_ids)))
        db.execute(delete(CourseOffering).where(CourseOffering.teacher_user_id == user_id))
    # оценки (как студент или как преподаватель), расписание, привязки, новости, уведомления
    db.execute(delete(Grade).where(or_(Grade.student_user_id == user_id, Grade.teacher_user_id == user_id)))
    db.execute(delete(ScheduleEntry).where(ScheduleEntry.teacher_user_id == user_id))
    db.execute(delete(TeacherDiscipline).where(TeacherDiscipline.teacher_user_id == user_id))
    db.execute(delete(News).where(News.author_user_id == user_id))
    db.execute(delete(Notification).where(Notification.user_id == user_id))
    # сам пользователь — через Core delete, чтобы сработал ON DELETE CASCADE БД
    # (профили, refresh-токены, коды подтверждения удалятся автоматически).
    db.execute(delete(User).where(User.id == user_id))
    db.commit()


# --------------------------------------------------------------------------
#  СТУДСОВЕТ: ограниченный просмотр студентов (только ФИО, ID, курс, группа)
# --------------------------------------------------------------------------
@router.get("/students/limited")
def council_students(
    db: Session = Depends(get_db),
    _: User = Depends(sec.require_role(Role.council, Role.admin)),
):
    rows = db.scalars(select(StudentProfile)).all()
    return [
        {"user_id": s.user_id, "student_code": s.student_code, "full_name": s.full_name,
         "course": s.course, "group_id": s.group_id}
        for s in rows
    ]


# --------------------------------------------------------------------------
#  ПРЕПОДАВАТЕЛЬ: выставление оценок
# --------------------------------------------------------------------------
@router.post("/grades", response_model=GradeOut, status_code=status.HTTP_201_CREATED)
def create_grade(
    data: GradeIn,
    db: Session = Depends(get_db),
    teacher: User = Depends(sec.require_role(Role.teacher, Role.admin)),
):
    # препод может ставить оценку только по своим дисциплинам
    if teacher.role == Role.teacher:
        owns = db.scalar(select(TeacherDiscipline).where(
            TeacherDiscipline.teacher_user_id == teacher.id,
            TeacherDiscipline.discipline_id == data.discipline_id,
        ))
        if not owns:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Вы не ведёте эту дисциплину")

    student = db.get(StudentProfile, data.student_user_id)
    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Студент не найден")

    grade = Grade(
        student_user_id=data.student_user_id, discipline_id=data.discipline_id,
        teacher_user_id=teacher.id, value=data.value,
        grade_type=data.grade_type, comment=data.comment,
    )
    db.add(grade)
    db.commit()
    db.refresh(grade)
    disc = db.get(Discipline, grade.discipline_id)
    out = GradeOut.model_validate(grade)
    out.discipline_title = disc.title if disc else None
    return out


@router.get("/teacher/classes")
def teacher_classes(
    teacher: User = Depends(sec.require_role(Role.teacher, Role.admin)),
    db: Session = Depends(get_db),
):
    """Группы, которые ведёт преподаватель: его дисциплины в каждой группе + список
    студентов группы. Нужно, чтобы оценки выставлялись выбором из списка, а не вводом ID."""
    stmt = select(ScheduleEntry.group_id, ScheduleEntry.discipline_id)
    if teacher.role == Role.teacher:
        stmt = stmt.where(ScheduleEntry.teacher_user_id == teacher.id)
    by_group: dict[int, set[int]] = {}
    for gid, did in db.execute(stmt).all():
        by_group.setdefault(gid, set()).add(did)
    if not by_group:
        return []

    groups = {g.id: g for g in db.scalars(
        select(StudentGroup).where(StudentGroup.id.in_(by_group.keys())))}
    all_disc_ids = {d for ids in by_group.values() for d in ids}
    discs = {d.id: d for d in db.scalars(
        select(Discipline).where(Discipline.id.in_(all_disc_ids)))}
    students_by_group: dict[int, list] = {}
    for s in db.scalars(select(StudentProfile).where(
            StudentProfile.group_id.in_(by_group.keys())).order_by(StudentProfile.full_name)):
        students_by_group.setdefault(s.group_id, []).append(s)

    result = []
    for gid, dids in by_group.items():
        g = groups.get(gid)
        if not g:
            continue
        result.append({
            "group_id": gid,
            "group_name": g.name,
            "course": g.course,
            "disciplines": [{"id": d, "title": discs[d].title}
                            for d in sorted(dids) if d in discs],
            "students": [{"user_id": s.user_id, "full_name": s.full_name,
                          "student_code": s.student_code}
                         for s in students_by_group.get(gid, [])],
        })
    result.sort(key=lambda x: x["group_name"])
    return result


@router.get("/grades/me", response_model=list[GradeOut])
def my_grades(user: User = Depends(sec.get_verified_user), db: Session = Depends(get_db)):
    """Студент видит свои оценки."""
    rows = db.scalars(select(Grade).where(Grade.student_user_id == user.id)
                      .order_by(Grade.created_at.desc())).all()
    result = []
    for g in rows:
        out = GradeOut.model_validate(g)
        out.discipline_title = g.discipline.title if g.discipline else None
        result.append(out)
    return result

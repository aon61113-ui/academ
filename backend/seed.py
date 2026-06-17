"""Заполнение БД демо-данными: пользователи всех ролей, группы, дисциплины,
расписание, новости и записи на дисциплины.

Запуск:  python seed.py
Создаёт таблицы (если запускался не SQL-скрипт) и наполняет их.
Демо-пароль у всех: Passw0rd!
"""
from datetime import date, time, timedelta, datetime

from sqlalchemy import select

from database import Base, SessionLocal, engine
from models import (
    CourseOffering, Discipline, News, Role, ScheduleEntry, Specialty,
    StudentGroup, StudentProfile, TeacherDiscipline, TeacherProfile, User,
)
from security import hash_password

DEMO_PASSWORD = "Passw0rd!"

# Сетка времени: 4 пары по 90 мин, строго 08:00–14:00 (короткие перерывы внутри пар).
PAIRS = [
    (time(8, 0), time(9, 30)),
    (time(9, 30), time(11, 0)),
    (time(11, 0), time(12, 30)),
    (time(12, 30), time(14, 0)),
]

# Префиксы названий групп по специальностям.
GROUP_PREFIX = {
    "software": "ПО", "cybersec": "КБ", "data_science": "DS", "qa": "QA", "fullstack": "FS",
}

# Латиница для email студентов по префиксу группы (ПО-21 -> po21@academy.kz).
LATIN_PREFIX = {"ПО": "po", "КБ": "kb", "DS": "ds", "QA": "qa", "FS": "fs"}

# Пул имён для демо-студентов (по одному на группу).
STUDENT_NAMES = [
    "Алихан Сериков", "Аружан Касымова", "Дамир Нургалиев", "Камила Ержанова",
    "Ерасыл Абдрахман", "Жанель Сапарова", "Нурлан Бекжанов", "Аяна Толеген",
    "Санжар Аманжол", "Дильназ Кудайберген", "Тимур Оразов", "Мадина Сейтказы",
    "Бекзат Мукашев", "Айгерим Дюсенова", "Ерлан Кайыр", "Зарина Мусина",
]

# 1 курс — общий для всех специальностей (фундамент).
COURSE1_COMMON = [
    ("Математический анализ", 4), ("Линейная алгебра", 3), ("Дискретная математика", 3),
    ("Основы программирования (Python)", 5), ("Введение в веб (HTML/CSS)", 3), ("Основы тестирования", 2),
]

# Учебный план 2–3 курсов: (предмет, число пар в неделю). Сумма по курсу = 20.
CURRICULUM = {
    "software": {
        2: [("Алгоритмы и структуры данных", 4), ("ООП (Java/C#)", 4), ("Базы данных (SQL)", 4),
            ("Frontend (React/Vue)", 3), ("Компьютерные сети", 2), ("Теория вероятностей", 3)],
        3: [("Архитектура ПО", 4), ("Backend (Node.js/Django/ASP.NET)", 4), ("Командная разработка", 4),
            ("Операционные системы", 3), ("Автоматизация QA", 3), ("Проф. английский", 2)],
    },
    "cybersec": {
        2: [("Алгоритмы и структуры данных", 3), ("ООП (Java/C#)", 3), ("Базы данных (SQL)", 3),
            ("Компьютерные сети (CCNA)", 5), ("Архитектура ПК", 3), ("Теория вероятностей", 3)],
        3: [("Операционные системы", 4), ("Безопасность ОС", 4), ("Пентест", 4),
            ("Backend (Node.js/Django)", 3), ("Архитектура ПО", 3), ("Проф. английский", 2)],
    },
    "data_science": {
        2: [("Алгоритмы и структуры данных", 4), ("ООП (Python)", 3), ("Теория вероятностей", 5),
            ("Базы данных (SQL)", 4), ("Frontend (React/Vue)", 2), ("Компьютерные сети", 2)],
        3: [("Машинное и глубокое обучение (ML/DL)", 5), ("Визуализация данных", 4),
            ("Инженерия данных", 3), ("Математическая статистика", 3),
            ("Backend (API для моделей)", 3), ("Проф. английский", 2)],
    },
    "qa": {
        2: [("Алгоритмы и структуры данных", 3), ("ООП (Java/C#)", 3), ("Базы данных (SQL)", 4),
            ("Техники тест-дизайна", 5), ("Frontend (React/Vue)", 3), ("Компьютерные сети", 2)],
        3: [("Автоматизация UI (Selenium)", 4), ("API-тестирование (Postman)", 4), ("БД для QA", 3),
            ("Backend (основы)", 3), ("Тест-менеджмент", 2), ("Нагрузочное тестирование", 2),
            ("Проф. английский", 2)],
    },
    "fullstack": {
        2: [("Алгоритмы и структуры данных", 3), ("ООП (Java/C#)", 3), ("Базы данных (SQL)", 4),
            ("Frontend (React/Vue)", 5), ("Компьютерные сети", 2), ("Теория вероятностей", 3)],
        3: [("Backend (Node.js/Django)", 4), ("Frontend (React/Next)", 4), ("API-дизайн", 3),
            ("Базы данных (ORM)", 3), ("Развёртывание (ОС)", 2), ("Командный проект", 2),
            ("Проф. английский", 2)],
    },
}


def _make_types(count: int) -> list[str]:
    """Делит пары предмета на типы: ~40% лекций, остальное практика/лаб (баланс ≈40/60)."""
    n_lec = max(1, round(count * 0.4))
    types = ["lecture"] * n_lec
    for i in range(count - n_lec):
        types.append("practice" if i % 2 == 0 else "lab")
    return types


def _interleave(subjects):
    """(предмет, кол-во) -> плоский список (предмет, тип), чередуя предметы,
    чтобы один предмет не шёл несколько раз в один день, а типы (Л/П/Лаб)
    были перемешаны по дням, а не «все лекции в понедельник»."""
    queues = []
    for i, (title, cnt) in enumerate(subjects):
        types = _make_types(cnt)
        r = i % len(types)                 # стаггер: у разных предметов разный стартовый тип
        queues.append((title, types[r:] + types[:r]))
    result = []
    while any(q for _, q in queues):
        for _title, q in queues:
            if q:
                result.append((_title, q.pop(0)))
    return result


def seed_schedules(db, specs) -> None:
    """Дисциплины + группы + расписание (Пн–Пт, 4 пары) для всех специальностей и курсов 1–4.
    Идемпотентно: группы с уже готовым расписанием пропускаются."""
    teacher_ids = [u.id for u in db.scalars(
        select(User).where(User.role == Role.teacher).order_by(User.id))]
    if not teacher_ids:
        return
    subj_teacher = {}
    td_seen = set()  # (teacher_id, discipline_id) — дедуп (autoflush выключен)

    def teacher_for(title):
        if title not in subj_teacher:
            subj_teacher[title] = teacher_ids[len(subj_teacher) % len(teacher_ids)]
        return subj_teacher[title]

    def get_discipline(title, spec_id, course):
        d = db.scalar(select(Discipline).where(
            Discipline.title == title, Discipline.specialty_id == spec_id, Discipline.course == course))
        if not d:
            d = Discipline(title=title, specialty_id=spec_id, course=course)
            db.add(d)
            db.flush()
        return d

    for code, spec in specs.items():
        prefix = GROUP_PREFIX.get(code, code[:2].upper())
        for course in (1, 2, 3):
            subjects = COURSE1_COMMON if course == 1 else CURRICULUM[code][course]
            group_name = f"{prefix}-{course}1"
            group = db.scalar(select(StudentGroup).where(StudentGroup.name == group_name))
            if not group:
                group = StudentGroup(name=group_name, specialty_id=spec.id, course=course,
                                     curator_user_id=teacher_for(subjects[0][0]))
                db.add(group)
                db.flush()
            if db.scalar(select(ScheduleEntry).where(ScheduleEntry.group_id == group.id)):
                continue  # уже есть расписание
            for idx, (title, ltype) in enumerate(_interleave(subjects)[:len(PAIRS) * 5]):
                day = idx // len(PAIRS) + 1   # 1..5 (Пн..Пт)
                pair = idx % len(PAIRS)       # 0..3
                start, end = PAIRS[pair]
                disc = get_discipline(title, spec.id, course)
                tid = teacher_for(title)
                db.add(ScheduleEntry(
                    discipline_id=disc.id, group_id=group.id, teacher_user_id=tid,
                    day_of_week=day, start_time=start, end_time=end,
                    room=f"{prefix}-{course}{pair + 1:02d}", lesson_type=ltype))
                if (tid, disc.id) not in td_seen and not db.scalar(select(TeacherDiscipline).where(
                        TeacherDiscipline.teacher_user_id == tid,
                        TeacherDiscipline.discipline_id == disc.id)):
                    db.add(TeacherDiscipline(teacher_user_id=tid, discipline_id=disc.id))
                    td_seen.add((tid, disc.id))
            db.commit()


def seed_group_students(db) -> None:
    """По одному студенту в каждую учебную группу — чтобы преподаватель выставлял
    оценки выбором студента из списка своей группы, а не вводом ID."""
    groups = list(db.scalars(select(StudentGroup).order_by(StudentGroup.name)))
    for i, g in enumerate(groups, start=1):
        prefix, _, suffix = g.name.partition("-")
        latin = LATIN_PREFIX.get(prefix, prefix.lower())
        u = get_or_create_user(db, f"{latin}{suffix}@academy.kz", f"+7702{i:07d}", Role.student)
        if not db.get(StudentProfile, u.id):
            db.add(StudentProfile(
                user_id=u.id, student_code=f"id_1{i:04d}",
                full_name=STUDENT_NAMES[(i - 1) % len(STUDENT_NAMES)],
                gpa=0, course=g.course, admission_year=2023,
                specialty_id=g.specialty_id, group_id=g.id))
    db.commit()


def get_or_create_user(db, email, phone, role, verified=True):
    u = db.scalar(select(User).where(User.email == email))
    if u:
        return u
    u = User(email=email, phone=phone, role=role,
             password_hash=hash_password(DEMO_PASSWORD),
             email_verified=verified, phone_verified=verified)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def run():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        # справочник специальностей (на случай чистой БД без SQL-сидов)
        specs = {s.code: s for s in db.scalars(select(Specialty))}
        if not specs:
            data = [
                ("software", "Программное обеспечение", "Бағдарламалық қамтамасыз ету", "Software Engineering"),
                ("cybersec", "Кибербезопасность", "Киберқауіпсіздік", "Cybersecurity"),
                ("data_science", "Data Science", "Data Science", "Data Science"),
                ("qa", "Тестировщик", "Тестілеуші", "QA Engineer"),
                ("fullstack", "Fullstack разработчик", "Fullstack әзірлеуші", "Fullstack Developer"),
            ]
            for code, ru, kz, en in data:
                db.add(Specialty(code=code, name_ru=ru, name_kz=kz, name_en=en))
            db.commit()
            specs = {s.code: s for s in db.scalars(select(Specialty))}

        # --- пользователи ---
        admin = get_or_create_user(db, "admin@academy.kz", "+77010000001", Role.admin)
        council = get_or_create_user(db, "council@academy.kz", "+77010000002", Role.council)
        # демо-преподаватель = куратор Айгерим Сабитова; логин по транслиту имени
        teacher = get_or_create_user(db, "asabitova@academy.kz", "+77010000003", Role.teacher)
        student = get_or_create_user(db, "student@academy.kz", "+77010000004", Role.student)

        # --- группа ---
        group = db.scalar(select(StudentGroup).where(StudentGroup.name == "ПО-21"))
        if not group:
            group = StudentGroup(name="ПО-21", specialty_id=specs["software"].id,
                                 course=2, curator_user_id=teacher.id)
            db.add(group)
            db.commit()
            db.refresh(group)

        # --- профили ---
        if not db.get(TeacherProfile, teacher.id):
            db.add(TeacherProfile(user_id=teacher.id, full_name="Айгерим Сабитова",
                                  experience_years=12, academic_degree="к.т.н.",
                                  academic_title="Доцент", bio="Школа программной инженерии"))
        if not db.get(StudentProfile, student.id):
            db.add(StudentProfile(user_id=student.id, student_code="id_00001",
                                  full_name="Данияр Ермеков", gpa=3.75, course=2,
                                  birth_year=2005, admission_year=2023,
                                  specialty_id=specs["software"].id, group_id=group.id))
        db.commit()

        # --- преподавательский состав ---
        # Вместе с куратором "Айгерим Сабитова" (создана выше) всего получится 10 человек.
        # bio — школа/кафедра, academic_title — должность. Логин: первая буква имени + фамилия.
        faculty = [
            ("Сейтжанова Айгерим Болатовна", "Доцент", "к.т.н.", 12, "Школа кибербезопасности", "aseitzhanova"),
            ("Жумабаев Данияр Маратович", "Старший преподаватель", None, 8, "Школа Data Science", "dzhumabaev"),
            ("Тлеубаев Арман Кайратович", "Доцент", "к.т.н.", 14, "Школа сетевых технологий", "atleubaev"),
            ("Бектурганова Динара Аскаровна", "Старший преподаватель", None, 9, "Школа веб-разработки", "dbekturganova"),
            ("Мухамеджанов Тимур Русланович", "Преподаватель", None, 5, "Школа кибербезопасности", "tmukhamedzhanov"),
            ("Карибаева Сауле Нурлановна", "Профессор", "д.т.н.", 19, "Школа искусственного интеллекта", "skaribaeva"),
            ("Достанов Ербол Канатович", "Доцент", "к.т.н.", 13, "Школа тестирования ПО", "edostanov"),
            ("Нуржанова Аружан Талгатовна", "Старший преподаватель", None, 7, "Школа Data Science", "anurzhanova"),
        ]
        for i, (name, title, degree, years, school, login) in enumerate(faculty, start=1):
            u = get_or_create_user(db, f"{login}@academy.kz", f"+7701000{1000 + i}", Role.teacher)
            if not db.get(TeacherProfile, u.id):
                db.add(TeacherProfile(user_id=u.id, full_name=name, academic_title=title,
                                      academic_degree=degree, experience_years=years, bio=school))
        db.commit()

        # --- дисциплины ---
        disc = db.scalar(select(Discipline).where(Discipline.title == "Веб-разработка"))
        if not disc:
            disc = Discipline(title="Веб-разработка", specialty_id=specs["software"].id,
                              course=2, description="FastAPI + React.")
            db.add(disc)
            db.commit()
            db.refresh(disc)
        disc2 = db.scalar(select(Discipline).where(Discipline.title == "Базы данных"))
        if not disc2:
            disc2 = Discipline(title="Базы данных", specialty_id=specs["software"].id,
                               course=2, description="Проектирование и SQL.")
            db.add(disc2)
            db.commit()
            db.refresh(disc2)

        if not db.scalar(select(TeacherDiscipline).where(
                TeacherDiscipline.teacher_user_id == teacher.id,
                TeacherDiscipline.discipline_id == disc.id)):
            db.add(TeacherDiscipline(teacher_user_id=teacher.id, discipline_id=disc.id))
            db.add(TeacherDiscipline(teacher_user_id=teacher.id, discipline_id=disc2.id))
            db.commit()

        # --- новости ---
        if not db.scalar(select(News)):
            db.add_all([
                News(title="Старт нового семестра", body="Учебный процесс начинается 1 сентября.",
                     category="news", author_user_id=council.id),
                News(title="День открытых дверей", body="Приглашаем абитуриентов.",
                     category="event", author_user_id=council.id,
                     event_date=datetime.now() + timedelta(days=7)),
            ])
            db.commit()

        # --- предложения для записи ---
        if not db.scalar(select(CourseOffering)):
            db.add_all([
                CourseOffering(discipline_id=disc.id, teacher_user_id=teacher.id,
                               specialty_id=specs["software"].id, course=2,
                               session_date=date.today() + timedelta(days=3),
                               start_time=time(14, 0), room="201",
                               total_seats=20, available_seats=20),
                CourseOffering(discipline_id=disc2.id, teacher_user_id=teacher.id,
                               specialty_id=specs["software"].id, course=2,
                               session_date=date.today() + timedelta(days=5),
                               start_time=time(16, 0), room="202",
                               total_seats=15, available_seats=15),
            ])
            db.commit()

        # --- расписание для всех специальностей и курсов ---
        seed_schedules(db, specs)

        # --- по одному студенту в каждую группу (для выставления оценок) ---
        seed_group_students(db)

        print("Seed готов. Демо-логины (пароль у всех Passw0rd!):")
        print("  admin@academy.kz / council@academy.kz / student@academy.kz")
        print("  преподаватели (по транслиту имени): asabitova@, aseitzhanova@, dzhumabaev@,")
        print("    kospanova@, atleubaev@, dbekturganova@, tmukhamedzhanov@, skaribaeva@,")
        print("    edostanov@, anurzhanova@ academy.kz")
    finally:
        db.close()


if __name__ == "__main__":
    run()

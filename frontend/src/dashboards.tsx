// Личные кабинеты по ролям: Студент, Преподаватель, Студсовет, Администрация.
// Один файл — выбор кабинета по роли в <Dashboard/>.
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { adminApi, apiErr, dataApi } from "./api";
import { useAuth } from "./auth";
import { Card, Toast } from "./components";
import { useI18n } from "./i18n";
import type { AdminProfile, AdminProfileUpdate, Grade, NewsItem, Role, ScheduleEntry, TeacherClass, User } from "./types";

// ====================== РОУТЕР КАБИНЕТА ======================
export function Dashboard() {
  const { me } = useAuth();
  if (!me) return null;
  switch (me.user.role) {
    case "student": return <StudentDashboard />;
    case "teacher": return <TeacherDashboard />;
    case "council": return <CouncilDashboard />;
    case "admin": return <AdminDashboard />;
  }
}

// ====================== СТУДЕНТ ======================
function StudentDashboard() {
  const { me } = useAuth();
  const { t } = useI18n();
  const p = me!.student_profile!;
  const [today, setToday] = useState<ScheduleEntry[]>([]);
  const [grades, setGrades] = useState<Grade[]>([]);

  useEffect(() => {
    dataApi.scheduleToday().then(setToday).catch(() => {});
    dataApi.myGrades().then(setGrades).catch(() => {});
  }, []);

  return (
    <div className="container">
      <div className="dash-head">
        <img className="avatar" src={p.photo_url || "https://placehold.co/120x120?text=DA"} alt="" />
        <div>
          <h2>{p.full_name}</h2>
          <p className="muted">{t("student_id")}: {p.student_code}</p>
          <span className="role-badge">{me!.user.role}</span>
        </div>
        <div className="gpa-box"><span>{t("gpa")}</span><b>{Number(p.gpa).toFixed(2)}</b></div>
      </div>

      <div className="grid">
        <Card title={t("today_classes")}>
          {today.length === 0 && <p className="muted">Сегодня пар нет</p>}
          {today.map((e) => (
            <div key={e.id} className="sched-row">
              <b>{e.start_time?.slice(0, 5)}–{e.end_time?.slice(0, 5)}</b>
              <span>{e.discipline_title}</span>
              <span className="muted">ауд. {e.room} · {e.teacher_name}</span>
            </div>
          ))}
        </Card>

        <Card title="Личные данные">
          <ul className="data-list">
            <li><span>{t("course")}</span><b>{p.course}</b></li>
            <li><span>Год рождения</span><b>{p.birth_year ?? "—"}</b></li>
            <li><span>Год поступления</span><b>{p.admission_year ?? "—"}</b></li>
            <li><span>Email</span><b>{me!.user.email}</b></li>
            <li><span>{t("phone")}</span><b>{me!.user.phone}</b></li>
          </ul>
        </Card>

        <Card title={t("my_grades")}>
          {grades.length === 0 && <p className="muted">Оценок пока нет</p>}
          {grades.map((g) => (
            <div key={g.id} className="sched-row">
              <span>{g.discipline_title}</span>
              <b className="grade">{g.value}</b>
              <span className="muted">{new Date(g.created_at).toLocaleDateString()}</span>
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}

// ====================== ПРЕПОДАВАТЕЛЬ ======================
function TeacherDashboard() {
  const { me } = useAuth();
  const { t } = useI18n();
  const p = me!.teacher_profile!;
  const [week, setWeek] = useState<ScheduleEntry[]>([]);
  const [dayFilter, setDayFilter] = useState<number | null>(null); // null = все дни
  const [classes, setClasses] = useState<TeacherClass[]>([]);
  const [grade, setGrade] = useState({ group_id: "", student_user_id: "", discipline_id: "", value: "", comment: "" });
  const [toast, setToast] = useState<{ m: string; k: "ok" | "err" } | null>(null);

  useEffect(() => {
    dataApi.scheduleWeek().then((w) => {
      setWeek(w);
      // по умолчанию показываем сегодняшний день (если в нём есть пары), иначе первый день с парами
      const todayIso = ((new Date().getDay() + 6) % 7) + 1; // 1=Пн..7=Вс
      const present = [...new Set(w.map((e) => e.day_of_week))].sort((a, b) => a - b);
      setDayFilter(present.includes(todayIso) ? todayIso : (present[0] ?? null));
    }).catch(() => {});
    dataApi.teacherClasses().then(setClasses).catch(() => {});
  }, []);

  // дни, в которых есть пары, + фильтрация расписания по выбранному дню
  const days = [...new Set(week.map((e) => e.day_of_week))].sort((a, b) => a - b);
  const shownWeek = dayFilter ? week.filter((e) => e.day_of_week === dayFilter) : week;

  // выбранная группа определяет доступные дисциплины и студентов в форме
  const cls = classes.find((c) => String(c.group_id) === grade.group_id);

  const pickGroup = (gid: string) => setGrade({ ...grade, group_id: gid, discipline_id: "", student_user_id: "" });

  const submitGrade = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await dataApi.createGrade({
        student_user_id: Number(grade.student_user_id),
        discipline_id: Number(grade.discipline_id),
        value: Number(grade.value),
        comment: grade.comment || undefined,
      });
      setToast({ m: t("grade_added"), k: "ok" });
      setGrade({ ...grade, student_user_id: "", value: "", comment: "" });
    } catch (err) {
      setToast({ m: apiErr(err), k: "err" });
    }
  };

  return (
    <div className="container">
      <div className="dash-head">
        <img className="avatar" src={p.photo_url || "https://placehold.co/120x120?text=DA"} alt="" />
        <div>
          <h2>{p.full_name}</h2>
          <p className="muted">{p.academic_title} · {p.academic_degree}</p>
          <p>{t("experience")}: {p.experience_years} {t("years_short")}</p>
        </div>
      </div>

      <div className="grid">
        <Card title={t("week_schedule")}>
          {week.length === 0 && <p className="muted">{t("schedule_empty")}</p>}
          {days.length > 0 && (
            <div className="day-filter">
              {days.map((d) => (
                <button key={d} type="button"
                  className={`day-chip${d === dayFilter ? " active" : ""}`}
                  onClick={() => setDayFilter(d)}>{t(`day_short_${d}`)}</button>
              ))}
              <button type="button"
                className={`day-chip${dayFilter === null ? " active" : ""}`}
                onClick={() => setDayFilter(null)}>{t("all_days")}</button>
            </div>
          )}
          {shownWeek.map((e) => (
            <div key={e.id} className="sched-row">
              <b>{t(`day_${e.day_of_week}`)} {e.start_time?.slice(0, 5)}</b>
              <span>{e.discipline_title}</span>
              <span className="muted">{e.group_name} · {t(`lt_${e.lesson_type}`)} · ауд. {e.room}</span>
            </div>
          ))}
        </Card>

        <Card title={t("set_grade")}>
          {classes.length === 0 && <p className="muted">{t("no_classes")}</p>}
          {classes.length > 0 && (
            <form onSubmit={submitGrade} className="form">
              <label>{t("group")}
                <select value={grade.group_id} required onChange={(e) => pickGroup(e.target.value)}>
                  <option value="">—</option>
                  {classes.map((c) => (
                    <option key={c.group_id} value={c.group_id}>{c.group_name}</option>
                  ))}
                </select></label>
              <label>{t("disciplines")}
                <select value={grade.discipline_id} required disabled={!cls}
                  onChange={(e) => setGrade({ ...grade, discipline_id: e.target.value })}>
                  <option value="">—</option>
                  {cls?.disciplines.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
                </select></label>
              <label>{t("enroll_student")}
                <select value={grade.student_user_id} required disabled={!cls}
                  onChange={(e) => setGrade({ ...grade, student_user_id: e.target.value })}>
                  <option value="">—</option>
                  {cls?.students.map((s) => (
                    <option key={s.user_id} value={s.user_id}>{s.full_name} ({s.student_code})</option>
                  ))}
                </select>
                {cls && cls.students.length === 0 && <small className="muted">{t("no_students")}</small>}
              </label>
              <label>{t("grade_value")}
                <input type="number" min={0} max={100} value={grade.value} required
                  onChange={(e) => setGrade({ ...grade, value: e.target.value })} /></label>
              <label>{t("comment")}
                <input value={grade.comment} onChange={(e) => setGrade({ ...grade, comment: e.target.value })} /></label>
              <button className="btn">{t("set_grade")}</button>
            </form>
          )}
        </Card>
      </div>
      {toast && <Toast msg={toast.m} kind={toast.k} onClose={() => setToast(null)} />}
    </div>
  );
}

// ====================== СТУДСОВЕТ ======================
function CouncilDashboard() {
  const { t } = useI18n();
  const [news, setNews] = useState<NewsItem[]>([]);
  const [form, setForm] = useState({ title: "", body: "", category: "news", event_date: "" });
  const [students, setStudents] = useState<{ student_code: string; full_name: string; course: number }[]>([]);
  const [toast, setToast] = useState<{ m: string; k: "ok" | "err" } | null>(null);

  const loadNews = () => dataApi.news().then(setNews).catch(() => {});
  useEffect(() => {
    loadNews();
    adminApi.council_students().then(setStudents).catch(() => {});
  }, []);

  const publish = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await dataApi.createNews({
        title: form.title, body: form.body,
        category: form.category as NewsItem["category"],
        event_date: form.event_date || null,
      });
      setForm({ title: "", body: "", category: "news", event_date: "" });
      setToast({ m: "Опубликовано", k: "ok" });
      loadNews();
    } catch (err) {
      setToast({ m: apiErr(err), k: "err" });
    }
  };

  return (
    <div className="container">
      <h2>Кабинет студсовета</h2>
      <div className="grid">
        <Card title={t("publish_news")}>
          <form onSubmit={publish} className="form">
            <label>Заголовок<input value={form.title} required
              onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
            <label>Категория
              <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                <option value="news">Новость</option>
                <option value="announcement">Объявление</option>
                <option value="event">Мероприятие</option>
              </select></label>
            <label>Текст<textarea value={form.body} required
              onChange={(e) => setForm({ ...form, body: e.target.value })} /></label>
            {form.category === "event" && (
              <label>Дата мероприятия<input type="datetime-local" value={form.event_date}
                onChange={(e) => setForm({ ...form, event_date: e.target.value })} /></label>
            )}
            <button className="btn">{t("publish_news")}</button>
          </form>
        </Card>

        <Card title="Студенты (ограниченный доступ)">
          {students.map((s) => (
            <div key={s.student_code} className="sched-row">
              <b>{s.student_code}</b><span>{s.full_name}</span>
              <span className="muted">{t("course")} {s.course}</span>
            </div>
          ))}
          {students.length === 0 && <p className="muted">—</p>}
        </Card>

        <Card title="Опубликованные">
          {news.map((n) => (
            <div key={n.id} className="sched-row">
              <span>{n.title}</span>
              <button className="btn ghost small" onClick={() => dataApi.deleteNews(n.id).then(loadNews)}>✕</button>
            </div>
          ))}
        </Card>
      </div>
      {toast && <Toast msg={toast.m} kind={toast.k} onClose={() => setToast(null)} />}
    </div>
  );
}

// ====================== АДМИНИСТРАЦИЯ ======================
function AdminDashboard() {
  const { t } = useI18n();
  const [users, setUsers] = useState<User[]>([]);
  const [filter, setFilter] = useState<Role | "">("");
  const [form, setForm] = useState({ email: "", phone: "", password: "", full_name: "", role: "student" as Role });
  const [toast, setToast] = useState<{ m: string; k: "ok" | "err" } | null>(null);
  const load = () => adminApi.users(filter || undefined).then(setUsers).catch(() => {});
  useEffect(() => { load(); }, [filter]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await adminApi.createUser(form);
      setForm({ email: "", phone: "", password: "", full_name: "", role: "student" });
      setToast({ m: "Пользователь создан", k: "ok" });
      load();
    } catch (err) {
      setToast({ m: apiErr(err), k: "err" });
    }
  };

  const changeRole = (id: number, role: Role) =>
    adminApi.updateUser(id, { role }).then(load).catch((err) => setToast({ m: apiErr(err), k: "err" }));
  const toggleActive = (u: User) =>
    adminApi.updateUser(u.id, { is_active: !u.is_active }).then(load)
      .catch((err) => setToast({ m: apiErr(err), k: "err" }));
  const remove = (u: User) => {
    if (!window.confirm(`${t("confirm_delete_user")}\n${u.email}`)) return;
    adminApi.deleteUser(u.id).then(load).catch((err) => setToast({ m: apiErr(err), k: "err" }));
  };

  const roles: Role[] = ["student", "teacher", "council", "admin"];

  return (
    <div className="container">
      <h2>Администрация — {t("manage_users")}</h2>

      <div className="grid">
        <Card title="Создать пользователя">
          <form onSubmit={create} className="form">
            <label>{t("full_name")}<input value={form.full_name} required
              onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></label>
            <label>{t("email")}<input type="email" value={form.email} required
              onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
            <label>{t("phone")}<input value={form.phone} required
              onChange={(e) => setForm({ ...form, phone: e.target.value })} /></label>
            <label>{t("password")}<input type="password" value={form.password} required
              onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
            <label>{t("role")}
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
                {roles.map((r) => <option key={r} value={r}>{r}</option>)}
              </select></label>
            <button className="btn">{t("save")}</button>
          </form>
        </Card>

        <Card title="Пользователи" actions={
          <select value={filter} onChange={(e) => setFilter(e.target.value as Role | "")}>
            <option value="">все роли</option>
            {roles.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        }>
          <table className="table">
            <thead><tr><th>ID</th><th>Email</th><th>{t("role")}</th><th>{t("active")}</th><th></th></tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.id}</td>
                  <td>
                    <Link className="user-link" title="Открыть профиль" to={`/users/${u.id}`}>{u.email}</Link>
                  </td>
                  <td>
                    <select value={u.role} onChange={(e) => changeRole(u.id, e.target.value as Role)}>
                      {roles.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </td>
                  <td>{u.is_active ? "✅" : "🚫"}</td>
                  <td className="row-actions">
                    <button className="btn ghost small" onClick={() => toggleActive(u)}>
                      {u.is_active ? "блок" : "разблок"}</button>
                    <button className="btn warn small" onClick={() => remove(u)}>{t("delete_user")}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
      {toast && <Toast msg={toast.m} kind={toast.k} onClose={() => setToast(null)} />}
    </div>
  );
}

// ====================== ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ (страница админа) ======================
export function AdminUserProfile() {
  const { t } = useI18n();
  const { id } = useParams();
  const navigate = useNavigate();
  const [p, setProfile] = useState<AdminProfile | null>(null);
  const [f, setF] = useState<Record<string, string>>({});
  const [toast, setToast] = useState<{ m: string; k: "ok" | "err" } | null>(null);

  const remove = async () => {
    if (!p || !window.confirm(`${t("confirm_delete_user")}\n${p.user.email}`)) return;
    try {
      await adminApi.deleteUser(p.user.id);
      navigate("/dashboard");
    } catch (e) { setToast({ m: apiErr(e), k: "err" }); }
  };

  useEffect(() => {
    adminApi.getProfile(Number(id)).then((pr) => {
      const sp = pr.student_profile, tp = pr.teacher_profile;
      setProfile(pr);
      setF({
        email: pr.user.email, phone: pr.user.phone,
        full_name: sp?.full_name ?? tp?.full_name ?? "",
        gpa: sp ? String(sp.gpa) : "", course: sp ? String(sp.course) : "",
        birth_year: sp?.birth_year != null ? String(sp.birth_year) : "",
        admission_year: sp?.admission_year != null ? String(sp.admission_year) : "",
        academic_title: tp?.academic_title ?? "", academic_degree: tp?.academic_degree ?? "",
        experience_years: tp ? String(tp.experience_years) : "", bio: tp?.bio ?? "",
      });
    }).catch((e) => setToast({ m: apiErr(e), k: "err" }));
  }, [id]);

  const ch = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setF((s) => ({ ...s, [k]: e.target.value }));

  const save = async () => {
    if (!p) return;
    const isS = !!p.student_profile, isT = !!p.teacher_profile;
    const data: AdminProfileUpdate = { email: f.email || undefined, phone: f.phone || undefined };
    if (isS || isT) data.full_name = f.full_name || undefined;
    if (isS) {
      if (f.gpa !== "") data.gpa = Number(f.gpa);
      if (f.course !== "") data.course = Number(f.course);
      if (f.birth_year !== "") data.birth_year = Number(f.birth_year);
      if (f.admission_year !== "") data.admission_year = Number(f.admission_year);
    }
    if (isT) {
      data.academic_title = f.academic_title || undefined;
      data.academic_degree = f.academic_degree || undefined;
      if (f.experience_years !== "") data.experience_years = Number(f.experience_years);
      data.bio = f.bio || undefined;
    }
    try {
      setProfile(await adminApi.updateProfile(p.user.id, data));
      setToast({ m: "Сохранено ✔", k: "ok" });
    } catch (e) { setToast({ m: apiErr(e), k: "err" }); }
  };

  if (!p) return <div className="container"><p className="muted">{t("loading")}</p></div>;
  const name = f.full_name || p.user.email;
  const initials = name.split(" ").filter(Boolean).slice(0, 2).map((s) => s[0]).join("").toUpperCase();

  return (
    <div className="container">
      <div className="dash-head">
        <div className="avatar avatar-initials">{initials}</div>
        <div>
          <h2>{name}</h2>
          <p className="muted">{p.user.email}</p>
          <span className="role-badge">{p.user.role}</span>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: "8px" }}>
          <button className="btn warn" onClick={remove}>{t("delete_user")}</button>
          <Link to="/dashboard" className="btn ghost">← {t("nav_dashboard")}</Link>
        </div>
      </div>

      <Card title="Редактирование данных (только админ)">
        <form className="form" onSubmit={(e) => { e.preventDefault(); save(); }}>
          <label>{t("email")}<input type="email" value={f.email} onChange={ch("email")} /></label>
          <label>{t("phone")}<input value={f.phone} onChange={ch("phone")} /></label>
          {(p.student_profile || p.teacher_profile) && (
            <label>{t("full_name")}<input value={f.full_name} onChange={ch("full_name")} /></label>
          )}
          {p.student_profile && (
            <>
              <label>{t("gpa")}<input type="number" step="0.01" value={f.gpa} onChange={ch("gpa")} /></label>
              <label>{t("course")}<input type="number" value={f.course} onChange={ch("course")} /></label>
              <label>Год рождения<input type="number" value={f.birth_year} onChange={ch("birth_year")} /></label>
              <label>Год поступления<input type="number" value={f.admission_year} onChange={ch("admission_year")} /></label>
            </>
          )}
          {p.teacher_profile && (
            <>
              <label>{t("title_rank")}<input value={f.academic_title} onChange={ch("academic_title")} /></label>
              <label>{t("degree")}<input value={f.academic_degree} onChange={ch("academic_degree")} /></label>
              <label>{t("experience")}<input type="number" value={f.experience_years} onChange={ch("experience_years")} /></label>
              <label>Био<textarea value={f.bio} onChange={ch("bio")} /></label>
            </>
          )}
          {!p.student_profile && !p.teacher_profile && (
            <p className="muted">У пользователя нет профиля (только аккаунт) — доступны email и телефон.</p>
          )}
          <button className="btn">{t("save")}</button>
        </form>
      </Card>
      {toast && <Toast msg={toast.m} kind={toast.k} onClose={() => setToast(null)} />}
    </div>
  );
}

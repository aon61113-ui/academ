// Модуль "Запись по дисциплинам": фильтры (специальность, курс, дата, преподаватель)
// + кнопка "Совершить бронь" с динамическим обновлением мест и статуса.
import { useEffect, useState } from "react";
import { adminApi, apiErr, dataApi } from "./api";
import { useAuth } from "./auth";
import { Card, Toast } from "./components";
import { specialtyName, useI18n } from "./i18n";
import type { LimitedStudent, Offering, Specialty } from "./types";

export function EnrollmentPage() {
  const { t, lang } = useI18n();
  const { me } = useAuth();
  const isAdmin = me?.user.role === "admin";
  const [specialties, setSpecialties] = useState<Specialty[]>([]);
  const [offerings, setOfferings] = useState<Offering[]>([]);
  const [filters, setFilters] = useState({ specialty_id: "", course: "", session_date: "", teacher: "" });
  const [students, setStudents] = useState<LimitedStudent[]>([]);
  const [studentId, setStudentId] = useState("");  // выбранный студент (для админа)
  const [toast, setToast] = useState<{ m: string; k: "ok" | "err" } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    dataApi.specialties().then(setSpecialties).catch(() => {});
    if (isAdmin) adminApi.council_students().then(setStudents).catch(() => {});
  }, [isAdmin]);

  const sid = studentId ? Number(studentId) : undefined;

  const load = () => {
    setLoading(true);
    dataApi.offerings({
      specialty_id: filters.specialty_id ? Number(filters.specialty_id) : undefined,
      course: filters.course ? Number(filters.course) : undefined,
      session_date: filters.session_date || undefined,
      teacher_user_id: filters.teacher ? Number(filters.teacher) : undefined,
      student_user_id: isAdmin ? sid : undefined,
    }).then(setOfferings).catch((e) => setToast({ m: apiErr(e), k: "err" })).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [filters, studentId]);

  // Динамическое обновление мест/статуса: заменяем элемент ответом сервера
  const replace = (o: Offering) => setOfferings((prev) => prev.map((x) => (x.id === o.id ? o : x)));

  const book = async (id: number) => {
    try {
      replace(await dataApi.book(id, isAdmin ? sid : undefined));
      setToast({ m: "Бронь оформлена ✔", k: "ok" });
    } catch (e) {
      setToast({ m: apiErr(e), k: "err" });
      load();
    }
  };
  const cancel = async (id: number) => {
    try {
      replace(await dataApi.cancelBook(id, isAdmin ? sid : undefined));
      setToast({ m: "Бронь отменена", k: "ok" });
    } catch (e) {
      setToast({ m: apiErr(e), k: "err" });
    }
  };

  return (
    <div className="container">
      <h2>{t("nav_enroll")}</h2>

      {isAdmin && (
        <Card title={t("enroll_student")}>
          <div className="filters">
            <label>{t("enroll_student")}
              <select value={studentId} onChange={(e) => setStudentId(e.target.value)}>
                <option value="">{t("enroll_pick")}</option>
                {students.map((s) => (
                  <option key={s.user_id} value={s.user_id}>
                    {s.full_name} · {s.student_code} · {t("course")} {s.course}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="muted">{t("enroll_admin_hint")}</p>
        </Card>
      )}

      <Card title={t("filter")}>
        <div className="filters">
          <label>{t("specialty")}
            <select value={filters.specialty_id}
              onChange={(e) => setFilters({ ...filters, specialty_id: e.target.value })}>
              <option value="">{t("all_specialties")}</option>
              {specialties.map((s) => (
                <option key={s.id} value={s.id}>{specialtyName(s, lang)}</option>
              ))}
            </select>
          </label>
          <label>{t("course")}
            <select value={filters.course} onChange={(e) => setFilters({ ...filters, course: e.target.value })}>
              <option value="">—</option>
              {[1, 2, 3].map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label>{t("date")}
            <input type="date" value={filters.session_date}
              onChange={(e) => setFilters({ ...filters, session_date: e.target.value })} />
          </label>
          <label>{t("teacher")} (user_id)
            <input value={filters.teacher} placeholder="напр. 3"
              onChange={(e) => setFilters({ ...filters, teacher: e.target.value })} />
          </label>
          <button className="btn ghost"
            onClick={() => setFilters({ specialty_id: "", course: "", session_date: "", teacher: "" })}>
            Сброс
          </button>
        </div>
      </Card>

      {loading && <p className="muted">{t("loading")}</p>}

      <div className="grid">
        {offerings.map((o) => {
          const soldOut = o.available_seats <= 0 || o.status !== "open";
          const blocked = isAdmin && !sid;  // админ не выбрал студента
          return (
            <Card key={o.id}>
              <div className="offer">
                <h4>{o.discipline_title}</h4>
                <p className="muted">{o.specialty_name} · {t("course")} {o.course}</p>
                <p>👨‍🏫 {o.teacher_name}</p>
                <p>📅 {o.session_date} · {o.start_time?.slice(0, 5)} · ауд. {o.room}</p>
                <div className="seats">
                  <span className={`seat-pill ${soldOut ? "full" : "open"}`}>
                    {t("seats_left")}: {o.available_seats}/{o.total_seats}
                  </span>
                  <span className={`status-pill ${o.status}`}>{o.status}</span>
                </div>
                {o.is_booked_by_me ? (
                  <button className="btn warn" disabled={blocked} onClick={() => cancel(o.id)}>{t("cancel_book")}</button>
                ) : (
                  <button className="btn" disabled={soldOut || blocked} onClick={() => book(o.id)}>
                    {soldOut ? t("no_seats") : t("book")}
                  </button>
                )}
              </div>
            </Card>
          );
        })}
        {!loading && offerings.length === 0 && <p className="muted">Ничего не найдено по фильтрам.</p>}
      </div>
      {toast && <Toast msg={toast.m} kind={toast.k} onClose={() => setToast(null)} />}
    </div>
  );
}

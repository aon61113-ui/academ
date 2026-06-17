// Публичные страницы и страницы авторизации, собранные в одном файле.
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { apiErr, authApi, dataApi } from "./api";
import { useAuth } from "./auth";
import { Card, NewsFeed, Toast } from "./components";
import { specialtyName, tValue, useI18n } from "./i18n";
import type { Discipline, Group, ScheduleEntry, Specialty, TeacherProfile } from "./types";

// ============================ ГЛАВНАЯ ============================
const SPECIALTY_ICONS: Record<string, string> = {
  software: "💻", cybersec: "🛡️", data_science: "📊", qa: "🐞", fullstack: "🧩",
};

// Ключевые показатели академии (статичный блок на главной).
const ACADEMY_STATS = [
  { key: "stat_founded", value: "2023" },
  { key: "stat_students", value: "1037" },
  { key: "stat_employment", value: "98%" },
];

// Главные новости академии (блок «2 фото» на главной). Тексты берутся из i18n,
// поэтому меняются вместе с языком интерфейса.
// Своё фото: положи /news-icpc.jpg и /news-cyber.jpg в frontend/public — они заменят заглушки .svg.
const HOME_NEWS = [
  { img: "/news-icpc.jpg", fallback: "/news-icpc.svg", category: "event" as const, titleKey: "news1_title", bodyKey: "news1_body", date: "2026-06-14" },
  { img: "/news-cyber.jpg", fallback: "/news-cyber.svg", category: "news" as const, titleKey: "news2_title", bodyKey: "news2_body", date: "2026-06-09" },
];

// Счётчик с анимацией «накрутки» при появлении в зоне видимости.
function Counter({ value, className }: { value: string; className?: string }) {
  const ref = useRef<HTMLElement>(null);
  const [display, setDisplay] = useState("0");
  useEffect(() => {
    const el = ref.current;
    const m = value.match(/^(\d+)(.*)$/);
    if (!el || !m) { setDisplay(value); return; }
    const target = parseInt(m[1], 10);
    const suffix = m[2];
    let started = false;
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !started) {
        started = true;
        io.disconnect();
        const dur = 1400;
        const t0 = performance.now();
        const tick = (now: number) => {
          const p = Math.min(1, (now - t0) / dur);
          const eased = 1 - Math.pow(1 - p, 3);
          setDisplay(Math.round(target * eased) + suffix);
          if (p < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      }
    }, { threshold: 0.4 });
    io.observe(el);
    return () => io.disconnect();
  }, [value]);
  return <b className={className} ref={ref}>{display}</b>;
}

export function HomePage() {
  const { t, lang } = useI18n();
  const [specialties, setSpecialties] = useState<Specialty[]>([]);
  const [topTeachers, setTopTeachers] = useState<TeacherProfile[]>([]);
  const heroRef = useRef<HTMLElement>(null);
  useEffect(() => { dataApi.specialties().then(setSpecialties).catch(() => {}); }, []);
  // «Лучшие преподаватели» — 4 случайных из состава (с запасным списком, если API недоступен).
  useEffect(() => {
    const pick4 = (arr: TeacherProfile[]) => [...arr].sort(() => Math.random() - 0.5).slice(0, 4);
    dataApi.publicTeachers()
      .then((list) => setTopTeachers(pick4(list.length ? list : FALLBACK_FACULTY)))
      .catch(() => setTopTeachers(pick4(FALLBACK_FACULTY)));
  }, []);

  // Плавное появление блоков при прокрутке (scroll-reveal).
  useEffect(() => {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      });
    }, { threshold: 0.15 });
    document.querySelectorAll<HTMLElement>(".reveal").forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [specialties, topTeachers]);

  // Параллакс hero от курсора — ТОЛЬКО на десктопе с мышью (на мобильной/тач не трогаем).
  useEffect(() => {
    const el = heroRef.current;
    if (!el) return;
    const finePointer = window.matchMedia("(pointer: fine)").matches;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!finePointer || reduced || window.innerWidth <= 820) return;

    const onMove = (ev: MouseEvent) => {
      const r = el.getBoundingClientRect();
      const nx = ((ev.clientX - r.left) / r.width - 0.5) * 2;   // -1..1
      const ny = ((ev.clientY - r.top) / r.height - 0.5) * 2;
      el.style.setProperty("--px", `${-nx * 18}px`);  // фон — против курсора
      el.style.setProperty("--py", `${-ny * 14}px`);
      el.style.setProperty("--cx", `${nx * 8}px`);     // текст — слегка
      el.style.setProperty("--cy", `${ny * 6}px`);
      el.style.setProperty("--ox", `${nx * 28}px`);    // сферы — сильнее (передний план)
      el.style.setProperty("--oy", `${ny * 22}px`);
    };
    const onLeave = () => {
      ["--px", "--py", "--cx", "--cy", "--ox", "--oy"].forEach((v) => el.style.setProperty(v, "0px"));
    };
    el.classList.add("parallax-on");
    el.addEventListener("mousemove", onMove);
    el.addEventListener("mouseleave", onLeave);
    return () => {
      el.removeEventListener("mousemove", onMove);
      el.removeEventListener("mouseleave", onLeave);
      el.classList.remove("parallax-on");
    };
  }, []);

  return (
    <div className="container">
      <section className="hero-banner" ref={heroRef}>
        <span className="hero-orb hero-orb-1" />
        <span className="hero-orb hero-orb-2" />
        <div className="hero-banner-content">
          <span className="hero-eyebrow">🎓 IT-образование нового поколения</span>
          <h1>Digital Academy</h1>
          <p className="hero-tagline">Learning today — leading tomorrow</p>
          <p className="hero-sub">{t("about_text")}</p>
          <div className="hero-actions">
            <Link to="/courses" className="btn lg">{t("view_courses")}</Link>
            <Link to="/schedule" className="btn ghost lg light">{t("view_schedule")}</Link>
          </div>
        </div>
      </section>

      <section className="stats-band">
        {ACADEMY_STATS.map((s, i) => (
          <div key={s.key} className="stat-box reveal" style={{ transitionDelay: `${i * 120}ms` }}>
            <span className="stat-label">{t(s.key)}</span>
            <Counter className="stat-value" value={s.value} />
          </div>
        ))}
      </section>

      <section className="specialty-strip">
        {specialties.map((s, i) => (
          <Link key={s.id} to="/courses" className="specialty-chip reveal" style={{ transitionDelay: `${i * 70}ms` }}>
            <span className="ico">{SPECIALTY_ICONS[s.code] || "📚"}</span>
            {specialtyName(s, lang)}
          </Link>
        ))}
      </section>

      <section className="home-news">
        <h2 className="section-title reveal">{t("home_news_title")}</h2>
        <div className="home-news-grid">
          {HOME_NEWS.map((n, i) => (
            <article key={n.titleKey} className="home-news-card reveal" style={{ transitionDelay: `${i * 120}ms` }}>
              <div className={`home-news-media tag-${n.category}`}>
                <img src={n.img} alt="" loading="lazy"
                  onError={(e) => {
                    const img = e.currentTarget;
                    if (!img.dataset.fb) { img.dataset.fb = "1"; img.src = n.fallback; }
                  }} />
              </div>
              <div className="home-news-body">
                <span className={`tag tag-${n.category}`}>{t(`label_${n.category}`)}</span>
                <h4>{t(n.titleKey)}</h4>
                <p className="muted">{t(n.bodyKey)}</p>
                <small className="muted">📅 {new Date(n.date).toLocaleDateString()}</small>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="home-teachers">
        <div className="section-head">
          <h2 className="section-title reveal">{t("top_teachers")}</h2>
          <Link to="/teachers" className="muted">{t("nav_teachers")} →</Link>
        </div>
        <div className="faculty-grid">
          {topTeachers.map((tt, i) => (
            <article key={tt.user_id} className="faculty-card reveal" style={{ transitionDelay: `${i * 90}ms` }}>
              <div className="faculty-photo">
                {tt.photo_url
                  ? <img src={tt.photo_url} alt={tt.full_name} />
                  : <span>{initials(tt.full_name)}</span>}
              </div>
              <div className="faculty-info">
                <h4>{tt.full_name}</h4>
                {tt.academic_title && <p className="faculty-title">{tValue(tt.academic_title, lang)}</p>}
                {tt.bio && <p className="muted">{tValue(tt.bio, lang)}</p>}
              </div>
            </article>
          ))}
        </div>
      </section>

      <NewsFeed />
    </div>
  );
}

// ============================ КУРСЫ / ДИСЦИПЛИНЫ (публично) ============================
export function CoursesPage() {
  const { t, lang } = useI18n();
  const [specialties, setSpecialties] = useState<Specialty[]>([]);
  const [disciplines, setDisciplines] = useState<Discipline[]>([]);
  const [specialtyId, setSpecialtyId] = useState("");
  const [course, setCourse] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => { dataApi.specialties().then(setSpecialties).catch(() => {}); }, []);
  useEffect(() => {
    setLoading(true);
    dataApi.disciplines({
      specialty_id: specialtyId ? Number(specialtyId) : undefined,
      course: course ? Number(course) : undefined,
    }).then(setDisciplines).catch(() => {}).finally(() => setLoading(false));
  }, [specialtyId, course]);

  const specName = (id: number) => {
    const s = specialties.find((x) => x.id === id);
    return s ? specialtyName(s, lang) : "";
  };

  // Группируем по названию предмета: один и тот же предмет (на разных специальностях/курсах)
  // показываем одной карточкой, собирая внутрь все курсы и специальности.
  const grouped = useMemo(() => {
    const map = new Map<string, { title: string; description: string | null; specs: Set<number>; courses: Set<number>; code: string }>();
    for (const d of disciplines) {
      const g = map.get(d.title) ?? { title: d.title, description: null, specs: new Set<number>(), courses: new Set<number>(), code: "" };
      g.specs.add(d.specialty_id);
      g.courses.add(d.course);
      if (!g.description && d.description) g.description = d.description;
      if (!g.code) g.code = specialties.find((s) => s.id === d.specialty_id)?.code || "";
      map.set(d.title, g);
    }
    return [...map.values()].sort((a, b) => a.title.localeCompare(b.title));
  }, [disciplines, specialties]);

  return (
    <div className="container">
      <div className="page-head">
        <h2>{t("courses_title")}</h2>
        <p className="muted">{t("courses_subtitle")}</p>
      </div>

      <div className="filters">
        <label>{t("specialty")}
          <select value={specialtyId} onChange={(e) => setSpecialtyId(e.target.value)}>
            <option value="">{t("all_specialties")}</option>
            {specialties.map((s) => <option key={s.id} value={s.id}>{specialtyName(s, lang)}</option>)}
          </select>
        </label>
        <label>{t("course")}
          <select value={course} onChange={(e) => setCourse(e.target.value)}>
            <option value="">—</option>
            {[1, 2, 3].map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
      </div>

      {loading && <p className="muted">{t("loading")}</p>}
      <div className="grid">
        {grouped.map((g) => {
          const courseList = [...g.courses].sort((a, b) => a - b);
          const specList = [...g.specs];
          const allSpecs = specialties.length > 0 && specList.length === specialties.length;
          return (
            <div key={g.title} className="course-card">
              <span className="course-badge">{SPECIALTY_ICONS[g.code] || "📚"}</span>
              <h4>{g.title}</h4>
              <div className="course-meta">
                <span className="pill alt">{t("course")} {courseList.join(", ")}</span>
                {allSpecs
                  ? <span className="pill">{t("all_specialties")}</span>
                  : specList.slice(0, 3).map((id) => <span key={id} className="pill">{specName(id)}</span>)}
                {!allSpecs && specList.length > 3 && <span className="pill">+{specList.length - 3}</span>}
              </div>
              {g.description && <p className="muted">{g.description}</p>}
            </div>
          );
        })}
      </div>
      {!loading && grouped.length === 0 && <p className="muted">{t("no_results")}</p>}
    </div>
  );
}

// ============================ РАСПИСАНИЕ (публично) ============================
export function SchedulePage() {
  const { t } = useI18n();
  const [groups, setGroups] = useState<Group[]>([]);
  const [groupId, setGroupId] = useState("");
  const [entries, setEntries] = useState<ScheduleEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { dataApi.groups().then(setGroups).catch(() => {}); }, []);
  useEffect(() => {
    setLoading(true);
    dataApi.schedulePublic(groupId ? Number(groupId) : undefined)
      .then(setEntries).catch(() => {}).finally(() => setLoading(false));
  }, [groupId]);

  // группируем по дню недели
  const byDay = entries.reduce<Record<number, ScheduleEntry[]>>((acc, e) => {
    (acc[e.day_of_week] ||= []).push(e);
    return acc;
  }, {});
  const days = Object.keys(byDay).map(Number).sort((a, b) => a - b);

  return (
    <div className="container">
      <div className="page-head">
        <h2>{t("schedule_title")}</h2>
        <p className="muted">{t("schedule_subtitle")}</p>
      </div>

      <div className="filters">
        <label>{t("group")}
          <select value={groupId} onChange={(e) => setGroupId(e.target.value)}>
            <option value="">{t("all_groups")}</option>
            {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        </label>
      </div>

      {loading && <p className="muted">{t("loading")}</p>}
      {!loading && entries.length === 0 && <p className="muted">{t("no_schedule")}</p>}

      <div className="timetable">
        {days.map((d) => (
          <div key={d} className="day-col">
            <div className="day-head">{t(`day_${d}`)}</div>
            {byDay[d].map((e) => (
              <div key={e.id} className="lesson">
                <span className="lesson-time">{e.start_time?.slice(0, 5)}–{e.end_time?.slice(0, 5)}</span>
                <b>{e.discipline_title}</b>
                <span className="muted">{e.teacher_name}</span>
                <div className="lesson-meta">
                  <span className={`pill type-${e.lesson_type}`}>{t(`lt_${e.lesson_type}`)}</span>
                  {e.group_name && <span className="pill">{e.group_name}</span>}
                  {e.room && <span className="pill alt">{t("room")} {e.room}</span>}
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================ ОБ АКАДЕМИИ ============================
// Специальности для страницы «Об академии»: фото из /public, разворачиваются по клику.
const ABOUT_SPECIALTIES: {
  code: string; icon: string; img: string;
  name: { ru: string; kz: string; en: string };
  desc: { ru: string; kz: string; en: string };
}[] = [
  {
    code: "software", icon: "💻", img: "/spec-software.jpg",
    name: { ru: "Программное обеспечение", kz: "Бағдарламалық қамтамасыз ету", en: "Software Engineering" },
    desc: {
      ru: "Разработка ПО: проектирование, написание и сопровождение приложений на современных языках.",
      kz: "БҚ әзірлеу: қазіргі тілдерде қосымшаларды жобалау, жазу және сүйемелдеу.",
      en: "Software development: designing, building and maintaining applications with modern languages.",
    },
  },
  {
    code: "cybersec", icon: "🛡️", img: "/spec-cybersec.jpg",
    name: { ru: "Кибербезопасность", kz: "Киберқауіпсіздік", en: "Cybersecurity" },
    desc: {
      ru: "Защита систем и данных: пентест, безопасность ОС и сетей, противодействие атакам.",
      kz: "Жүйелер мен деректерді қорғау: пентест, ОЖ мен желілер қауіпсіздігі, шабуылдарға қарсы тұру.",
      en: "Protecting systems and data: penetration testing, OS and network security, defense against attacks.",
    },
  },
  {
    code: "data_science", icon: "📊", img: "/spec-data.jpg",
    name: { ru: "Data Science", kz: "Data Science", en: "Data Science" },
    desc: {
      ru: "Анализ данных и машинное обучение: модели, визуализация, работа с большими данными.",
      kz: "Деректерді талдау және машиналық оқыту: модельдер, визуализация, үлкен деректермен жұмыс.",
      en: "Data analysis and machine learning: models, visualization and big data.",
    },
  },
  {
    code: "qa", icon: "🐞", img: "/spec-qa.jpg",
    name: { ru: "QA Тестировщик", kz: "QA Сынақшы", en: "QA Engineer" },
    desc: {
      ru: "Тестирование ПО: ручное и автоматизированное, API- и нагрузочное тестирование, контроль качества.",
      kz: "БҚ тестілеу: қолмен және автоматтандырылған, API және жүктеме тестілеу, сапаны бақылау.",
      en: "Software testing: manual and automated, API and load testing, quality assurance.",
    },
  },
  {
    code: "fullstack", icon: "🧩", img: "/spec-fullstack.jpg",
    name: { ru: "Fullstack разработчик", kz: "Fullstack әзірлеушісі", en: "Fullstack Developer" },
    desc: {
      ru: "Полный цикл веб-разработки: frontend и backend, базы данных, развёртывание.",
      kz: "Веб-әзірлеудің толық циклі: frontend және backend, дерекқорлар, орналастыру.",
      en: "Full-cycle web development: frontend and backend, databases and deployment.",
    },
  },
];

export function AboutPage() {
  const { t, lang } = useI18n();
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="container">
      <section className="about-banner">
        {/* анимированная «сеть» из точек и линий */}
        <svg className="about-net" viewBox="0 0 1200 420" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
          <g stroke="rgba(180,215,255,0.22)" strokeWidth="1.2" fill="none">
            <polyline points="90,70 250,160 180,330 420,300 560,180" />
            <polyline points="1110,90 980,200 1040,340 800,300 660,200" />
            <polyline points="250,160 660,200 980,200" />
          </g>
          <g className="about-dots" fill="#cfe6ff">
            <circle cx="90" cy="70" r="5" /><circle cx="250" cy="160" r="4" />
            <circle cx="180" cy="330" r="4" /><circle cx="420" cy="300" r="5" />
            <circle cx="560" cy="180" r="4" /><circle cx="660" cy="200" r="5" />
            <circle cx="800" cy="300" r="4" /><circle cx="980" cy="200" r="4" />
            <circle cx="1040" cy="340" r="5" /><circle cx="1110" cy="90" r="4" />
          </g>
        </svg>
        <span className="about-ring about-ring-1" />
        <span className="about-ring about-ring-2" />

        <div className="about-banner-content">
          <img className="about-logo" src="/logo.png" alt="Digital Academy"
            onError={(e) => { const i = e.currentTarget; if (!i.dataset.fb) { i.dataset.fb = "1"; i.src = "/logo.svg"; } }} />
          <h1>Digital Academy</h1>
          <p>Learning today — leading tomorrow</p>
        </div>
      </section>

      <Card title={t("about_title")}>
        <p>{t("about_text")}</p>
      </Card>

      <div className="spec-grid">
        {ABOUT_SPECIALTIES.map((s) => (
          <div key={s.code} className={`spec-card ${open === s.code ? "open" : ""}`}
            onClick={() => setOpen(open === s.code ? null : s.code)}>
            <div className="spec-photo">
              <span className="spec-ico">{s.icon}</span>
              <img src={`${s.img}?v=1`} alt="" onError={(e) => { e.currentTarget.style.display = "none"; }} />
            </div>
            <div className="spec-name">{s.name[lang]} <span className="spec-caret">▾</span></div>
            <div className="spec-info"><p>{s.desc[lang]}</p></div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================ О ПРЕПОДАВАТЕЛЯХ ============================
// Состав загружается из БД (эндпоинт /users/teachers/public, наполняется seed.py).
// Должность берётся из academic_title, школа/кафедра — из bio.
// Если бэкенд недоступен (например, показываем только фронтенд через туннель),
// используем встроенный список тех же 10 человек, чтобы страница не была пустой.
const initials = (name: string) =>
  name.split(" ").filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toUpperCase();

const FALLBACK_FACULTY: TeacherProfile[] = [
  { user_id: -1, full_name: "Айгерим Сабитова", photo_url: null, experience_years: 12, academic_degree: "к.т.н.", academic_title: "Доцент", bio: "Школа программной инженерии" },
  { user_id: -2, full_name: "Сейтжанова Айгерим Болатовна", photo_url: null, experience_years: 12, academic_degree: "к.т.н.", academic_title: "Доцент", bio: "Школа кибербезопасности" },
  { user_id: -3, full_name: "Жумабаев Данияр Маратович", photo_url: null, experience_years: 8, academic_degree: null, academic_title: "Старший преподаватель", bio: "Школа Data Science" },
  { user_id: -5, full_name: "Тлеубаев Арман Кайратович", photo_url: null, experience_years: 14, academic_degree: "к.т.н.", academic_title: "Доцент", bio: "Школа сетевых технологий" },
  { user_id: -6, full_name: "Бектурганова Динара Аскаровна", photo_url: null, experience_years: 9, academic_degree: null, academic_title: "Старший преподаватель", bio: "Школа веб-разработки" },
  { user_id: -7, full_name: "Мухамеджанов Тимур Русланович", photo_url: null, experience_years: 5, academic_degree: null, academic_title: "Преподаватель", bio: "Школа кибербезопасности" },
  { user_id: -8, full_name: "Карибаева Сауле Нурлановна", photo_url: null, experience_years: 19, academic_degree: "д.т.н.", academic_title: "Профессор", bio: "Школа искусственного интеллекта" },
  { user_id: -9, full_name: "Достанов Ербол Канатович", photo_url: null, experience_years: 13, academic_degree: "к.т.н.", academic_title: "Доцент", bio: "Школа тестирования ПО" },
  { user_id: -10, full_name: "Нуржанова Аружан Талгатовна", photo_url: null, experience_years: 7, academic_degree: null, academic_title: "Старший преподаватель", bio: "Школа Data Science" },
];

export function TeachersPage() {
  const { t, lang } = useI18n();
  const [teachers, setTeachers] = useState<TeacherProfile[]>([]);
  useEffect(() => {
    dataApi.publicTeachers()
      .then((list) => setTeachers(list.length ? list : FALLBACK_FACULTY))
      .catch(() => setTeachers(FALLBACK_FACULTY));
  }, []);
  return (
    <div className="container">
      <div className="page-head">
        <h2>{t("teachers_title")}</h2>
        <p className="muted">{t("faculty_subtitle")}</p>
      </div>
      <div className="faculty-grid">
        {teachers.map((tt) => (
          <article key={tt.user_id} className="faculty-card">
            <div className="faculty-photo">
              {tt.photo_url
                ? <img src={tt.photo_url} alt={tt.full_name} />
                : <span>{initials(tt.full_name)}</span>}
            </div>
            <div className="faculty-info">
              <h4>{tt.full_name}</h4>
              {tt.academic_title && <p className="faculty-title">{tValue(tt.academic_title, lang)}</p>}
              {tt.bio && <p className="muted">{tValue(tt.bio, lang)}</p>}
            </div>
          </article>
        ))}
        {teachers.length === 0 && <p className="muted">{t("loading")}</p>}
      </div>
    </div>
  );
}

// ============================ ВХОД ============================
export function LoginPage() {
  const { t } = useI18n();
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // переводит код ошибки от бэкенда в текст на языке пользователя; иначе показывает как есть
  const authErr = (raw: string) =>
    ["account_not_found", "pending_approval", "oauth_failed", "oauth_unconfigured"].includes(raw)
      ? t(`err_${raw}`) : raw;

  // ошибка из Google OAuth-редиректа (?err=код)
  useEffect(() => {
    const e = params.get("err");
    if (e) setToast(authErr(e));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch (err) {
      setToast(authErr(apiErr(err)));
    } finally {
      setBusy(false);
    }
  };

  // прямой top-level переход (не XHR): так cookie со state доезжает обратно на мобильных
  const google = () => { window.location.href = "/api/auth/google/login"; };

  return (
    <div className="container narrow">
      <Card title={t("login")}>
        <form onSubmit={submit} className="form">
          <label>{t("email")}<input type="email" value={email} required
            onChange={(e) => setEmail(e.target.value)} /></label>
          <label>{t("password")}<input type="password" value={password} required
            onChange={(e) => setPassword(e.target.value)} /></label>
          <button className="btn" disabled={busy}>{busy ? "..." : t("login")}</button>
        </form>
        <div className="divider">или</div>
        <button className="btn google" onClick={google}>
          <svg className="g-icon" viewBox="0 0 48 48" width="18" height="18" aria-hidden="true">
            <path fill="#FFC107" d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"/>
            <path fill="#FF3D00" d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"/>
            <path fill="#4CAF50" d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238C29.211 35.091 26.715 36 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"/>
            <path fill="#1976D2" d="M43.611 20.083H42V20H24v8h11.303c-.792 2.237-2.231 4.166-4.087 5.571l6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"/>
          </svg>
          {t("google_login")}
        </button>
        <p className="muted">Нет аккаунта? <Link to="/register">{t("register")}</Link></p>
      </Card>
      {toast && <Toast msg={toast} kind="err" onClose={() => setToast(null)} />}
    </div>
  );
}

// ============================ РЕГИСТРАЦИЯ ============================
export function RegisterPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", phone: "", password: "", full_name: "" });
  const [toast, setToast] = useState<{ m: string; k: "ok" | "err" } | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.value });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      // recaptcha_token подставляется здесь при включённой reCAPTCHA
      const resp = await authApi.register(form);
      const userId = (resp.data as { user_id: number }).user_id;
      navigate(`/verify?user_id=${userId}`);
    } catch (err) {
      setToast({ m: apiErr(err), k: "err" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="container narrow">
      <Card title={t("register")}>
        <form onSubmit={submit} className="form">
          <label>{t("full_name")}<input value={form.full_name} required onChange={set("full_name")} /></label>
          <label>{t("email")}<input type="email" value={form.email} required onChange={set("email")} /></label>
          <label>{t("phone")}<input placeholder="+77011234567" value={form.phone} required onChange={set("phone")} /></label>
          <label>{t("password")}<input type="password" value={form.password} required onChange={set("password")} /></label>
          <small className="muted">Минимум 8 символов, буквы и цифры.</small>
          <button className="btn" disabled={busy}>{busy ? "..." : t("register")}</button>
        </form>
      </Card>
      {toast && <Toast msg={toast.m} kind={toast.k} onClose={() => setToast(null)} />}
    </div>
  );
}

// ============================ ПОДТВЕРЖДЕНИЕ (email + телефон) ============================
export function VerifyPage() {
  const { t } = useI18n();
  const [params] = useSearchParams();
  const userId = Number(params.get("user_id"));
  const [toast, setToast] = useState<{ m: string; k: "ok" | "err" } | null>(null);

  const resend = () =>
    authApi.resendCode(userId)
      .then(() => setToast({ m: "Письмо отправлено повторно", k: "ok" }))
      .catch((err) => setToast({ m: apiErr(err), k: "err" }));

  return (
    <div className="container narrow">
      <Card title={t("verify_title")}>
        <div className="verify-step">
          <h4>{t("email")}</h4>
          <p className="muted">{t("verify_email_sent")}</p>
          <button className="btn ghost" onClick={resend}>{t("resend")}</button>
        </div>
        <hr />
        <p className="muted">После подтверждения email <Link to="/login">войдите</Link>.</p>
      </Card>
      {toast && <Toast msg={toast.m} kind={toast.k} onClose={() => setToast(null)} />}
    </div>
  );
}

// ============================ ПОДТВЕРЖДЕНИЕ EMAIL ПО ССЫЛКЕ ============================
export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const [status, setStatus] = useState("Проверяем токен...");
  useEffect(() => {
    const token = params.get("token");
    if (!token) { setStatus("Токен отсутствует"); return; }
    authApi.verifyEmail(token)
      .then(() => setStatus("Email подтверждён! Теперь подтвердите телефон и войдите."))
      .catch((err) => setStatus(apiErr(err)));
  }, [params]);
  return (
    <div className="container narrow">
      <Card title="Подтверждение email"><p>{status}</p><Link to="/login">Ко входу</Link></Card>
    </div>
  );
}

// ============================ ВОЗВРАТ ПОСЛЕ GOOGLE OAUTH ============================
export function OAuthDonePage() {
  const navigate = useNavigate();
  const { refreshMe } = useAuth();
  useEffect(() => {
    (async () => {
      await authApi.refresh();
      await refreshMe();
      navigate("/dashboard");
    })();
  }, [navigate, refreshMe]);
  return <div className="container">Завершаем вход через Google...</div>;
}

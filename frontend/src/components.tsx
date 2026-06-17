// Общие UI-компоненты: Navbar, Footer, LanguageSwitcher, NewsFeed, Card, Toast, NotificationsBell.
import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { dataApi } from "./api";
import { useAuth } from "./auth";
import { tValue, useI18n } from "./i18n";
import type { Lang, NewsItem, Notification } from "./types";

// ----- Переключатель языков KZ / EN / RU -----
export function LanguageSwitcher() {
  const { lang, setLang } = useI18n();
  const langs: Lang[] = ["kz", "en", "ru"];
  return (
    <div className="lang-switch">
      {langs.map((l) => (
        <button key={l} className={l === lang ? "active" : ""} onClick={() => setLang(l)}>
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

// ----- Верхняя навигация + блок авторизации/профиля -----
export function Navbar() {
  const { t } = useI18n();
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  return (
    <header className="navbar">
      <div className="navbar-inner container">
        <Link to="/" className="logo" onClick={close}>
          <img className="logo-img" src="/logo.png" alt=""
            onError={(e) => { const i = e.currentTarget; if (!i.dataset.fb) { i.dataset.fb = "1"; i.src = "/logo.svg"; } }} />
          Digital Academy
        </Link>
        <button className="nav-toggle" aria-label="Меню" aria-expanded={open}
                onClick={() => setOpen((o) => !o)}>
          {open ? "✕" : "☰"}
        </button>
        <div className={`nav-collapse ${open ? "open" : ""}`}>
          <nav className="nav-links" onClick={close}>
            <Link to="/">{t("nav_home")}</Link>
            <Link to="/courses">{t("nav_courses")}</Link>
            {me && <Link to="/schedule">{t("nav_schedule")}</Link>}
            <Link to="/teachers">{t("nav_teachers")}</Link>
            <Link to="/about">{t("nav_about")}</Link>
            {(me?.user.role === "student" || me?.user.role === "admin") && <Link to="/enroll">{t("nav_enroll")}</Link>}
            {me && <Link to="/dashboard">{t("nav_dashboard")}</Link>}
          </nav>
          <div className="navbar-right">
            <LanguageSwitcher />
            {me && <NotificationsBell />}
            {me ? (
              <div className="profile-box">
                <span className="role-badge">{me.user.role}</span>
                <button className="btn ghost" onClick={() => { close(); logout().then(() => navigate("/")); }}>
                  {t("logout")}
                </button>
              </div>
            ) : (
              <div className="auth-box">
                <button className="btn ghost" onClick={() => { close(); navigate("/login"); }}>{t("login")}</button>
                <button className="btn" onClick={() => { close(); navigate("/register"); }}>{t("register")}</button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

// ----- Колокол уведомлений -----
export function NotificationsBell() {
  const [items, setItems] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);
  const { t } = useI18n();

  const load = () => dataApi.notifications().then(setItems).catch(() => {});
  useEffect(() => {
    load();
    const id = setInterval(load, 20000);
    return () => clearInterval(id);
  }, []);

  const unread = items.filter((i) => !i.is_read).length;
  return (
    <div className="bell">
      <button className="btn ghost" onClick={() => setOpen((o) => !o)}>
        🔔{unread > 0 && <span className="badge">{unread}</span>}
      </button>
      {open && (
        <div className="dropdown">
          <div className="dropdown-title">{t("notifications")}</div>
          {items.length === 0 && <div className="muted">—</div>}
          {items.map((n) => (
            <div key={n.id} className={`notif ${n.is_read ? "" : "unread"}`}
                 onClick={() => dataApi.markRead(n.id).then(load)}>
              <b>{n.title}</b>
              <div>{n.message}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ----- Карточка -----
export function Card({ title, children, actions }: { title?: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <div className="card">
      {title && <div className="card-head"><h3>{title}</h3>{actions}</div>}
      <div className="card-body">{children}</div>
    </div>
  );
}

// ----- Тост-уведомление -----
export function Toast({ msg, kind, onClose }: { msg: string; kind: "ok" | "err"; onClose: () => void }) {
  useEffect(() => {
    const id = setTimeout(onClose, 4000);
    return () => clearTimeout(id);
  }, [onClose]);
  return <div className={`toast ${kind}`} onClick={onClose}>{msg}</div>;
}

// ----- Лента новостей -----
export function NewsFeed() {
  const { t, lang } = useI18n();
  const [items, setItems] = useState<NewsItem[]>([]);
  useEffect(() => {
    dataApi.news().then(setItems).catch(() => {});
  }, []);
  return (
    <Card title={t("news_feed")}>
      {items.length === 0 && <div className="muted">{t("loading")}</div>}
      <div className="news-list">
        {items.map((n) => (
          <article key={n.id} className="news-item">
            <span className={`tag tag-${n.category}`}>{t(`label_${n.category}`)}</span>
            <h4>{tValue(n.title, lang)}</h4>
            <p>{tValue(n.body, lang)}</p>
            {n.event_date && <small>📅 {new Date(n.event_date).toLocaleString()}</small>}
            <small className="muted"> · {new Date(n.created_at).toLocaleDateString()}</small>
          </article>
        ))}
      </div>
    </Card>
  );
}

// ----- Подвал -----
export function Footer() {
  const { t } = useI18n();
  return (
    <footer className="footer">
      <div className="container footer-grid">
        <div>
          <h4>{t("contacts")}</h4>
          <p>📍 г. Алматы, ул. Цифрлық, 1</p>
          <p>✉️ info@digital-academy.kz</p>
          <p>☎️ +7 (700) 000-00-00</p>
        </div>
        <div>
          <h4>{t("social")}</h4>
          <p><a href="#">Instagram</a> · <a href="#">Telegram</a></p>
          <p><a href="#">YouTube</a> · <a href="#">LinkedIn</a></p>
        </div>
        <div>
          <h4>{t("authors")}</h4>
          <p>Козыбаева Салтанат Алибековна</p>
          <p>Даутов Дамир Жұмабекұлы</p>
        </div>
      </div>
      <div className="footer-bottom">© {new Date().getFullYear()} Digital Academy</div>
    </footer>
  );
}

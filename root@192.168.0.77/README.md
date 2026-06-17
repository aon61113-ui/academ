# Digital Academy — веб-платформа

Образовательная платформа: надёжная авторизация с RBAC, личные кабинеты (Студент,
Преподаватель, Студсовет, Администрация), новости, расписание, оценки и модуль
«Запись по дисциплинам».

**Стек:** FastAPI (Python) · React + TypeScript (Vite) · MySQL · деплой на Debian.

## Структура

```
backend/      FastAPI: config, database, models, schemas, security (RBAC),
              services, routers/{auth,users,academy}, migrations/schema.sql, seed.py
frontend/     React+TS: api, auth (RBAC), i18n (KZ/EN/RU), types,
              components, pages, dashboards, enrollment, styles
docker-compose.yml
```

## Безопасность авторизации (ключевое)

- Пароли — **argon2**; access-JWT (15 мин, в памяти) + **refresh-токен** в httpOnly-cookie
  с ротацией и отзывом в БД.
- Подтверждение **email** (ссылка-токен) и **телефона** (6-значный код), хранятся хэшами,
  TTL 15 мин, лимит попыток. Доступ в кабинеты — только после обоих подтверждений.
- **Google OAuth 2.0** (с проверкой `state` против CSRF).
- Защита регистрации: валидация (E.164, надёжный пароль), **reCAPTCHA**, **rate limiting**
  на отправку кодов/вход, блокировка после 5 неудачных входов.
- **CSRF** (double-submit cookie) на cookie-эндпоинтах `/refresh` и `/logout`.
- **RBAC** через зависимость `require_role(...)` на каждом защищённом эндпоинте +
  `<ProtectedRoute roles=[...]>` на фронте.

> В режиме разработки `EMAIL_ENABLED=false` и `SMS_ENABLED=false` — коды печатаются
> в **консоль бэкенда**, проект запускается без платных провайдеров.

---

## Вариант 1. Запуск через Docker (быстрее всего)

```bash
cp backend/.env.example backend/.env        # при желании поправьте значения
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend (Swagger): http://localhost:8000/docs
- БД-схема загружается автоматически, демо-данные наполняет `seed.py`.

## Вариант 2. Локальный запуск (без Docker)

**1) MySQL** (создать схему):
```bash
mysql -u root -p < backend/migrations/schema.sql
# создать пользователя academy / academy_pass (или поправить .env)
```

**2) Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # заполнить JWT_SECRET и БД
python seed.py                                       # демо-данные
uvicorn main:app --reload
```

**3) Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Демо-логины (пароль у всех: `Passw0rd!`)

| Роль          | Email                 |
|---------------|-----------------------|
| Администрация | admin@academy.kz      |
| Студсовет     | council@academy.kz    |
| Преподаватель | teacher@academy.kz    |
| Студент       | student@academy.kz    |

> Демо-пользователи уже подтверждены. Новые регистрации проходят подтверждение
> email + телефона (коды — в консоли бэкенда в dev-режиме).

---

## Деплой на Debian (production)

```bash
# 1. Зависимости
sudo apt update && sudo apt install -y python3-venv python3-pip mysql-server nginx nodejs npm

# 2. База
sudo mysql < /opt/academy/backend/migrations/schema.sql
sudo mysql -e "CREATE USER 'academy'@'localhost' IDENTIFIED BY 'STRONG_PASS';
               GRANT ALL ON digital_academy.* TO 'academy'@'localhost';"

# 3. Backend (venv + gunicorn/uvicorn workers)
cd /opt/academy/backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt gunicorn
# .env: COOKIE_SECURE=true, реальные JWT_SECRET, SMTP, SMS, Google, reCAPTCHA

# 4. Frontend (статическая сборка)
cd /opt/academy/frontend && npm ci && npm run build   # → dist/
```

**systemd-юнит** `/etc/systemd/system/academy.service`:
```ini
[Unit]
Description=Digital Academy API
After=network.target mysql.service

[Service]
WorkingDirectory=/opt/academy/backend
ExecStart=/opt/academy/backend/.venv/bin/gunicorn main:app \
  -k uvicorn.workers.UvicornWorker -w 4 -b 127.0.0.1:8000
EnvironmentFile=/opt/academy/backend/.env
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now academy
```

**nginx** `/etc/nginx/sites-available/academy` (статика + проксирование API):
```nginx
server {
    listen 80;
    server_name digital-academy.kz;

    root /opt/academy/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location / { try_files $uri /index.html; }   # SPA-роутинг
}
```
```bash
sudo ln -s /etc/nginx/sites-available/academy /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
# HTTPS: sudo certbot --nginx   (обязательно для COOKIE_SECURE=true)
```

-- ============================================================
--  Digital Academy — MySQL schema (single migration script)
--  Engine: InnoDB | Charset: utf8mb4 | Collation: utf8mb4_unicode_ci
--  Запуск: mysql -u root -p < migrations/schema.sql
-- ============================================================
CREATE DATABASE IF NOT EXISTS digital_academy
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE digital_academy;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ---------------- СПРАВОЧНИКИ ----------------
CREATE TABLE IF NOT EXISTS specialties (
  id        SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  code      VARCHAR(40)  NOT NULL UNIQUE,
  name_ru   VARCHAR(120) NOT NULL,
  name_kz   VARCHAR(120) NOT NULL,
  name_en   VARCHAR(120) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS student_groups (
  id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name            VARCHAR(40) NOT NULL UNIQUE,
  specialty_id    SMALLINT UNSIGNED NOT NULL,
  course          TINYINT UNSIGNED NOT NULL,
  curator_user_id BIGINT UNSIGNED NULL,
  FOREIGN KEY (specialty_id) REFERENCES specialties(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------- ЯДРО АВТОРИЗАЦИИ / RBAC ----------------
CREATE TABLE IF NOT EXISTS users (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  email           VARCHAR(255) NOT NULL UNIQUE,
  phone           VARCHAR(20)  NOT NULL UNIQUE,
  password_hash   VARCHAR(255) NULL,
  role            ENUM('student','teacher','admin','council') NOT NULL DEFAULT 'student',
  google_id       VARCHAR(64)  NULL UNIQUE,
  email_verified  TINYINT(1)   NOT NULL DEFAULT 0,
  phone_verified  TINYINT(1)   NOT NULL DEFAULT 0,
  is_active       TINYINT(1)   NOT NULL DEFAULT 1,
  failed_logins   SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  locked_until    DATETIME NULL,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_users_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS verification_codes (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     BIGINT UNSIGNED NOT NULL,
  channel     ENUM('email','phone') NOT NULL,
  code_hash   VARCHAR(255) NOT NULL,
  expires_at  DATETIME NOT NULL,
  consumed_at DATETIME NULL,
  attempts    TINYINT UNSIGNED NOT NULL DEFAULT 0,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_vc_user_channel (user_id, channel)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS refresh_tokens (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     BIGINT UNSIGNED NOT NULL,
  token_hash  CHAR(64) NOT NULL UNIQUE,
  user_agent  VARCHAR(255) NULL,
  ip_address  VARCHAR(45) NULL,
  expires_at  DATETIME NOT NULL,
  revoked_at  DATETIME NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_rt_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS rate_limit_events (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  scope_key   VARCHAR(120) NOT NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_rl_scope_time (scope_key, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------- ПРОФИЛИ ----------------
CREATE TABLE IF NOT EXISTS student_profiles (
  user_id        BIGINT UNSIGNED PRIMARY KEY,
  student_code   VARCHAR(12) NOT NULL UNIQUE,
  full_name      VARCHAR(150) NOT NULL,
  photo_url      VARCHAR(255) NULL,
  gpa            DECIMAL(3,2) NOT NULL DEFAULT 0.00,
  course         TINYINT UNSIGNED NOT NULL,
  birth_year     SMALLINT UNSIGNED NULL,
  admission_year SMALLINT UNSIGNED NULL,
  specialty_id   SMALLINT UNSIGNED NULL,
  group_id       INT UNSIGNED NULL,
  FOREIGN KEY (user_id)      REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (specialty_id) REFERENCES specialties(id),
  FOREIGN KEY (group_id)     REFERENCES student_groups(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS teacher_profiles (
  user_id          BIGINT UNSIGNED PRIMARY KEY,
  full_name        VARCHAR(150) NOT NULL,
  photo_url        VARCHAR(255) NULL,
  experience_years TINYINT UNSIGNED NOT NULL DEFAULT 0,
  academic_degree  VARCHAR(120) NULL,
  academic_title   VARCHAR(120) NULL,
  bio              TEXT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------- УЧЕБНАЯ ЧАСТЬ ----------------
CREATE TABLE IF NOT EXISTS disciplines (
  id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  title        VARCHAR(150) NOT NULL,
  specialty_id SMALLINT UNSIGNED NOT NULL,
  course       TINYINT UNSIGNED NOT NULL,
  description  TEXT NULL,
  FOREIGN KEY (specialty_id) REFERENCES specialties(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS teacher_disciplines (
  teacher_user_id BIGINT UNSIGNED NOT NULL,
  discipline_id   INT UNSIGNED NOT NULL,
  PRIMARY KEY (teacher_user_id, discipline_id),
  FOREIGN KEY (teacher_user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (discipline_id)   REFERENCES disciplines(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS schedule_entries (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  discipline_id   INT UNSIGNED NOT NULL,
  group_id        INT UNSIGNED NOT NULL,
  teacher_user_id BIGINT UNSIGNED NOT NULL,
  day_of_week     TINYINT UNSIGNED NOT NULL,
  start_time      TIME NOT NULL,
  end_time        TIME NOT NULL,
  room            VARCHAR(40) NULL,
  lesson_type     VARCHAR(20) NOT NULL DEFAULT 'lecture',
  FOREIGN KEY (discipline_id)   REFERENCES disciplines(id),
  FOREIGN KEY (group_id)        REFERENCES student_groups(id),
  FOREIGN KEY (teacher_user_id) REFERENCES users(id),
  INDEX idx_sched_group_day (group_id, day_of_week),
  INDEX idx_sched_teacher_day (teacher_user_id, day_of_week)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS grades (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  student_user_id BIGINT UNSIGNED NOT NULL,
  discipline_id   INT UNSIGNED NOT NULL,
  teacher_user_id BIGINT UNSIGNED NOT NULL,
  value           DECIMAL(4,1) NOT NULL,
  grade_type      VARCHAR(40) NOT NULL DEFAULT 'current',
  comment         VARCHAR(255) NULL,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (student_user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (discipline_id)   REFERENCES disciplines(id),
  FOREIGN KEY (teacher_user_id) REFERENCES users(id),
  INDEX idx_grades_student (student_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------- КОНТЕНТ ----------------
CREATE TABLE IF NOT EXISTS news (
  id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  title          VARCHAR(200) NOT NULL,
  body           TEXT NOT NULL,
  category       ENUM('news','announcement','event') NOT NULL DEFAULT 'news',
  author_user_id BIGINT UNSIGNED NOT NULL,
  event_date     DATETIME NULL,
  is_published   TINYINT(1) NOT NULL DEFAULT 1,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (author_user_id) REFERENCES users(id),
  INDEX idx_news_cat_pub (category, is_published, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------- ЗАПИСЬ ПО ДИСЦИПЛИНАМ ----------------
CREATE TABLE IF NOT EXISTS course_offerings (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  discipline_id   INT UNSIGNED NOT NULL,
  teacher_user_id BIGINT UNSIGNED NOT NULL,
  specialty_id    SMALLINT UNSIGNED NOT NULL,
  course          TINYINT UNSIGNED NOT NULL,
  session_date    DATE NOT NULL,
  start_time      TIME NOT NULL,
  room            VARCHAR(40) NULL,
  total_seats     SMALLINT UNSIGNED NOT NULL,
  available_seats SMALLINT UNSIGNED NOT NULL,
  status          ENUM('open','full','closed') NOT NULL DEFAULT 'open',
  FOREIGN KEY (discipline_id)   REFERENCES disciplines(id),
  FOREIGN KEY (teacher_user_id) REFERENCES users(id),
  FOREIGN KEY (specialty_id)    REFERENCES specialties(id),
  INDEX idx_off_filters (specialty_id, course, session_date, teacher_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS enrollments (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  offering_id     BIGINT UNSIGNED NOT NULL,
  student_user_id BIGINT UNSIGNED NOT NULL,
  status          ENUM('booked','cancelled') NOT NULL DEFAULT 'booked',
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_offer_student (offering_id, student_user_id),
  FOREIGN KEY (offering_id)     REFERENCES course_offerings(id) ON DELETE CASCADE,
  FOREIGN KEY (student_user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------- УВЕДОМЛЕНИЯ ----------------
CREATE TABLE IF NOT EXISTS notifications (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     BIGINT UNSIGNED NOT NULL,
  title       VARCHAR(150) NOT NULL,
  message     VARCHAR(500) NOT NULL,
  type        VARCHAR(40) NOT NULL DEFAULT 'info',
  is_read     TINYINT(1) NOT NULL DEFAULT 0,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_notif_user_read (user_id, is_read)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- FK кураторства (после создания users)
ALTER TABLE student_groups
  ADD CONSTRAINT fk_group_curator FOREIGN KEY (curator_user_id)
  REFERENCES users(id) ON DELETE SET NULL;

-- ---------------- SEED: специальности ----------------
INSERT INTO specialties (code, name_ru, name_kz, name_en) VALUES
 ('software',     'Программное обеспечение','Бағдарламалық қамтамасыз ету','Software Engineering'),
 ('cybersec',     'Кибербезопасность',      'Киберқауіпсіздік',           'Cybersecurity'),
 ('data_science', 'Data Science',           'Data Science',               'Data Science'),
 ('qa',           'Тестировщик',            'Тестілеуші',                 'QA Engineer'),
 ('fullstack',    'Fullstack разработчик',  'Fullstack әзірлеуші',        'Fullstack Developer')
ON DUPLICATE KEY UPDATE code = VALUES(code);

SET FOREIGN_KEY_CHECKS = 1;

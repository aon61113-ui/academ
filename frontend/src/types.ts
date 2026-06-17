// Все TypeScript-типы платформы в одном файле.

export type Role = "student" | "teacher" | "admin" | "council";
export type Lang = "ru" | "kz" | "en";

export interface User {
  id: number;
  email: string;
  phone: string;
  role: Role;
  email_verified: boolean;
  phone_verified: boolean;
  is_active: boolean;
  created_at: string;
}

export interface StudentProfile {
  user_id: number;
  student_code: string;
  full_name: string;
  photo_url: string | null;
  gpa: number;
  course: number;
  birth_year: number | null;
  admission_year: number | null;
  specialty_id: number | null;
  group_id: number | null;
}

export interface TeacherProfile {
  user_id: number;
  full_name: string;
  photo_url: string | null;
  experience_years: number;
  academic_degree: string | null;
  academic_title: string | null;
  bio: string | null;
}

export interface Me {
  user: User;
  student_profile: StudentProfile | null;
  teacher_profile: TeacherProfile | null;
  discipline_ids: number[];
}

export interface Specialty {
  id: number;
  code: string;
  name_ru: string;
  name_kz: string;
  name_en: string;
}

export interface Discipline {
  id: number;
  title: string;
  specialty_id: number;
  course: number;
  description: string | null;
}

export interface Group {
  id: number;
  name: string;
  specialty_id: number;
  course: number;
}

export interface NewsItem {
  id: number;
  title: string;
  body: string;
  category: "news" | "announcement" | "event";
  author_user_id: number;
  event_date: string | null;
  is_published: boolean;
  created_at: string;
}

export interface ScheduleEntry {
  id: number;
  discipline_id: number;
  group_id: number;
  teacher_user_id: number;
  day_of_week: number;
  start_time: string;
  end_time: string;
  room: string | null;
  lesson_type: "lecture" | "practice" | "lab";
  discipline_title: string | null;
  group_name: string | null;
  teacher_name: string | null;
}

export interface TeacherClass {
  group_id: number;
  group_name: string;
  course: number;
  disciplines: { id: number; title: string }[];
  students: { user_id: number; full_name: string; student_code: string }[];
}

export interface Grade {
  id: number;
  student_user_id: number;
  discipline_id: number;
  teacher_user_id: number;
  value: number;
  grade_type: string;
  comment: string | null;
  created_at: string;
  discipline_title: string | null;
}

export interface Offering {
  id: number;
  discipline_id: number;
  teacher_user_id: number;
  specialty_id: number;
  course: number;
  session_date: string;
  start_time: string;
  room: string | null;
  total_seats: number;
  available_seats: number;
  status: "open" | "full" | "closed";
  discipline_title: string | null;
  teacher_name: string | null;
  specialty_name: string | null;
  is_booked_by_me: boolean;
}

export interface AdminProfile {
  user: User;
  student_profile: StudentProfile | null;
  teacher_profile: TeacherProfile | null;
}

export interface AdminProfileUpdate {
  email?: string;
  phone?: string;
  full_name?: string;
  gpa?: number;
  course?: number;
  birth_year?: number;
  admission_year?: number;
  academic_title?: string;
  academic_degree?: string;
  experience_years?: number;
  bio?: string;
}

export interface LimitedStudent {
  user_id: number;
  student_code: string;
  full_name: string;
  course: number;
  group_id: number | null;
}

export interface Notification {
  id: number;
  title: string;
  message: string;
  type: string;
  is_read: boolean;
  created_at: string;
}

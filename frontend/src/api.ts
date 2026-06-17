// Axios-клиент + все вызовы API. Access-токен хранится в памяти (не в localStorage),
// refresh — в httpOnly cookie; при 401 происходит прозрачный refresh и повтор запроса.
import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import type {
  AdminProfile, AdminProfileUpdate, Discipline, Grade, Group, LimitedStudent, Me, NewsItem,
  Notification, Offering, ScheduleEntry, Specialty, TeacherClass, TeacherProfile, User, Role,
} from "./types";

export interface TokenResponseT {
  access_token: string;
  token_type: string;
  expires_in: number;
}

let accessToken: string | null = null;
export const setAccessToken = (t: string | null) => {
  accessToken = t;
};
export const getAccessToken = () => accessToken;

// читаем CSRF-токен из cookie (double-submit) и кладём в заголовок
function csrfFromCookie(): string | null {
  const m = document.cookie.match(/(?:^|;\s*)da_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

export const api = axios.create({
  baseURL: "/api",
  withCredentials: true, // отправлять cookie
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  const method = (config.method || "get").toLowerCase();
  if (["post", "put", "patch", "delete"].includes(method)) {
    const csrf = csrfFromCookie();
    if (csrf) config.headers["X-CSRF-Token"] = csrf;
  }
  return config;
});

// Прозрачный refresh при 401 (один раз на запрос)
let refreshing: Promise<string | null> | null = null;

async function doRefresh(): Promise<string | null> {
  try {
    const csrf = csrfFromCookie();
    const resp = await axios.post<TokenResponseT>(
      "/api/auth/refresh",
      {},
      { withCredentials: true, headers: csrf ? { "X-CSRF-Token": csrf } : {} },
    );
    accessToken = resp.data.access_token;
    return accessToken;
  } catch {
    accessToken = null;
    return null;
  }
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retried?: boolean };
    const isAuthCall = original?.url?.includes("/auth/login") || original?.url?.includes("/auth/refresh");
    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {
      original._retried = true;
      refreshing = refreshing || doRefresh();
      const token = await refreshing;
      refreshing = null;
      if (token) {
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      }
    }
    return Promise.reject(error);
  },
);

// ------------------------- AUTH -------------------------
export const authApi = {
  register: (data: { email: string; phone: string; password: string; full_name: string; recaptcha_token?: string }) =>
    api.post("/auth/register", data),
  login: async (email: string, password: string, recaptcha_token?: string) => {
    const resp = await api.post<TokenResponseT>("/auth/login", { email, password, recaptcha_token });
    setAccessToken(resp.data.access_token);
    return resp.data;
  },
  refresh: doRefresh,
  logout: () => api.post("/auth/logout").finally(() => setAccessToken(null)),
  me: () => api.get<Me>("/auth/me").then((r) => r.data),
  verifyEmail: (token: string) => api.post("/auth/verify-email", { token }),
  resendCode: (userId: number) => api.post(`/auth/resend-code?user_id=${userId}`),
  googleLogin: () => api.get<{ url: string }>("/auth/google/login").then((r) => r.data.url),
};

// ------------------------- ACADEMY / DATA -------------------------
export const dataApi = {
  news: (category?: string) =>
    api.get<NewsItem[]>("/news", { params: category ? { category } : {} }).then((r) => r.data),
  createNews: (data: Partial<NewsItem>) => api.post<NewsItem>("/news", data).then((r) => r.data),
  deleteNews: (id: number) => api.delete(`/news/${id}`),

  specialties: () => api.get<Specialty[]>("/specialties").then((r) => r.data),
  disciplines: (params?: { specialty_id?: number; course?: number }) =>
    api.get<Discipline[]>("/disciplines", { params }).then((r) => r.data),
  groups: () => api.get<Group[]>("/groups").then((r) => r.data),
  publicTeachers: () => api.get<TeacherProfile[]>("/users/teachers/public").then((r) => r.data),

  scheduleToday: () => api.get<ScheduleEntry[]>("/schedule/today").then((r) => r.data),
  scheduleWeek: () => api.get<ScheduleEntry[]>("/schedule/week").then((r) => r.data),
  schedulePublic: (groupId?: number) =>
    api.get<ScheduleEntry[]>("/schedule/public", { params: groupId ? { group_id: groupId } : {} })
      .then((r) => r.data),

  teacherClasses: () => api.get<TeacherClass[]>("/users/teacher/classes").then((r) => r.data),
  myGrades: () => api.get<Grade[]>("/users/grades/me").then((r) => r.data),
  createGrade: (data: { student_user_id: number; discipline_id: number; value: number; grade_type?: string; comment?: string }) =>
    api.post<Grade>("/users/grades", data).then((r) => r.data),

  offerings: (params: { specialty_id?: number; course?: number; teacher_user_id?: number; session_date?: string; student_user_id?: number }) =>
    api.get<Offering[]>("/offerings", { params }).then((r) => r.data),
  book: (id: number, studentUserId?: number) =>
    api.post<Offering>(`/offerings/${id}/book`, null, { params: studentUserId ? { student_user_id: studentUserId } : {} }).then((r) => r.data),
  cancelBook: (id: number, studentUserId?: number) =>
    api.post<Offering>(`/offerings/${id}/cancel`, null, { params: studentUserId ? { student_user_id: studentUserId } : {} }).then((r) => r.data),

  notifications: () => api.get<Notification[]>("/notifications").then((r) => r.data),
  markRead: (id: number) => api.post(`/notifications/${id}/read`),
};

// ------------------------- ADMIN -------------------------
export const adminApi = {
  users: (role?: Role) => api.get<User[]>("/users/admin", { params: role ? { role } : {} }).then((r) => r.data),
  createUser: (data: { email: string; phone: string; password: string; role: Role; full_name: string }) =>
    api.post<User>("/users/admin", data).then((r) => r.data),
  updateUser: (id: number, data: { role?: Role; is_active?: boolean }) =>
    api.patch<User>(`/users/admin/${id}`, data).then((r) => r.data),
  deleteUser: (id: number) => api.delete(`/users/admin/${id}`),
  getProfile: (id: number) => api.get<AdminProfile>(`/users/admin/${id}/profile`).then((r) => r.data),
  updateProfile: (id: number, data: AdminProfileUpdate) =>
    api.patch<AdminProfile>(`/users/admin/${id}/profile`, data).then((r) => r.data),
  council_students: () => api.get<LimitedStudent[]>("/users/students/limited").then((r) => r.data),
};

export function apiErr(e: unknown): string {
  const ax = e as AxiosError<{ detail?: unknown }>;
  const d = ax.response?.data?.detail;
  if (typeof d === "string") return d;
  // FastAPI на ошибках валидации (422) присылает detail массивом объектов {msg,...}
  if (Array.isArray(d)) {
    const msgs = d
      .map((x) => (x && typeof x === "object" && "msg" in x ? String((x as { msg: unknown }).msg) : String(x)))
      .map((m) => m.replace(/^Value error,\s*/i, ""))  // убираем технический префикс Pydantic
      .filter(Boolean);
    if (msgs.length) return msgs.join("; ");
  }
  return "Произошла ошибка. Попробуйте ещё раз.";
}

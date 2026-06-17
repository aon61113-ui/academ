// Корневой компонент: провайдеры (i18n, Auth), layout (Navbar/Footer) и маршрутизация с RBAC.
import { useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider, ProtectedRoute } from "./auth";
import { Footer, Navbar } from "./components";
import { AdminUserProfile, Dashboard } from "./dashboards";
import { EnrollmentPage } from "./enrollment";
import { I18nContext } from "./i18n";
import {
  AboutPage, CoursesPage, HomePage, LoginPage, OAuthDonePage, RegisterPage,
  SchedulePage, TeachersPage, VerifyEmailPage, VerifyPage,
} from "./pages";
import type { Lang } from "./types";
import "./styles.css";

export default function App() {
  const [lang, setLang] = useState<Lang>((localStorage.getItem("lang") as Lang) || "kz");
  const setAndStore = (l: Lang) => { localStorage.setItem("lang", l); setLang(l); };

  return (
    <I18nContext.Provider value={{ lang, setLang: setAndStore }}>
      <BrowserRouter>
        <AuthProvider>
          <Navbar />
          <main className="page">
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/about" element={<AboutPage />} />
              <Route path="/teachers" element={<TeachersPage />} />
              <Route path="/courses" element={<CoursesPage />} />
              <Route path="/schedule" element={
                <ProtectedRoute><SchedulePage /></ProtectedRoute>
              } />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/verify" element={<VerifyPage />} />
              <Route path="/verify-email" element={<VerifyEmailPage />} />
              <Route path="/oauth-done" element={<OAuthDonePage />} />

              {/* Защищённые маршруты (RBAC) */}
              <Route path="/dashboard" element={
                <ProtectedRoute><Dashboard /></ProtectedRoute>
              } />
              <Route path="/enroll" element={
                <ProtectedRoute roles={["student", "admin"]}><EnrollmentPage /></ProtectedRoute>
              } />
              <Route path="/users/:id" element={
                <ProtectedRoute roles={["admin"]}><AdminUserProfile /></ProtectedRoute>
              } />
            </Routes>
          </main>
          <Footer />
        </AuthProvider>
      </BrowserRouter>
    </I18nContext.Provider>
  );
}

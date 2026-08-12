import React, { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import "./styles/design-tokens.css";
import "./styles/components.css";
import { useAuth } from "./context/useAuth";

// Layouts
const PatientLayout = lazy(() => import("./layouts/PatientLayout"));
const ClinicianLayout = lazy(() => import("./layouts/ClinicianLayout"));

// Screens — Patient (Mobile)
const HomeScreen = lazy(() => import("./screens/mobile/HomeScreen/HomeScreen"));
const MonitoringScreen = lazy(() => import("./screens/mobile/MonitoringScreen/MonitoringScreen"));
const HistoryScreen = lazy(() => import("./screens/mobile/HistoryScreen/HistoryScreen"));
const NotificationsScreen = lazy(() => import("./screens/mobile/NotificationsScreen/NotificationsScreen"));
const EducationScreen = lazy(() => import("./screens/mobile/EducationScreen/EducationScreen"));
const SettingsScreen = lazy(() => import("./screens/mobile/SettingsScreen/SettingsScreen"));
const ProfileScreen = lazy(() => import("./screens/mobile/ProfileScreen/ProfileScreen"));

// Screens — Clinician (Web Dashboard)
const ClinicianDashboard = lazy(() => import("./screens/clinician/ClinicianDashboard/ClinicianDashboard"));
const AdminPortal = lazy(() => import("./screens/admin/AdminPortal/AdminPortal"));

// Auth
const AuthScreen = lazy(() => import("./components/AuthScreen/AuthScreen"));
const PasswordResetScreen = lazy(() => import("./components/PasswordResetScreen/PasswordResetScreen"));

// Public screens
const LandingPage = lazy(() => import("./screens/public/LandingPage/LandingPage"));
const PatientPortalPage = lazy(() => import("./screens/public/PortalPages/PortalPages").then(
  (module) => ({ default: module.PatientPortalPage }),
));
const ClinicianPortalPage = lazy(() => import("./screens/public/PortalPages/PortalPages").then(
  (module) => ({ default: module.ClinicianPortalPage }),
));

// ============================================
// PROTECTED ROUTE WRAPPERS
// ============================================

const ROLE_HOME_PATHS = {
  admin: "/admin",
  clinician: "/clinician/dashboard",
  patient: "/patient/home",
};

/**
 * RequireAuth — Redirect ke login sesuai domain jika belum login
 */
function RequireAuth({
  children,
  loginPath = "/login/ibu-hamil",
  allowPasswordResetRequired = false,
}) {
  const { isAuthenticated, isAuthLoading, user } = useAuth();

  if (isAuthLoading) {
    return (
      <div
        className="app font-display"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
        }}
      >
        <p>Memeriksa sesi akun...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to={loginPath} replace />;
  }

  if (user?.must_reset_password && !allowPasswordResetRequired) {
    return <Navigate to="/ganti-password-awal" replace />;
  }

  return children;
}

/**
 * RequireRole — Redirect jika role tidak cocok
 */
function RequireRole({ role, children }) {
  const { user } = useAuth();

  if (!user?.role || user.role !== role) {
    return <Navigate to={ROLE_HOME_PATHS[user?.role] || "/"} replace />;
  }

  return children;
}

/**
 * RoleRedirect — Root "/" handler: arahkan berdasarkan role
 */
function RoleRedirect() {
  const { isAuthenticated, isAuthLoading, user } = useAuth();

  if (isAuthLoading) {
    return (
      <div
        className="app font-display"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
        }}
      >
        <p>Memeriksa sesi akun...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login/ibu-hamil" replace />;
  }

  if (user?.must_reset_password) {
    return <Navigate to="/ganti-password-awal" replace />;
  }

  return (
    <Navigate to={ROLE_HOME_PATHS[user?.role] || "/"} replace />
  );
}

/**
 * LoginGuard — Jika sudah login, redirect ke dashboard masing-masing role.
 * Jika belum, tampilkan AuthScreen.
 */
function LoginGuard({ portal = "general" }) {
  const { isAuthenticated, isAuthLoading, user } = useAuth();

  if (isAuthLoading) {
    return (
      <div
        className="app font-display"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
        }}
      >
        <p>Memeriksa sesi akun...</p>
      </div>
    );
  }

  if (isAuthenticated) {
    if (user?.must_reset_password) {
      return <Navigate to="/ganti-password-awal" replace />;
    }

    return (
      <Navigate to={ROLE_HOME_PATHS[user?.role] || "/"} replace />
    );
  }

  return <AuthScreen portal={portal} />;
}

// ============================================
// APP — ROUTER CORE
// ============================================

function App() {
  return (
    <Suspense fallback={<div className="app font-display" aria-busy="true" />}>
    <Routes>
      {/* === PUBLIC === */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/portal-ibu-hamil" element={<PatientPortalPage />} />
      <Route path="/portal-nakes" element={<ClinicianPortalPage />} />
      <Route
        path="/login"
        element={<Navigate to="/login/ibu-hamil" replace />}
      />
      <Route
        path="/login/ibu-hamil"
        element={<LoginGuard portal="patient" />}
      />
      <Route path="/login/nakes" element={<LoginGuard portal="clinician" />} />
      <Route path="/login/admin" element={<LoginGuard portal="admin" />} />
      <Route
        path="/ganti-password-awal"
        element={
          <RequireAuth loginPath="/login/nakes" allowPasswordResetRequired>
            <PasswordResetScreen />
          </RequireAuth>
        }
      />

      {/* === ADMIN === */}
      <Route
        path="/admin"
        element={
          <RequireAuth loginPath="/login/admin">
            <RequireRole role="admin">
              <AdminPortal />
            </RequireRole>
          </RequireAuth>
        }
      />

      {/* === PATIENT (MOBILE) === */}
      <Route
        path="/patient"
        element={
          <RequireAuth loginPath="/login/ibu-hamil">
            <RequireRole role="patient">
              <PatientLayout />
            </RequireRole>
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="home" replace />} />
        <Route path="home" element={<HomeScreen />} />
        <Route path="monitoring" element={<MonitoringScreen />} />
        <Route path="history" element={<HistoryScreen />} />
        <Route path="notifications" element={<NotificationsScreen />} />
        <Route path="education" element={<EducationScreen />} />
        <Route path="settings" element={<SettingsScreen />} />
        <Route path="profile" element={<ProfileScreen />} />
      </Route>

      {/* === CLINICIAN (WEB DASHBOARD) === */}
      <Route
        path="/clinician"
        element={
          <RequireAuth loginPath="/login/nakes">
            <RequireRole role="clinician">
              <ClinicianLayout />
            </RequireRole>
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<ClinicianDashboard />} />
      </Route>

      {/* === CATCH-ALL 404 === */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </Suspense>
  );
}

export default App;

import "@/App.css";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/context/AuthContext";
import { ProtectedAdminRoute, ProtectedUserRoute } from "@/components/ProtectedRoute";
import MobileShell from "@/components/MobileShell";
import Splash from "@/pages/Splash";
import Welcome from "@/pages/Welcome";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import ForgotPassword from "@/pages/ForgotPassword";
import Home from "@/pages/Home";
import Programs from "@/pages/Programs";
import ProgramDetail from "@/pages/ProgramDetail";
import ModulePlayer from "@/pages/ModulePlayer";
import Assessment from "@/pages/Assessment";
import Certificate from "@/pages/Certificate";
import ReferEarn from "@/pages/ReferEarn";
import Team from "@/pages/Team";
import BankDetails from "@/pages/BankDetails";
import Profile from "@/pages/Profile";
import Notifications from "@/pages/Notifications";
import Settings from "@/pages/Settings";
import Offline from "@/pages/Offline";
import LegalPage from "@/pages/LegalPage";
import Purchases from "@/pages/Purchases";
import Commissions from "@/pages/Commissions";
import Payouts from "@/pages/Payouts";
import Reports from "@/pages/Reports";
import AdminLogin from "@/pages/AdminLogin";
import AdminDashboard from "@/pages/AdminDashboard";
import AdminPayments from "@/pages/AdminPayments";
import AdminReferrals from "@/pages/AdminReferrals";
import AdminUsers from "@/pages/AdminUsers";
import AdminCMS from "@/pages/AdminCMS";
import AdminSystem from "@/pages/AdminSystem";
import AdminNotifications from "@/pages/AdminNotifications";
import AdminBanners from "@/pages/AdminBanners";
import AdminAuditLog from "@/pages/AdminAuditLog";
import AdminAnalytics from "@/pages/AdminAnalytics";
import AdminReports from "@/pages/AdminReports";
import AdminQA from "@/pages/AdminQA";
import AdminShell from "@/components/AdminShell";
import ErrorBoundary from "@/components/ErrorBoundary";

function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
        <Routes>
          {/* Splash + public */}
          <Route path="/" element={<Splash />} />
          <Route path="/welcome" element={<Welcome />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/offline" element={<Offline />} />
          <Route path="/legal/:slug" element={<LegalPage />} />

          {/* Referral shortcut — prefills referral on registration */}
          <Route path="/join/:referral" element={<Register />} />

          {/* Authenticated PWA shell with bottom nav */}
          <Route
            path="/app"
            element={
              <ProtectedUserRoute>
                <MobileShell />
              </ProtectedUserRoute>
            }
          >
            <Route index element={<Home />} />
            <Route path="home" element={<Home />} />
            <Route path="programs" element={<Programs />} />
            <Route path="programs/:id" element={<ProgramDetail />} />
            <Route path="programs/:id/module/:moduleId" element={<ModulePlayer />} />
            <Route path="programs/:id/assessment/:moduleId" element={<Assessment />} />
            <Route path="certificate/:id" element={<Certificate />} />
            <Route path="refer" element={<ReferEarn />} />
            <Route path="team" element={<Team />} />
            <Route path="bank" element={<BankDetails />} />
            <Route path="notifications" element={<Notifications />} />
            <Route path="profile" element={<Profile />} />
            <Route path="purchases" element={<Purchases />} />
            <Route path="commissions" element={<Commissions />} />
            <Route path="payouts" element={<Payouts />} />
            <Route path="reports" element={<Reports />} />
            <Route path="settings" element={<Settings />} />
          </Route>

          {/* Admin */}
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route
            element={
              <ProtectedAdminRoute>
                <AdminShell />
              </ProtectedAdminRoute>
            }
          >
            <Route path="/admin" element={<AdminDashboard />} />
            <Route path="/admin/dashboard" element={<AdminDashboard />} />
            <Route path="/admin/analytics" element={<AdminAnalytics />} />
            <Route path="/admin/reports" element={<AdminReports />} />
            <Route path="/admin/users" element={<AdminUsers />} />
            <Route path="/admin/payments" element={<AdminPayments />} />
            <Route path="/admin/referrals" element={<AdminReferrals />} />
            <Route path="/admin/notifications" element={<AdminNotifications />} />
            <Route path="/admin/banners" element={<AdminBanners />} />
            <Route path="/admin/cms" element={<AdminCMS />} />
            <Route path="/admin/system" element={<AdminSystem />} />
            <Route path="/admin/audit" element={<AdminAuditLog />} />
            <Route path="/admin/qa" element={<AdminQA />} />
          </Route>

          <Route path="*" element={<Welcome />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-center" richColors closeButton />
    </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;

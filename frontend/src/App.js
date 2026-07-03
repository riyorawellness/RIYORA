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
import AdminLogin from "@/pages/AdminLogin";
import AdminDashboard from "@/pages/AdminDashboard";

function App() {
  return (
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
            <Route path="settings" element={<Settings />} />
          </Route>

          {/* Admin */}
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route
            path="/admin/dashboard"
            element={
              <ProtectedAdminRoute>
                <AdminDashboard />
              </ProtectedAdminRoute>
            }
          />

          <Route path="*" element={<Welcome />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-center" richColors closeButton />
    </AuthProvider>
  );
}

export default App;

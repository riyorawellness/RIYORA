import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export function ProtectedUserRoute({ children }) {
  const { user, status } = useAuth();
  if (status === "loading") return <FullScreenLoader />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export function ProtectedAdminRoute({ children }) {
  const { admin, status } = useAuth();
  if (status === "loading") return <FullScreenLoader />;
  if (!admin) return <Navigate to="/admin/login" replace />;
  return children;
}

function FullScreenLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="rw-serif text-3xl text-primary animate-pulse">RIYORA</div>
    </div>
  );
}

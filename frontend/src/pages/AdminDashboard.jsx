import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import Logo from "@/components/Logo";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { TID } from "@/constants/testIds";
import { LogOut, Users, Activity, Layers, Send, CreditCard, Wallet } from "lucide-react";

export default function AdminDashboard() {
  const { admin, logout } = useAuth();
  const nav = useNavigate();
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);

  useEffect(() => {
    (async () => {
      const [s, u] = await Promise.all([api.get("/admin/stats"), api.get("/admin/users?limit=50")]);
      setStats(s.data);
      setUsers(u.data);
    })();
  }, []);

  const doLogout = async () => {
    await logout();
    nav("/", { replace: true });
  };

  return (
    <div className="min-h-screen rw-hero-radial rw-grain">
      <header className="rw-container flex items-center justify-between py-6">
        <div className="flex items-center gap-3">
          <Logo size="sm" />
          <Badge variant="secondary" className="ml-1">Admin</Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={() => nav("/admin/payments")} data-testid="admin-nav-payments">
            <CreditCard className="mr-1 h-4 w-4" /> Payments
          </Button>
          <Button variant="secondary" onClick={() => nav("/admin/referrals")} data-testid="admin-nav-referrals">
            <Wallet className="mr-1 h-4 w-4" /> Referrals
          </Button>
          <Button variant="secondary" onClick={doLogout} data-testid={TID.adminLogout}>
            <LogOut className="mr-1 h-4 w-4" /> Sign out
          </Button>
        </div>
      </header>

      <main className="rw-container pb-16">
        <p className="rw-eyebrow">Admin</p>
        <h1 className="mt-2 rw-serif text-5xl text-foreground">
          Welcome, <span className="text-primary">{admin.name}</span>.
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Foundation phase — monitor members and health of the platform.
        </p>

        <section
          className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-4"
          data-testid={TID.adminDashStats}
        >
          <Stat icon={Users} label="Total members" value={stats?.total_users ?? "—"} />
          <Stat icon={Activity} label="Active members" value={stats?.active_users ?? "—"} />
          <Stat icon={Layers} label="Memberships" value={stats?.total_memberships ?? "—"} />
          <Stat icon={Send} label="OTPs sent" value={stats?.total_otps_sent ?? "—"} />
        </section>

        <section className="mt-10">
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="rw-serif text-3xl text-foreground">Latest members</h2>
            <span className="text-xs text-muted-foreground">Showing latest {users.length}</span>
          </div>
          <Card className="rw-card overflow-x-auto p-0">
            <Table data-testid={TID.adminUsersTable}>
              <TableHeader>
                <TableRow>
                  <TableHead>Membership</TableHead>
                  <TableHead>Full name</TableHead>
                  <TableHead>Mobile</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Sponsor</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((u) => (
                  <TableRow key={u.membership_id}>
                    <TableCell className="font-mono">{u.membership_id}</TableCell>
                    <TableCell>{u.full_name}</TableCell>
                    <TableCell>+91 {u.mobile}</TableCell>
                    <TableCell>
                      {u.city}, {u.state}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{u.sponsor_membership_id}</TableCell>
                    <TableCell>
                      <Badge variant={u.is_active ? "default" : "secondary"}>
                        {u.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
                {users.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">
                      No members yet.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Card>
        </section>
      </main>
    </div>
  );
}

function Stat({ icon: Icon, label, value }) {
  return (
    <Card className="rw-card">
      <div className="flex items-center justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <span className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
          {label}
        </span>
      </div>
      <div className="mt-4 rw-serif text-4xl text-foreground">{value}</div>
    </Card>
  );
}

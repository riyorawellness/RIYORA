import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Loader2, Save } from "lucide-react";

import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";

/**
 * Inline profile editor.
 *
 * Editable here: name pronunciation, gender, dob, address, state, district,
 * city, pincode, profession, blood group, profile photo URL, emergency
 * contact, about me.
 *
 * Read-only here (see Profile.jsx for how they're rendered): full name,
 * mobile, email, member ID, referral ID, sponsor, joining date. Email and
 * mobile changes go through /app/profile/change-request instead.
 */
export default function EditProfile() {
  const nav = useNavigate();
  const { user, updateMyProfile } = useAuth();
  const [form, setForm] = useState({
    name_pronunciation: "",
    gender: "",
    dob: "",
    address: "",
    state: "",
    district: "",
    city: "",
    pincode: "",
    profession: "",
    blood_group: "",
    profile_photo_url: "",
    emergency_contact: "",
    about_me: "",
  });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!user) return;
    setForm({
      name_pronunciation: user.name_pronunciation ?? "",
      gender: user.gender ?? "",
      dob: user.dob ?? "",
      address: user.address ?? "",
      state: user.state ?? "",
      district: user.district ?? "",
      city: user.city ?? "",
      pincode: user.pincode ?? "",
      profession: user.profession ?? "",
      blood_group: user.blood_group ?? "",
      profile_photo_url: user.profile_photo_url ?? user.photo_url ?? "",
      emergency_contact: user.emergency_contact ?? "",
      about_me: user.about_me ?? "",
    });
  }, [user]);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      // Send only non-empty values so we don't overwrite fields with "".
      const patch = Object.fromEntries(
        Object.entries(form).filter(([, v]) => v !== "" && v != null),
      );
      await updateMyProfile(patch);
      toast.success("Profile updated.");
      nav("/app/profile", { replace: true });
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  if (!user) return null;

  return (
    <div className="px-5 pt-6 pb-24" data-testid="edit-profile-page">
      <button
        onClick={() => nav("/app/profile")}
        className="mb-4 inline-flex items-center gap-2 text-xs font-semibold text-[hsl(var(--rw-royal))]"
        data-testid="edit-profile-back"
      >
        <ArrowLeft className="h-3 w-3" /> Back to profile
      </button>
      <p className="rw-eyebrow">Edit</p>
      <h1 className="mt-1 rw-serif text-4xl">Your profile</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        These fields are safe to edit yourself. To change your <span className="font-semibold">email</span> or
        {" "}<span className="font-semibold">mobile number</span>, submit a{" "}
        <button
          type="button"
          onClick={() => nav("/app/profile/change-request")}
          className="font-semibold text-[hsl(var(--rw-royal))] underline"
          data-testid="edit-profile-change-request-link"
        >
          change request
        </button>.
      </p>

      <form className="mt-6 space-y-4" onSubmit={submit}>
        <ReadOnlyGrid user={user} />

        <Section label="About you">
          <Field label="Name pronunciation (optional)">
            <input className="rw-input" value={form.name_pronunciation} onChange={set("name_pronunciation")} data-testid="edit-name-pron" />
          </Field>
          <Field label="About me">
            <textarea className="rw-input min-h-[80px]" rows={3} value={form.about_me} onChange={set("about_me")} data-testid="edit-about-me" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Gender">
              <select className="rw-input" value={form.gender} onChange={set("gender")} data-testid="edit-gender">
                <option value="">—</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
                <option value="prefer_not">Prefer not to say</option>
              </select>
            </Field>
            <Field label="Date of birth">
              <input className="rw-input" type="date" value={form.dob} onChange={set("dob")} data-testid="edit-dob" />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Blood group">
              <select className="rw-input" value={form.blood_group} onChange={set("blood_group")} data-testid="edit-blood-group">
                <option value="">—</option>
                {["A+","A-","B+","B-","AB+","AB-","O+","O-","unknown"].map((b) => <option key={b} value={b}>{b}</option>)}
              </select>
            </Field>
            <Field label="Profession / Occupation">
              <input className="rw-input" value={form.profession} onChange={set("profession")} data-testid="edit-profession" />
            </Field>
          </div>
        </Section>

        <Section label="Address">
          <Field label="Address">
            <textarea className="rw-input min-h-[60px]" rows={2} value={form.address} onChange={set("address")} data-testid="edit-address" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="State"><input className="rw-input" value={form.state} onChange={set("state")} data-testid="edit-state" /></Field>
            <Field label="District"><input className="rw-input" value={form.district} onChange={set("district")} data-testid="edit-district" /></Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="City"><input className="rw-input" value={form.city} onChange={set("city")} data-testid="edit-city" /></Field>
            <Field label="PIN code"><input className="rw-input" inputMode="numeric" maxLength={6} value={form.pincode} onChange={set("pincode")} data-testid="edit-pincode" /></Field>
          </div>
        </Section>

        <Section label="Contact & photo">
          <Field label="Profile photo URL">
            <input className="rw-input" value={form.profile_photo_url} onChange={set("profile_photo_url")} placeholder="https://…" data-testid="edit-photo-url" />
          </Field>
          <Field label="Emergency contact (10 digits)">
            <input className="rw-input" inputMode="numeric" maxLength={10} value={form.emergency_contact} onChange={(e) => setForm({ ...form, emergency_contact: e.target.value.replace(/\D/g, "").slice(0,10) })} data-testid="edit-emergency-contact" />
          </Field>
        </Section>

        <button type="submit" className="rw-btn-pill rw-btn-primary w-full" disabled={busy} data-testid="edit-profile-save">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save changes
        </button>
      </form>
    </div>
  );
}

function ReadOnlyGrid({ user }) {
  const items = [
    ["Full name", user.full_name],
    ["Mobile", user.mobile ? `+91 ${user.mobile}` : "—"],
    ["Email", user.email || "—"],
    ["Member ID", user.membership_id],
    ["Referral ID", user.referral_id],
    ["Sponsor", user.sponsor_name || "RIYORA Wellness"],
    ["Joining date", (user.joining_date || user.created_at || "").slice(0,10)],
  ];
  return (
    <div className="rounded-2xl border border-neutral-200 bg-neutral-50/60 p-4">
      <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Locked (identity)</p>
      <div className="grid grid-cols-2 gap-3 text-xs">
        {items.map(([k, v]) => (
          <div key={k}>
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground">{k}</div>
            <div className="mt-0.5 text-sm font-medium">{v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Section({ label, children }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">{label}</p>
      <div className="mt-2 space-y-3">{children}</div>
    </div>
  );
}
function Field({ label, children }) {
  return (
    <div>
      <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{label}</label>
      <div className="mt-1">{children}</div>
    </div>
  );
}

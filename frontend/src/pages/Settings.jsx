import { Info, Globe, HelpCircle, Lock, Moon, Palette, Phone, ShieldCheck, FileText } from "lucide-react";
import TopBar from "@/components/TopBar";
import { TID } from "@/constants/testIds";

const GROUPS = [
  {
    title: "Preferences",
    items: [
      { icon: Palette, label: "Theme", value: "Light · Royal", testId: TID.settingsTheme },
      { icon: Globe, label: "Language", value: "English (India)", testId: TID.settingsLanguage },
      { icon: Moon, label: "Reduced motion", value: "Off" },
    ],
  },
  {
    title: "Privacy",
    items: [
      { icon: Lock, label: "Privacy policy" },
      { icon: FileText, label: "Terms of service" },
      { icon: ShieldCheck, label: "Data & security" },
    ],
  },
  {
    title: "About",
    items: [
      { icon: Info, label: "About RIYORA", value: "v1.0.0" },
      { icon: HelpCircle, label: "Help & FAQ", testId: TID.settingsSupport },
      { icon: Phone, label: "Contact us", value: "care@riyorawellness.com" },
    ],
  },
];

export default function Settings() {
  return (
    <div className="px-4 pt-3">
      <TopBar title="Settings" />

      {GROUPS.map((g) => (
        <div key={g.title} className="mt-5">
          <p className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            {g.title}
          </p>
          <div className="rw-card divide-y overflow-hidden p-0" style={{ borderColor: "hsl(var(--rw-grey-100))" }}>
            {g.items.map((it) => (
              <button
                key={it.label}
                data-testid={it.testId}
                className="flex w-full items-center gap-3 p-4 text-left hover:bg-[hsl(var(--rw-grey-50))]"
              >
                <div className="grid h-9 w-9 place-items-center rounded-full bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal))]">
                  <it.icon className="h-4 w-4" />
                </div>
                <div className="flex-1">
                  <div className="text-sm font-semibold">{it.label}</div>
                </div>
                {it.value && <div className="text-xs text-muted-foreground">{it.value}</div>}
              </button>
            ))}
          </div>
        </div>
      ))}

      <p className="mt-8 text-center text-[10px] text-muted-foreground">
        RIYORA WELLNESS · Heal · Learn · Earn
      </p>
    </div>
  );
}

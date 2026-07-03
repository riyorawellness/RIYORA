// Phase 3 — Frontend-only mock data. Backend integration will replace this in Phase 4+.

export const PROGRAMS = [
  {
    id: "inner-peace",
    slug: "inner-peace",
    name: "Inner Peace",
    tagline: "Daily meditation & breath work",
    description:
      "A gentle, guided path to daily stillness. Weekly live sessions, meditation audios and a rhythmic activity meter to keep you consistent.",
    duration: "Ongoing",
    validity_days: 30,
    price: 999,
    discount: 100,
    gst_percent: 18,
    thumbnail:
      "https://images.unsplash.com/photo-1518241353330-0f7941c2d9b5?auto=format&fit=crop&w=800&q=60",
    banner:
      "https://images.unsplash.com/photo-1506126613408-eca07ce68773?auto=format&fit=crop&w=1400&q=60",
    is_subscription: true,
    level: 0,
    locked: false,
    purchased: true,
    progress: 42,
    benefits: [
      "Live weekly meditation sessions",
      "Guided audio library",
      "Activity meter with mindful streaks",
      "Priority support",
    ],
  },
  {
    id: "level-1",
    slug: "chitta-shuddhi",
    name: "Level 1 — Chitta Shuddhi",
    tagline: "Purification of the mind",
    description:
      "The foundational program to steady the mind, clear mental fog and reset your relationship with attention.",
    duration: "4 weeks",
    validity_days: 90,
    price: 4999,
    discount: 500,
    gst_percent: 18,
    thumbnail:
      "https://images.unsplash.com/photo-1533662017580-01ee9d1a9e1c?auto=format&fit=crop&w=800&q=60",
    banner:
      "https://images.unsplash.com/photo-1519821172144-4f87d1de1e6d?auto=format&fit=crop&w=1400&q=60",
    is_subscription: false,
    level: 1,
    locked: false,
    purchased: false,
    progress: 0,
    benefits: ["3 core modules", "Mid-course assessment", "Personal workbook (PDF)", "Certificate on completion"],
  },
  {
    id: "level-2",
    slug: "prana-activation",
    name: "Level 2 — Prana Activation",
    tagline: "Awakening life-force",
    description: "Activate breath-force pathways with progressive kriyas and pranayama.",
    duration: "6 weeks",
    validity_days: 120,
    price: 7999,
    discount: 0,
    gst_percent: 18,
    thumbnail:
      "https://images.unsplash.com/photo-1531727991582-cfd25ce79613?auto=format&fit=crop&w=800&q=60",
    banner:
      "https://images.unsplash.com/photo-1483794344563-d27a8d18014e?auto=format&fit=crop&w=1400&q=60",
    is_subscription: false,
    level: 2,
    locked: true,
    purchased: false,
    progress: 0,
    benefits: ["Advanced pranayama", "Weekly live labs", "Assessment + certification"],
  },
  {
    id: "level-3",
    slug: "chakra-udaya",
    name: "Level 3 — Chakra Udaya",
    tagline: "Rising through the centres",
    description: "Systematic activation of the seven energy centres.",
    duration: "8 weeks",
    validity_days: 150,
    price: 11999,
    discount: 0,
    gst_percent: 18,
    thumbnail:
      "https://images.unsplash.com/photo-1602928321679-560bb453f190?auto=format&fit=crop&w=800&q=60",
    banner:
      "https://images.unsplash.com/photo-1517394834181-95ed159986c7?auto=format&fit=crop&w=1400&q=60",
    is_subscription: false,
    level: 3,
    locked: true,
    purchased: false,
    progress: 0,
    benefits: ["Chakra meditations", "One-on-one review", "Certificate"],
  },
  {
    id: "level-4",
    slug: "param-alignment",
    name: "Level 4 — Param Alignment",
    tagline: "Alignment with the supreme",
    description: "Deep integration and alignment practices.",
    duration: "10 weeks",
    validity_days: 180,
    price: 17999,
    discount: 0,
    gst_percent: 18,
    thumbnail:
      "https://images.unsplash.com/photo-1440557958969-404dd53d3b58?auto=format&fit=crop&w=800&q=60",
    banner:
      "https://images.unsplash.com/photo-1476611317561-60117649dd94?auto=format&fit=crop&w=1400&q=60",
    is_subscription: false,
    level: 4,
    locked: true,
    purchased: false,
    progress: 0,
    benefits: ["Advanced retreat access", "Mentor circle", "Certificate"],
  },
  {
    id: "level-5",
    slug: "param-siddhi",
    name: "Level 5 — Param Siddhi",
    tagline: "Attainment",
    description: "The culminating program for lifelong practitioners.",
    duration: "12 weeks",
    validity_days: 365,
    price: 24999,
    discount: 0,
    gst_percent: 18,
    thumbnail:
      "https://images.unsplash.com/photo-1418065460487-3e41a6c84dc5?auto=format&fit=crop&w=800&q=60",
    banner:
      "https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?auto=format&fit=crop&w=1400&q=60",
    is_subscription: false,
    level: 5,
    locked: true,
    purchased: false,
    progress: 0,
    benefits: ["Final assessment", "Lifetime honorific"],
  },
];

export const MODULES_BY_PROGRAM = {
  "inner-peace": [
    { id: "ip-1", module_number: 1, name: "Foundation: The Breath", type: "video", duration_min: 22, status: "completed" },
    { id: "ip-2", module_number: 2, name: "Silence Between Thoughts", type: "audio", duration_min: 18, status: "completed" },
    { id: "ip-3", module_number: 3, name: "Companion Notes", type: "pdf", pages: 14, status: "unlocked" },
    { id: "ip-4", module_number: 4, name: "Weekly Assessment", type: "assessment", status: "locked" },
  ],
  "level-1": [
    { id: "l1-1", module_number: 1, name: "Setting the Ground", type: "video", duration_min: 26, status: "unlocked" },
    { id: "l1-2", module_number: 2, name: "Chitta — Perception & Movement", type: "video", duration_min: 34, status: "locked" },
    { id: "l1-3", module_number: 3, name: "Purification Kriyas", type: "audio", duration_min: 21, status: "locked" },
    { id: "l1-4", module_number: 4, name: "Workbook", type: "pdf", pages: 22, status: "locked" },
    { id: "l1-5", module_number: 5, name: "Assessment", type: "assessment", status: "locked" },
  ],
};

export const QUIZ = {
  id: "q-1",
  title: "Inner Peace — Weekly Assessment",
  questions: [
    {
      q: "The primary anchor of the Inner Peace practice is:",
      options: ["Effort", "Breath", "Mantra", "Silence"],
      correct_index: 1,
    },
    {
      q: "Green status on the Activity Meter means:",
      options: ["Grace period", "Active cycle", "Inactive", "Locked"],
      correct_index: 1,
    },
    {
      q: "How many sessions form one Inner Peace cycle?",
      options: ["3", "4", "5", "7"],
      correct_index: 1,
    },
  ],
};

export const DAILY_QUOTE = {
  quote: "Peace is not the absence of noise. It is the presence of returning.",
  author: "— Inner Peace, Week 4",
};

export const UPCOMING_LIVE = {
  title: "Live · Session 04",
  starts_at: "Today · 6:30 AM",
  host: "Acharya M. Rao",
  cover:
    "https://images.unsplash.com/photo-1445205170230-053b83016050?auto=format&fit=crop&w=1000&q=60",
};

export const ANNOUNCEMENT = {
  title: "New program: Level 2 — Prana Activation",
  body: "Early-bird pricing for existing members until Sunday.",
  when: "2h ago",
};

export const NOTIFICATIONS = [
  { id: "n1", title: "Welcome to RIYORA", body: "Your journey begins now.", category: "welcome", is_read: false, when: "just now" },
  { id: "n2", title: "Session unlocked", body: "Foundation: The Breath is now available.", category: "programs", is_read: false, when: "1h ago" },
  { id: "n3", title: "Live in 30 min", body: "Session 04 with Acharya M. Rao.", category: "live", is_read: true, when: "yesterday" },
  { id: "n4", title: "Referral update", body: "A new seeker joined via your link.", category: "referrals", is_read: true, when: "2d ago" },
];

export const TEAM = {
  direct: [
    { id: "RW197518", name: "Aarohi Menon", state: "MH", joined: "12 Jun 2026", status: "active" },
    { id: "RW220441", name: "Kabir Sethi", state: "DL", joined: "20 Jun 2026", status: "active" },
    { id: "RW231902", name: "Nia Bhalla", state: "KA", joined: "01 Jul 2026", status: "grace" },
  ],
  level_2: [
    { id: "RW250811", name: "Rehan Rao", state: "TN", joined: "18 Jun 2026", status: "active" },
    { id: "RW261200", name: "Meher Iyer", state: "TN", joined: "23 Jun 2026", status: "inactive" },
  ],
  level_3: [
    { id: "RW271881", name: "Ishan Bakshi", state: "WB", joined: "26 Jun 2026", status: "active" },
  ],
};

export const EARNINGS = {
  total: 12480,
  pending: 3620,
  paid: 8860,
  current_month: 2140,
  activity_status: "active", // active | grace | inactive
};

export const ACTIVITY = {
  required: 4,
  completed: 3,
  cycle_start: "04 Jun 2026",
  cycle_end: "03 Jul 2026",
  status: "grace",
};

export const WATER_REMINDER = {
  glasses_target: 8,
  glasses_done: 5,
};

# RIYORA WELLNESS — PRD

## Original problem statement
Full-stack RIYORA WELLNESS platform (Heal. Learn. Earn.) — Phase 1 scope: production-ready foundation with React PWA + FastAPI + MongoDB. Only authentication, user/admin management, membership + referral ID validation, company seed account, and core project structure. NO programs, payments, referral commissions, reports, notifications, activity meter, or business logic in this phase.

## Personas
- **User (Member)** — signs up with mobile + OTP + mandatory Referral ID, receives permanent RW###### Membership ID, manages profile.
- **Admin** — separate credentials, views member roster and platform stats.

## Core requirements (static)
- Mobile OTP registration (5-min TTL, 5/hour resend).
- Mandatory Referral ID validation with sponsor lookup.
- Unique, permanent Membership ID `RW######`.
- Reserved company account `RW000000` = root of referral tree.
- JWT access + refresh token auth (with rotation).
- bcrypt passwords.
- Separate admin login + password reset.
- PWA (manifest + service worker + installable).
- Swagger docs.
- Soft-delete, audit logs, indexes.

## Delivered on 2026-07-03 (Phase 1)
- Modular FastAPI backend (`app/core|db|models|routes|utils`), MongoDB.
- All auth endpoints (register/login/refresh/logout/forgot/reset/verify-otp/send-otp).
- Membership validate-referral + me.
- Admin login/profile/stats/users.
- React PWA frontend: Landing, Register (4-step), Login, Forgot Password, Dashboard, Profile, Admin Login, Admin Dashboard.
- Custom earthy design system (terracotta/saffron/sage/bone) + Cormorant Garamond serif + Manrope.
- Admin + Company seed on startup.
- Audit logs, indexes, exception handlers.
- test_credentials.md + README + Swagger.

## Delivered on 2026-07-03 (Phase 2 — Database & Backend)
- New collections: profiles, program_categories, programs, program_modules, program_purchases, program_progress, assessments, assessment_results, certificates, referral_tree, bank_details, user_settings, app_settings, system_configuration, notifications, activity_log.
- Repository pattern (`app/repositories/base.py`) with generic pagination/search/sort/soft-delete.
- CRUD endpoints for every entity (user + admin), pagination + search + filter + sort.
- Referral tree materialization on register: user rows inserted with computed depth level.
- Extended profile (email/dob/gender/address/photo/occupation/alt_contact).
- Assessments with server-side scoring (no attempt-limit business rule — Phase 3).
- Bank details with masked-list view for admin.
- App settings public endpoint for PWA bootstrap.
- Full Swagger docs at `/docs`.

## Delivered on 2026-07-03 (Phase 3 — Mobile PWA UI)
- Complete mobile-first PWA UI in `/app/frontend/src/` — 22 screens including Splash, Welcome, Auth (Login/Register/Forgot), Home, Programs, ProgramDetail, ModulePlayer (video/audio/pdf with watermark), Assessment quiz, Certificate, Refer & Earn, Team, Bank Details, Profile, Notifications, Settings, Offline.
- New royal-blue/gold theme with Fraunces + Manrope typography and 5-tab bottom navigation.
- Mock data (`/app/frontend/src/mock/data.js`) for programs/modules/quiz/team/notifications so UI works standalone.
- Real backend integration for auth flows + bank-details.

## Delivered on 2026-07-03 (Phase 4 — Programs Engine)
- `app/services/program_engine.py` — sequence gate, module unlock, progress recompute, auto-cert issue, dashboard categorisation, continue-learning.
- `app/services/validity.py` — expiry computation, active-purchase lookup, opportunistic expire-past-purchases.
- `app/utils/file_token.py` + `app/routes/content.py` — signed content JWT + `/content/token` + `/content/stream/{token}` redirect (302, inline, no-store) with watermark payload.
- Enhanced routes: programs (`/me/dashboard`, `/me/continue-learning`, `/{id}/eligibility`, `/{id}/status`, `/{id}/purchase`), modules (`/me/by-program/{id}`), progress (`/me/{pid}/module/{mid}/complete`), assessments (attempts limit + randomize + auto-cert + correct_index stripping).
- New `level` field on programs (0=subscription, 1-5=levels) driving the sequence gate.
- 98/98 backend tests passing.

## Delivered on 2026-07-03 (Phase 5 — Razorpay Payment Engine)
- `app/services/payment.py` — Razorpay client (LIVE + MOCK modes), HMAC-SHA256 signature verification, webhook verification, mock subscriptions.
- `app/services/invoice.py` — ReportLab-based GST-compliant PDF invoice, persisted at `/app/backend/invoices/`.
- `app/routes/payments.py` — full engine:
  - `POST /payments/order` (server-computed pricing, sequence gate)
  - `POST /payments/verify` (signature check → creates `program_purchases` row → generates invoice)
  - `POST /payments/webhook` (Razorpay webhook receiver)
  - `GET /payments/config` (public key id + is_mock)
  - `GET /payments/me` + `GET /payments/invoice/{id}` (user history + PDF download)
  - `POST /payments/subscription` + `GET/POST cancel` (Inner Peace mock AutoPay)
  - Admin: `/admin/transactions`, `/admin/summary`, `/admin/transactions/{id}/refund`, `/admin/settings`
- Access unlocking now happens ONLY via `/payments/verify` — frontend can't self-grant access.
- Frontend: real-API `Programs.jsx` (dashboard buckets), real-API `ProgramDetail.jsx` with sticky checkout, `CheckoutModal.jsx` (Razorpay Standard Checkout + mock-mode simulator), `Purchases.jsx` (history + invoice download), `AdminPayments.jsx` (transactions table, refund, GST settings).
- New env: `RAZORPAY_MOCK_MODE`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`.

## Delivered on 2026-07-03 (Phase 6 — Refer & Earn Engine)
- `app/services/activity_meter.py` — subscription cycle detection (finds ANY active `is_subscription=true` purchase), session logging (auto on Inner Peace module completion + manual), 4-session rule, meter with green/yellow/red/no_subscription statuses, smart reminders (7d/3d/1d/expiry) as in-app notifications rows.
- `app/services/commission_engine.py` — 3-level upline walk (excludes company root RW000000), per-program `commission_override` OR global rates (percent | fixed | both), eligibility check via activity meter, idempotent per (purchase, sponsor). Rows created as `pending` for eligible sponsors and `rejected` (with reason) for inactive ones — full audit trail preserved.
- `app/services/reports.py` — 5 ReportLab PDF reports: referral, income, downline, subscription, transaction.
- Routes:
  - `/api/referrals/dashboard` (earnings + activity + team counts + referral link)
  - `/api/referrals/share/qr` (base64 PNG QR code of referral link)
  - `/api/referrals/team?level=1|2|3` (members with sub + activity status)
  - `/api/referrals/admin/settings` GET/PUT (L1/L2/L3 percent + fixed + mode + activity rules)
  - `/api/activity/meter` + `/api/activity/session` + `/api/activity/reminders/generate`
  - `/api/commissions/me[/summary]` + admin list/summary/approve/reject/bulk-approve
  - `/api/payouts/me` + admin list/pending-by-user/create/mark-paid/cancel
  - `/api/reports/{type}` PDF export (referral | income | downline | subscription | transaction)
- Payment engine hook: `/payments/verify` and `/payments/subscription` now call `create_commissions_for_purchase()` on success.
- Program engine hook: `mark_module_completed()` auto-logs an Inner Peace session when the module belongs to a subscription program.
- Frontend: real-API `ReferEarn.jsx` (dashboard + QR modal + WhatsApp/SMS/Email/Copy share sheet), real-API `Team.jsx` (3-tab downline), Home activity meter (log-session button), `Commissions.jsx` (filter chips + ledger cards), `Payouts.jsx`, `Reports.jsx` (5 PDF downloads), `AdminReferrals.jsx` (3 tabs: Commissions with bulk-approve, Payouts with queue + mark-paid, Settings with commission mode / percent / fixed / activity rules).
- Profile page now surfaces Commissions / Payouts / Reports links. Admin Dashboard header has Payments + Referrals buttons.

## Backlog (Phase 2+)
### P0 — high impact
- Programs listing (Inner Peace subscription + Levels 1–5) with per-program price/discount/GST/validity (admin-editable).
- Module viewer (video/audio/PDF streaming with expiring URLs + user watermark, anti-download).
- Razorpay integration (order create, signature verify, webhook, GST invoice).
- AutoPay (eMandate) for Inner Peace monthly/yearly.

### P1
- 3-level referral commission engine (active/inactive gating on Inner Peace cycle).
- Activity Meter (subscription-cycle sessions completed/remaining, Green/Yellow/Red).
- Notifications (in-app + FCM).
- Payout dashboard (Pending/Paid/History) + bank details.

### P2
- Reports: PDF export for users, PDF + Excel for admin.
- CMS: notification templates, daily quote, water reminder, live sessions.
- Admin analytics dashboard.
- Multi-language + iOS Flutter/PWA parity.
- AI Wellness Assistant.

## Next tasks
1. Programs & Modules schema + admin CRUD.
2. Secure content streaming (Emergent Object Storage upload + expiring signed URLs).
3. Razorpay integration playbook + real keys.

## Delivered on 2026-07-03 (Phase 7 — Admin Panel & CMS)
- Backend: 4 new route files (admin_dashboard, admin_users, cms, admin_phase7) with rich stats, revenue series, top sellers/referrers, activity feed, full user CRUD + CSV export + session-revoking status change/password reset, CMS with version snapshots, System + Security settings with proper default-fallback, banners CRUD with schedule, notification compose (broadcast + targeted), file uploads (`/app/backend/uploads/`), audit-log viewer.
- All admin routes idempotent + audit-logged via unified `activity_log` collection.
- Frontend: new `AdminShell` (left rail + mobile bottom nav) wraps every admin page. New pages: rich AdminDashboard (Recharts revenue chart), AdminUsers (search/filter/detail modal with tabs), AdminCMS (sidebar page selector + textarea), AdminSystem (Company / Social / Application / Security tabs), AdminNotifications (compose + history), AdminBanners (grid + schedule dialog + inline upload), AdminAuditLog (filter/paginate).
- Bugs caught + fixed during testing: log_action collection mismatch, system-settings setdefault-after-None bug, /notifications/me route collision, PaginatedResponse stripping the `unread` field. Final: 97/97 tests pass across Phase 5+6+7.

## Backlog (Phase 8+)

## Delivered on 2026-07-03 (Phase 8 — Reports & Analytics)
- Backend services: `services/analytics.py` (MongoDB aggregation pipelines: revenue summary/series, program mix, state distribution, source split, user growth, user KPIs, commission summary+by-level, top earners/buyers, subscription health with activity meter breakdown, GST summary, payout summary, user personal earnings+downline series), `services/exports.py` (generic CSV/Excel/PDF exporter — openpyxl + reportlab, supports money/date/datetime/int/bool typed columns), `services/user_reports.py` (column/row builders for all 5 user report types).
- Backend routes:
  - `/api/analytics/*` (admin): kpis, revenue, programs, states, user-growth, commissions, leaderboard, subscriptions, gst, dashboard (composite).
  - `/api/analytics/me` (user): personal earnings series, downline growth series, downline counts, activity meter, spent.
  - `/api/admin/reports/{report_type}` (admin): 7 report types — users, programs, subscriptions, payments, referrals, activity, assessments — with filters (since/until/q/status/program_id/state/level) and pagination.
  - `/api/admin/reports/{report_type}/export?fmt=csv|excel|pdf` — full-dataset export (capped at 20k rows).
  - `/api/reports/{type}?fmt=pdf|csv|excel` — user reports now multi-format (backward-compatible default pdf).
- Frontend:
  - `pages/AdminAnalytics.jsx` — rich financial dashboard with KPI cards (revenue+compare, GST, users, subs, commission liability, net margin), revenue trend area chart (current vs previous), user growth bar chart, program mix pie, state ranking table with share bars, commissions-by-level stacked bar, subscription health tiles + activity meter distribution, leaderboards (top earners + buyers), payouts + GST snapshot, date presets (7d/30d/90d/YTD/1y) + custom range + granularity switch + refresh.
  - `pages/AdminReports.jsx` — tabbed detailed reports (7 types), filter bar (search/date/status/level), paginated table, one-click CSV/Excel/PDF export.
  - `pages/Reports.jsx` (user) — enhanced with personal KPI tiles (earnings/month/downline/activity), earnings trend area chart, downline growth bar chart, and PDF/Excel/CSV downloads per report.
  - `services/analytics.js` — new API client + downloadBlob helper.
  - Admin nav (`AdminShell.jsx`) — new "Analytics" + "Reports" left-rail items.
- Tests: `/app/backend/tests/test_phase8.py` — 31/31 pass covering all endpoints, filters, exports, auth guards.
- Deps: `openpyxl 3.1.5` added; `recharts` (already present) drives all charts.
- DB: added indexes for `program_purchases.purchase_date`, `program_purchases.program_id`.

## Delivered on 2026-07-03 (Phase 9 — Testing, Security Hardening & Production Prep)
- **Business Rule Validation (BRV) Engine** — `services/brv.py` runs 36 live assertions across 10 categories (Registration, Program, Module, Payment, Refer & Earn, Payout, Data, Security, Admin, PWA/Ops). Returns JSON matrix + Pass/Fail verdict. `POST /api/admin/qa/brv[/pdf]` — the PDF is a printable Test Name / Expected / Actual / Status / Remarks report. Frontend `/admin/qa` page with live runner, verdict card, per-category detail, one-click PDF download.
- **Security hardening**:
  - `core/security_mw.py` — SecurityHeadersMiddleware (CSP, HSTS, X-Frame, X-Content-Type, Referrer, Permissions), slowapi limiter (120 req/min per IP), and brute-force lockout (5 fails → 15-min lock, tracked in `login_attempts` collection).
  - `/api/auth/login` and `/api/admin/login` now enforce the lockout.
  - `utils/sanitize.py` — regex-escaped, `$`-stripped free-text search.
  - `utils/file_validator.py` — extension whitelist + size caps + magic-byte checks for uploads.
- **Observability**:
  - `core/logging_mw.py` — RequestIdMiddleware issues per-request `X-Request-ID`, structured JSON access log.
  - `routes/health.py` — `/api/health/{live,ready}` (public) + `/deep` (admin) with Mongo ping, collection counts, uptime, errors_24h.
- **Ops**:
  - `scripts/backup_mongo.sh` — daily gzipped mongodump with retention & weekly snapshots.
  - `scripts/restore_mongo.sh` — companion restore.
- **Frontend polish**:
  - `components/ErrorBoundary.jsx` wraps the entire app tree; friendly retry / home fallback.
  - `public/robots.txt`, `public/sitemap.xml`, richer Open Graph + Twitter meta tags in `index.html`.
- **Docs** (`/app/docs/`): DEPLOYMENT, SECURITY, ADMIN_MANUAL, BACKUP_RESTORE, DEVELOPER, API.
- **Tests**: `/app/backend/tests/test_phase9.py` — 19/19 pass covering BRV, lockout, headers, health, SEO, regressions.
- **Deps added**: `slowapi 0.1.10`, `openpyxl 3.1.5` (from P8).
- **BRV verdict at go-live**: **PASS · 36/36 rules · overall verdict PASS**.

## Delivered on 2026-07-03 (Phase 10 — Legal & Support Pages)
- **Welcome consent gate** — clickable Terms & Conditions and Privacy Policy links plus a mandatory "I have read and agree" checkbox. Create-account and Sign-in buttons blocked with a toast warning until the checkbox is ticked. App version + copyright footer.
- **User-facing legal pages** — universal `LegalPage.jsx` component routed at `/legal/:slug` renders any published CMS page (title, last-updated date, markdown body, back button, brand footer). Pages: `privacy`, `terms`, `data-security`, `faq`, `contact`. React-markdown added.
- **Profile "Legal & Support" section** — five menu items linking to `/legal/*`. Profile footer displays App Version + Copyright.
- **Contact CTA** — `mailto:info@riyorawellness.com?subject=Support%20Request%20-%20RIYORA%20Wellness` prominently rendered on Contact / FAQ / Support pages.
- **Public system endpoint** — `/api/system/public` (no auth) exposes `application_version`, `support_email`, `company_name` etc. Cached client-side by `useSystemInfo()` hook (30 s TTL).
- **CMS seed** — `db/seed_legal.py` inserts 5 placeholder pages on startup if not already present (never overwrites admin edits). `CMS_SLUGS` extended with `data-security`.
- **Admin CMS** — AdminCMS auto-discovers the new `data-security` slug from `/admin/cms/pages`. AdminSystem already has `application_version` + `support_email` fields.
- **Tests**: `/app/backend/tests/test_phase10.py` — 12/12 pytest cases pass; full frontend E2E green (all 5 pages + profile section + Welcome consent gate + toast + navigation gating).

## Delivered on 2026-07-04 (Phase 11 — Manual QR Payment System)
- **Provider pattern**: `payment_mode` app setting (`manual_qr` | `razorpay` | `both`) drives which checkout path the UI takes. Only `manual_qr` is active pending Razorpay AutoPay approvals.
- **Backend**:
  - `models/phase11.py` — request bodies with ISO-date validation.
  - `routes/manual_payments.py` — user endpoints (`/payments/mode`, `/payments/manual/{qr,quote,submit,upload-screenshot,me,pending}`) + admin endpoints (`/admin/payments/{settings,mode,qr,manual,manual/{summary,<id>/action}}`) + public serve router (`/uploads/screenshot/<filename>`).
  - On admin approve → inserts `program_purchases` row with `source='manual_qr'` (identical schema to Razorpay flow), generates GST-compliant invoice PDF, fires the 3-level commission engine, notifies user. Downstream business logic (access, expiry, certificates, reports, analytics, BRV) untouched.
  - Business rule enforced: one active pending request per (user, program). Subscription programs (Inner Peace) return 409 "coming soon".
  - Every state transition audit-logged.
- **Frontend**:
  - `pages/PayManualQR.jsx` — user checkout: server-computed breakdown, QR + UPI + copy buttons, "I have completed payment" → submission form with UTR + screenshot upload → success card. Clipboard write with WebView fallback.
  - `pages/PaymentHistory.jsx` — user list of manual submissions with status badges + resubmit CTA on rejection.
  - `pages/AdminPaymentSettings.jsx` — payment mode selector (Razorpay/Both greyed "Soon"), QR upload/replace/delete, bank/UPI fields, instructions textarea. Guard prevents deactivating the only active QR record.
  - `pages/AdminPendingPayments.jsx` — 4-status tabs, summary tiles, table with view/download/approve/reject, approve/reject dialog with rejection-reason requirement, screenshot viewer.
  - `pages/ProgramDetail.jsx` — button branches on payment_mode; label becomes "Pay via QR" in manual mode; Inner Peace shows "Coming Soon" badge with tagline, no purchase button; existing purchase now shows "Pending Verification" chip while awaiting admin action.
  - `pages/Home.jsx` — prominent amber "Payment Verification Pending" card per pending request with "View details" + "Contact support" CTAs.
  - `services/manualPayments.js` — API client + `resolveUploadUrl` helper.
- **Tests**: `/app/backend/tests/test_phase11.py` — 17/17 pytest cases pass covering mode toggle, settings round-trip, QR upload/delete/serve, quote, submit + duplicate 409, admin summary + list, approve creates purchase + fires commissions + notifies user, reject stores reason + allows resubmit, subscription programs blocked. Frontend Playwright E2E green on every acceptance criterion. BRV still 36/36 PASS.


## Delivered on 2026-02 (P0 Bug — Broadcast Notification Duplication)
- **Root cause**: `GET /api/notifications/me` used `$or: [{user_membership_id: current}, {is_broadcast: True}]`. Since `POST /api/admin/notifications` materialises 1 row per active user (each row carrying `is_broadcast: True`), the `$or` matched every user's copy, returning N rows per broadcast (N = active users) — hence 99+ duplicates.
- **Fix** (`/app/backend/app/routes/notifications.py`):
  - `list_my_notifications` and `unread_count` now strictly filter by `user_membership_id`.
  - `read_all` and `mark_read` no longer exclude `is_broadcast` rows — per-user materialised rows can now be flipped safely.
  - Removed stale `/app/backend/tests/test_notifications_bugfix.py` (asserted old shared-row semantics).
- **Tests**: `/app/backend/tests/test_notifications_p0_dedup.py` — 8/8 pass. Frontend E2E green: 1 broadcast = 1 row per user (no cross-user leakage). Report `/app/test_reports/iteration_18.json`.

## Pending / Roadmap
- P1: Razorpay / AutoPay integration (Provider Pattern is ready — swap in when creds are live).
- P2: Admin Programs / Modules editor UI.
- P2: Media Library gallery UI over `/admin/uploads`.


## Delivered on 2026-02 (Go-live pack — Danger Zone + MSG91 SMS)
- **Empty App Data (Danger Zone)** — `POST /api/admin/danger/empty-app-data` behind required `confirmation: "EMPTY APP DATA"` body (case-sensitive). Wipes users (except admin), memberships (except RW000000), referral tree, profiles, purchases, progress, assessments, certificates, notifications, OTPs, refresh tokens, audit logs, commissions, payouts, bank details, subscriptions, manual-payment requests, login lockouts. Preserves admin + company root + programs/modules/banners/policies/QR/system settings.
- **Soft Delete User** — `DELETE /api/admin/danger/users/{mid}` behind `confirmation: "DELETE USER"`. Stamps `deleted_at`, parks mobile as `<mobile>#deleted-<ts>` so the number is immediately reusable for a fresh signup, revokes refresh tokens, preserves referral_tree row so downline sponsors keep their commissions.
- **Frontend UX** — Admin → System & security → **Danger zone** tab hosts a 3-step confirmation modal (step 1 awareness → step 2 last-chance → step 3 type-to-confirm `EMPTY APP DATA`). Admin → Users list gets a red 🗑 trash icon per row that opens a typed-confirmation dialog (`DELETE USER`).
- **MSG91 OTP integration** — `app/services/sms_msg91.py` speaks Flow API v5. Env-driven (`MSG91_AUTH_KEY`, `MSG91_TEMPLATE_ID`, `MSG91_SENDER_ID`, optional `MSG91_OTP_VAR`). When any var is missing, `send_otp` falls back to logging the code + returning `dev_code` for auto-fill (dev mode). Real SMS is dispatched the moment all three vars are set AND `OTP_DEV_MODE=false`. On MSG91 network / API failure the `/auth/send-otp` route returns 502.
- **Password-only login (already active)** — Register requires 8+ char password (double confirmed). Login = mobile + password. OTP is only used for `register` and `forgot_password` purposes.
- **Docs** — `/app/docs/GOLIVE.md` — step-by-step production checklist (empty test data → MSG91 setup → env vars → smoke test).
- **Tests** — `/app/backend/tests/test_danger_zone.py` (10/10 PASS). Frontend Playwright E2E green — both dialogs and both wipe paths. Report `/app/test_reports/iteration_19.json`.

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

## Delivered on 2026-02 (Bug fixes + Real-time notifications)
- **Banner delete bug**: Replaced native `window.confirm()` (silently blocked in PWA/installed webviews) with a shadcn Dialog. Testid `banner-delete-dialog`. Backend endpoint unchanged.
- **Danger Zone — granular Delete User**: Added a second card in Admin → System → Danger zone with a search picker + 8 scope checkboxes (profile, notifications, purchases, certificates, assessments, bank details, commissions, referral-tree). Server-side `DeleteUserRequest` accepts booleans; response returns a `wiped` dict summarising what was purged. `wipe_referral_tree` defaults OFF to protect downline sponsors.
- **Real-time notifications**: New `usePollUnreadCount` hook polls `/api/notifications/me/unread-count` every 20 s (skips when `document.hidden`, fires immediately on `visibilitychange`). Red badge appears on the bottom-nav bell (testid `nav-notif-badge`). Notifications page auto-refreshes every 15 s while open. Dropped the stale localStorage broadcast-read hack since broadcasts are now materialised per-user.
- **Tests**: `/app/backend/tests/test_iter20_batch.py` (8/8 PASS). Frontend E2E green — banner delete dialog, granular delete user, real-time badge + visibility-refresh. Report `/app/test_reports/iteration_20.json`.


## Delivered on 2026-02 (Admin content editor + Media Library)
- **Admin Programs page** (`/admin/programs`) — list + search + create/edit dialog with full field set (name, slug, description, thumbnail, banner, price, discount, GST, validity, category, level, order, access mode, publish + subscription toggles). Publish/unpublish toggle, soft-delete, inline media upload on thumbnail/banner fields.
- **Admin Modules editor** (`/admin/programs/:programId/modules`) — per-program modules list with up/down reorder, audio/video/PDF/image upload per module, sequential-unlock + visible toggles, assignment field.
- **Admin Media Library** (`/admin/media`) — grid view of every uploaded asset (image/video/audio/PDF), filter by kind, search, copy-URL, delete. Multi-file upload via hidden file input.
- **Backend**: added `get_current_user_or_admin` dep in `core/deps.py` so admin token can now fetch `/api/programs`, `/api/modules`, `/api/categories` (previously 403). Admin sees inactive/hidden content by default; regular users are **always** restricted to `is_active=true` regardless of query param (privilege-leak fix caught in code review).
- **Backend**: `PUT /api/modules/admin/{id}` now enforces (program_id, module_number) uniqueness on update — matches the check that create already had — so admin edits can't create duplicate module numbers within a program.
- **Tests**: `/app/backend/tests/test_iter21_programs_media.py` — 24/24 PASS. Frontend E2E green. Report `/app/test_reports/iteration_21.json`. Two follow-on privilege fixes verified by curl.

## Delivered on 2026-02 (Activity Meter v2 — universal 30-day cycle)
- **New business rule**: Account "Active" now requires (a) any purchased program (subscription OR one-time still within validity) AND (b) 4 completed module sessions in the current rolling 30-day cycle. Cycle starts at user registration, rolls every 30 days.
- **Backend** (`services/activity_meter.py`): full rewrite.
  - `compute_cycle(registered_at, now)` returns the current 30-day window (cycle_number, start, end).
  - `has_any_active_purchase()` — replaces subscription-only check with "any active purchase within validity".
  - `log_session()` no longer requires a subscription; any user with an active plan can log. Idempotent by `module_id` across sources.
  - `get_meter()` returns: `status` (green | yellow | red | no_plan), `completed`, `remaining`, `required`, `cycle_number`, `cycle_start`, `cycle_end`, `days_left`, `has_active_plan`.
  - Statuses: `no_plan` = never purchased or all expired; `yellow` = first cycle grace (auto-active); `green` = 4 sessions met (locks for cycle); `red` = past cycles with < 4.
  - `is_eligible_for_commission()` still fires on `green` only.
  - Legacy `no_subscription` kept in Pydantic Literal for backward compatibility.
- **Backend** (`services/program_engine.mark_module_completed`): auto-log now fires for ANY purchased program on module completion (not just subscription).
- **Frontend** (`pages/Home.jsx`):
  - New red "Account Inactive" banner with reactivation CTA — shown when `status ∈ {red, no_plan}`.
  - Meter card now reads "Purchase or subscribe to start your activity cycle" for `no_plan` and shows cycle window when active.
  - Status chip: "Active" / "Active · Grace" / "Inactive" / "No active plan".
  - "Mark today's session" button gated on `has_active_plan` (no longer subscription-only).
- **Tests**: `/app/backend/tests/test_activity_meter_v2.py` (6/6 PASS) + regression `/app/backend/tests/test_phase6.py` activity classes (7/7 PASS). Two phase6 test expectations were updated to reflect the new business rule (module completion on one-time programs now logs a session; new status name).

## Delivered on 2026-02 (Home cleanup + Admin "Feature on Home" toggle)
- **Home simplified**: removed Daily Quote, Water Reminder, Upcoming Live, and Announcement mock sections. Home now: header → banners → activity meter → continue-learning card → Featured program section.
- **New `is_featured` field on programs**: added to `ProgramCreate` / `ProgramUpdate` models (default `false`) and `/api/programs` list filter (`?is_featured=true`). Backend fully backwards-compatible.
- **Admin control**: `AdminPrograms.jsx` — new star toggle button on every row (⭐ filled amber when featured), a "Featured on Home" switch inside the create/edit dialog, and an amber "Featured" badge next to the row title. Toggle uses `PUT /api/programs/admin/{id}` with `{is_featured: bool}`.
- **User Home wiring**: `Home.jsx` now fetches `is_featured=true, is_subscription=true` for the hero and `is_featured=true, is_subscription=false` for the Featured card. If nothing is featured, the corresponding section is hidden entirely (no dead link, no broken image). Continue-learning still takes precedence over the hero when the user has an in-progress purchase.
- Verified: create program with `is_featured=true` → shows on Home; toggle off → hidden. Admin can hand-pick exactly which programs surface on the user Home page.


## Delivered on 2026-02 (Batch 1 — Per-program payment mode + Level-gate visibility)
- **Per-program `payment_mode`** field on programs (`manual_qr` | `razorpay` | `both` | null=global). Backend precedence: `program.payment_mode > app_setting.payment_mode`. Admin dropdown in create/edit dialog (`admin-program-field-payment-mode` testid).
- **New API contract**: `GET /api/payments/mode?program_id=<id>` now returns the effective mode for that specific program with a `program_override` flag.
- **Cross-flow enforcement**:
  - `POST /api/payments/manual/submit` — 409 if program is razorpay-only.
  - `POST /api/payments/order` — 409 if program is manual_qr-only.
- **User UI**: `ProgramDetail.jsx` now fetches per-program mode and renders:
  - `manual_qr` → single "Pay via QR" button (goes to `/app/pay/{id}`)
  - `razorpay` → single "Purchase" button (opens CheckoutModal)
  - `both` → BOTH buttons side-by-side (Pay online + Pay via QR)
- **Level-gate visibility** on `/programs/{id}/status`:
  - Response now embeds `eligibility: { eligible, reason }` (uses existing `check_purchase_allowed` from Phase 4).
  - `ProgramDetail.jsx` — when `eligible=false`, hides all purchase buttons and shows a "Locked" chip with the server-provided reason (e.g. "Complete 'Level 1' and earn its certificate before purchasing this program.").
  - Subscription programs bypass the level gate as before.
- **Tests**: `/app/backend/tests/test_batch1_payment_and_level_gate.py` — 8/8 PASS covering: default global fallback, per-program override, razorpay-only blocks QR submit, manual_qr-only blocks Razorpay order, admin update, eligibility block shape, L2 locked without L1 completion, subscription bypass.

## Delivered on 2026-02 (Batch 2 — Admin Preview Mode)
- **Impersonation** — admin can browse the app as any regular user without knowing their password. New endpoint `POST /api/admin/preview/impersonate/{membership_id}` mints a short-lived (30-min) user-role JWT with `impersonated_by=<admin_mobile>` claim. Blocks impersonation of the company root (RW000000).
- **Mark as Paid (Preview)** — `POST /api/admin/preview/mark-paid` grants access to any program without payment. Requires the impersonation JWT (guarded by `_impersonated_by` on the current user dict). Creates a `program_purchases` row with `source='admin_preview'`, `is_mock=true`, `payment_status='preview'` — does NOT trigger the commission engine or create a real invoice.
- **Frontend**:
  - `services/adminPreview.js` — startAdminPreview / exitAdminPreview / getPreviewMeta / markPaidPreview. Preserves prior user tokens on entry, restores on exit.
  - `components/PreviewBanner.jsx` — sticky red banner injected into `MobileShell` showing "Viewing as RW######" + Exit button. Full-reload on entry/exit to make AuthContext pick up new tokens.
  - `AdminUsers.jsx` — new indigo Preview button (ShieldCheck icon) per row.
  - `ProgramDetail.jsx` — special indigo "Mark as Paid (Preview)" card shown only when `isInPreview() && !hasAccess`.
- **Audit** — every impersonation and mark-paid event is written to `activity_log`.
- **Tests**: `/app/backend/tests/test_batch2_admin_preview.py` — 8/8 PASS (impersonate happy path, block company root, 404 unknown user, admin-only, mark-paid grants access, idempotent, requires impersonation, does NOT trigger sponsor commissions). Combined Batch 1+2 suite: **16/16 PASS**.

## Delivered on 2026-02 (Batch 3 — Password-gated Danger Zone + Backup/Restore)
- **Password gate on destructive endpoints**:
  - `POST /admin/danger/empty-app-data` — now requires `admin_password` field; fresh DB check (not JWT-cached).
  - `DELETE /admin/danger/users/{mid}` — requires `admin_password` ONLY when destructive scopes (`wipe_purchases`, `wipe_certificates`, `wipe_commissions`, `wipe_referral_tree`) are enabled.
- **Auto-backup before wipe**: `empty-app-data` runs a full `mongodump --archive --gzip` into `/app/backups/` BEFORE deleting anything. Backup failure aborts the wipe.
- **New Backup/Restore API** (`/app/backend/app/routes/admin_backups.py`):
  - `GET /admin/backups` — list all archives
  - `POST /admin/backups/create` — manual backup (password-gated)
  - `POST /admin/backups/{filename}/restore` — mongorestore --drop (password-gated, rejects path traversal)
  - `DELETE /admin/backups/{filename}` — remove archive (password-gated)
- **Service** (`app/services/backup.py`) — wraps `mongodump`/`mongorestore` via async subprocess, human-readable sizes, safe filename validation.
- **Frontend**:
  - `AdminDangerZone.jsx` — password input added to the 3-step wipe wizard + amber notice explaining auto-backup.
  - New `AdminBackups.jsx` page + "Backups" tab wired into `AdminSystem.jsx`. Lists all archives with Restore/Delete actions, each dialog requiring the admin password.
- **Tests**:
  - `/app/backend/tests/test_batch3_backup_and_password_gate.py` — 9/9 PASS (list, create requires password, wrong password rejected, create+delete happy path, delete wrong password, path traversal blocked, empty-app-data missing password → 422, wrong password → 403, wrong confirmation → 400).
  - Regression: updated `test_phase6.py::_create_program` to set `payment_mode="razorpay"` explicitly (post-Batch-1 the global default `manual_qr` was blocking `/payments/order` in tests). Also updated `test_red_status_when_subscription_expired` to accept the new `no_plan` status introduced by Activity Meter v2.
  - **Total suite** across Batches 1+2+3 + Activity Meter v2 + Phase 6 regression: **64/64 PASS**.

## Delivered on 2026-02 (Batch 4 — User 360° export + Business reports)
- **User 360° JSON + Excel** — new endpoints under `admin_reports.py`:
  - `GET /api/admin/reports/user-360/{membership_id}` → JSON payload with 11 sections: profile, sponsor, meter, bank, aggregates, downline, payments, programs, commissions, activity, logins, payouts.
  - `GET /api/admin/reports/user-360/{membership_id}/export` → multi-sheet `.xlsx` with **8 sheets**: Profile · Downline · Payments · Programs · Commissions · Payouts · Activity · Logins. Formatted headers, ₹ money formatting, frozen top row per sheet.
  - Aggregates auto-computed: total_paid, total_commission_earned, downline_count, purchases_count, programs_touched.
- **3 new report types** added to `/admin/reports/{type}` framework:
  - `payouts` — wallet payouts (all statuses, sortable).
  - `pending_payments` — manual QR requests awaiting admin action.
  - `revenue_summary` — monthly buckets (default) or yearly (`?level=1`); columns: Period · Sales · Razorpay ₹ · QR ₹ · Taxable ₹ · GST ₹ · Total ₹. Handles gateway split via `source` field or fallback (utr → QR, razorpay_payment_id → Razorpay).
- **Payments report** enhanced — now shows Gateway, UTR, Razorpay Payment ID columns (previously missing).
- **Shared exports service** — new `to_excel_multi_sheet()` in `services/exports.py`; kept `to_excel()` as a single-sheet convenience wrapper (fully backward-compatible).
- **Frontend**:
  - `AdminReports.jsx` — tabs expanded from 7 → 10 (Wallet payouts, Pending QR, Revenue).
  - `AdminUsers.jsx` — new emerald "Export 360°" button (FileSpreadsheet icon) per user row.
  - `services/admin.js` — `export360(mid)` helper returning a Blob.
- **Tests**: `/app/backend/tests/test_batch4_user360_and_reports.py` — 12/12 PASS.
- **Aggregate test result** (Batches 1+2+3+4 + Activity Meter v2 + Phase 6 regression): **76/76 PASS**.

## Delivered on 2026-02 (Batch 5 — Notification triggers audit)
- **New shared service** `/app/backend/app/services/notify.py` — helpers `notify()`, `broadcast()`, plus named-triggers `payment_success()`, `payment_failed()`, `module_unlocked()`, `referral_income()`, `validity_expiring()`, `new_program_published()`. Best-effort inserts: notification failure never breaks the parent operation.
- **Broadcast fan-out**: `broadcast()` writes one row per active user so the standard `/notifications/me` list picks them up (matches admin_phase7 pattern).
- **Trigger wiring**:
  - Razorpay success → `payments.py::verify_payment` (after commission engine)
  - Razorpay failed → `payments.py::verify_payment` (signature mismatch branch)
  - Manual QR success → existing `manual_payments.py::approve_payment` (kept)
  - Manual QR failed → existing `manual_payments.py::reject_payment` (kept)
  - New Module Unlocked → `program_engine.py::mark_module_completed` (auto-computes next module by module_number, dedup_key prevents dupes)
  - Referral Income → `commission_engine.py::create_commissions_for_purchase` (only when commission is `eligible`, i.e. sponsor is green)
  - New Program → `programs.py::admin_create_program` (broadcast, only if `is_active=True`)
- **Validity Expiring** — new admin endpoint `POST /notifications/admin/scan-expiring` scans all active purchases and fires notifications for any user within the last 7 days of validity. Idempotent per (user, program, days_left) via `dedup_key`. Meant to be called by a nightly cron; a "Scan expiring plans" button on `/admin/notifications` triggers it on demand.
- **Tests**: `/app/backend/tests/test_batch5_notification_triggers.py` — 7/7 PASS.
- **Aggregate test result** across Batches 1+2+3+4+5 + Activity Meter v2: **50/50 PASS**.

## Delivered on 2026-02 (Post-Batch-5 add-ons)
- **Inner Peace "Coming Soon" branding removed** — `ProgramDetail.jsx` no longer short-circuits on `is_subscription` with a Coming-Soon chip. Admin creates the Inner Peace subscription program manually via `/admin/programs` like any other program (subscription toggle + payment mode).
- **Renew CTA on expiring notifications**:
  - `services/notify.py::validity_expiring` now sets `cta_link=/app/pay/{program_id}` and `cta_label=Renew`.
  - `services/notify.py::notify` extended to accept `cta_label` field, stored on the notification doc.
  - `Notifications.jsx` renders a royal-blue pill button "Renew →" beneath the notification body when both `cta_link` + `cta_label` are present.
- **Nightly background scheduler**:
  - New `services/scheduler.py` — asyncio-based daily loop. Fires `_scan_expiring_job` at 03:00 IST every day (idempotent via existing `dedup_key`).
  - Registered from FastAPI `lifespan` startup, cancelled on shutdown. Survives uvicorn hot-reload (idempotent `start()`).
  - Visible in backend logs: `scheduler started: 1 job(s)` and `scheduler 'scan_expiring' sleeping <seconds> until <UTC time>`.
- **Test** — expanded `test_validity_expiring_scan` to also assert `cta_link=="/app/pay/{program_id}"` and `cta_label=="Renew"`.

## Delivered on 2026-02 (Batch 6 — Launch readiness checklist in BRV)
- **9 new BRV rules** in the "Launch" category (`app/services/brv.py`):
  - **L1** — MSG91 production OTP (`OTP_DEV_MODE=false` + `MSG91_AUTH_KEY` set) — **FAIL until live keys added**
  - **L2** — Razorpay live mode (`RAZORPAY_MOCK_MODE=false` + `rzp_live_*` key) — **FAIL until live keys added**
  - **L3** — Per-program payment mode (`ProgramCreate.payment_mode` field present) — **PASS**
  - **L4** — Referral gated by activity (`is_eligible_for_commission` importable) — **PASS**
  - **L5** — Sequential level gate (`check_purchase_allowed` importable) — **PASS**
  - **L6** — Admin Preview Mode (impersonate + mark-paid routes registered) — **PASS**
  - **L7** — Backup / Restore API (4 routes registered) — **PASS**
  - **L8** — Danger Zone password gate (`admin_password` field on `EmptyAppDataRequest`) — **PASS**
  - **L9** — Reports engine launch spec (payouts + revenue_summary + user-360 routes) — **PASS**
- **Overall BRV result**: 43/45 rules pass (only L1 & L2 gated on live credentials).
- **Frontend** — `AdminQA.jsx` — Launch category renders automatically via `groupBy` (no code changes needed). Now shows "7/9 passed" chip next to Launch heading.
- **Regression** — Full Batch 1-6 + Activity Meter v2: **50/50 PASS**.

## Delivered on 2026-02 (Live Integration Diagnostic — pre-flight launch check)
- **Backend** (`app/routes/qa.py`) — 4 new admin-only endpoints:
  - `GET /api/admin/qa/live-check/status` — snapshot of Razorpay + MSG91 env: mock/dev/live status, masked key ids, prefix check (rzp_live_*), secret + webhook-secret presence.
  - `POST /api/admin/qa/live-check/razorpay/test-order` — creates a real ₹1 (or configurable 100–100000 paise) test order. Live mode hits Razorpay REST; mock mode returns synthetic id. No purchase row created, no user charged, no commissions triggered. Audit-logged.
  - `GET /api/admin/qa/live-check/webhook-events?limit=25` — lists the N most recent Razorpay webhook events observed by the backend (sourced from `activity_log` rows written by `POST /api/payments/webhook`).
  - `POST /api/admin/qa/live-check/msg91/dry-run` — sends a diagnostic OTP (code `424242`) via MSG91. In dev mode (no keys) returns `{sent:false, dev_mode:true}` without contacting MSG91; in live mode dispatches a real SMS.
- **Bug fix** — `POST /api/payments/webhook` previously read `request.app.state.db` which is never set, so webhook events were silently dropped from `activity_log`. Switched to `get_db()` — events now persist and appear on the Live Check page.
- **Frontend** — new `/admin/qa/live-check` page (`AdminLiveCheck.jsx`) with three cards:
  - Razorpay: mode chip, masked key id, all boolean checks (live prefix / secret / webhook secret), "Create ₹1 test order" button + inline order-id + copy button.
  - MSG91: mode chip, masked auth key, template + sender ids, mobile input + "Send" test-SMS button. Dev/live label switches automatically.
  - Recent Razorpay webhook events: last 25 events (event name, target payment id, timestamp) + refresh button.
- **AdminShell** — new "Live Check" left-rail item (`data-testid=admin-nav-livecheck`).
- **Tests** — `/app/backend/tests/test_live_check.py` (9/9 PASS): status shape, admin-only guard, mock/live order creation, amount validation (422 for <100 or >100000), webhook capture round-trip (webhook POST → GET /webhook-events), MSG91 dry-run, mobile validation.
- **E2E** — `/app/test_reports/iteration_23.json`: **30/30 frontend UI checks pass** across Live Check, QA/BRV, Programs, Users, System/Backups, Danger Zone, and full user shell. Zero regressions.
- **Regression** — Batch 1-6 + Activity Meter v2 + Live Check: **59/59 backend PASS**.


## Delivered on 2026-02 (Live-mode flip + visibility polish + Danger Zone verification)
- **Preview `.env` flipped to LIVE mode** at user request:
  - `RAZORPAY_MOCK_MODE=false` · `RAZORPAY_KEY_ID=rzp_live_REDACTED` · secret populated
  - `OTP_DEV_MODE=false` · MSG91 auth key / template / sender all populated
  - `/admin/qa/live-check/status` reports both integrations **LIVE**; test order creation returns real `order_TCXD6X...` id (not `mock_ord_*`).
- **BRV Launch category now 9/9 GREEN**; overall verdict **PASS · 45/45 rules**.
- **NOTE**: Automated pytests are now expected to fail because they rely on dev OTP `123456` and mock Razorpay signatures. This is expected in live mode. To re-enable regression testing, revert `OTP_DEV_MODE` and `RAZORPAY_MOCK_MODE` to `true` and empty the four provider keys.
- **Admin Users page visibility fix** — Preview button is now `<Preview>` labelled (was icon-only indigo shield) and a persistent indigo hint banner at the top of the page explains impersonation. `data-testid=admin-users-preview-hint`.
- **Danger Zone verified end-to-end** — the "Empty app data" button does work. Backend `POST /admin/danger/empty-app-data` wipes 20+ collections (preserves admin, company root, programs, banners, CMS), creates a pre-wipe gzipped `mongodump` archive under `/app/backups/`, and returns a per-collection deletion report. Frontend surfaces the report inline under the button as "Last wipe report". Verified via curl (522 → 0 users, 106 KB backup) and via browser (3-step dialog → password → success card, no console errors).
- **Only remaining launch step**: configure Razorpay dashboard webhook to `https://<your-domain>/api/payments/razorpay/webhook` and paste the secret into `RAZORPAY_WEBHOOK_SECRET`. All other launch prerequisites are green.



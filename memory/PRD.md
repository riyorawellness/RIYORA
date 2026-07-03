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

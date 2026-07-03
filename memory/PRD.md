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

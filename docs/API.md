# RIYORA WELLNESS — API Documentation

The canonical, always-up-to-date OpenAPI spec is served at:
```
{REACT_APP_BACKEND_URL}/docs        # Swagger UI
{REACT_APP_BACKEND_URL}/openapi.json
```

## Module map (Phase → Path)

| Phase | Module | Base path | Description |
|---|---|---|---|
| 1 | Auth | `/api/auth/*` | Register, login, OTP, refresh, logout, forgot/reset, `/me` |
| 1 | Admin | `/api/admin/*` | Admin login, profile, stats |
| 1 | Membership | `/api/membership/*` | Referral validation, `/me` |
| 2 | Programs | `/api/programs/*` | List, detail, admin CRUD |
| 2 | Modules | `/api/modules/*` | List by program, admin CRUD |
| 2 | Assessments | `/api/assessments/*` | Fetch, submit, admin CRUD |
| 2 | Purchases | `/api/purchases/*` | User history, admin CRUD |
| 2 | Progress | `/api/progress/*` | Per-user/program |
| 2 | Certificates | `/api/certificates/*` | List, admin CRUD |
| 2 | Referral tree | `/api/referral-tree/*` | Downline / upline |
| 2 | Bank details | `/api/bank-details/*` | Own + admin verify |
| 2 | Notifications | `/api/notifications/*` | Personal + admin |
| 4 | Content | `/api/content/*` | Signed URL token + streaming |
| 5 | Payments | `/api/payments/*` | Order, verify, webhook, subscription, admin ops |
| 6 | Referrals | `/api/referrals/*` | Dashboard, team, QR, admin settings |
| 6 | Activity | `/api/activity/*` | Meter, session log, reminders |
| 6 | Commissions | `/api/commissions/*` | User + admin ledger |
| 6 | Payouts | `/api/payouts/*` | User + admin queue |
| 6 | Reports (user) | `/api/reports/{type}` | 5 report types · PDF/CSV/Excel |
| 7 | Admin Dashboard | `/api/admin/dashboard/*` | Overview, series, top-N, feeds |
| 7 | Admin Users | `/api/admin/users/*` | Search, detail, update, status, reset password, export |
| 7 | CMS | `/api/admin/cms/*` | Pages, versions |
| 7 | System | `/api/admin/system/*` + `/security/*` | Settings |
| 7 | Uploads | `/api/admin/uploads/*` | File uploads |
| 7 | Banners | `/api/admin/banners/*` | CRUD |
| 8 | Analytics | `/api/analytics/*` | Financial + user analytics |
| 8 | Admin Reports | `/api/admin/reports/{type}` and `/export` | 7 report types |
| 9 | Health | `/api/health/{live,ready,deep}` | Ops probes |
| 9 | QA / BRV | `/api/admin/qa/brv[/pdf]` | Business Rule Validation report |

## Auth
All non-public endpoints require:
```
Authorization: Bearer <access_token>
```
Access tokens expire after `JWT_ACCESS_TTL_MIN` minutes. Rotate via `POST /api/auth/refresh`.

## Errors
Every error returns `{ "detail": "<human message>" }` with the appropriate HTTP status:
- `400` — validation / bad request
- `401` — missing / invalid token
- `403` — wrong role
- `404` — not found
- `409` — conflict (duplicate)
- `413` — payload too large (upload)
- `429` — rate limit / brute-force lockout
- `500` — unexpected

## Rate Limiting
- Global: 120 req/min per IP.
- Login (`/api/auth/login`, `/api/admin/login`): additionally lock the mobile
  number for 15 min after 5 failed attempts.

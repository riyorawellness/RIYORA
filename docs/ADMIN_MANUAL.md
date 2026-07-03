# RIYORA WELLNESS — Admin Manual

## 1. Getting Started
- Access the admin panel at `<domain>/admin/login`.
- Default credentials on first boot come from `ADMIN_MOBILE` + `ADMIN_PASSWORD`.
  **Change the password immediately** via `/admin/profile`.

## 2. Left-rail Navigation
| Section | Path | Purpose |
|---|---|---|
| Dashboard | `/admin/dashboard` | Real-time KPIs, revenue trend, top sellers, top referrers, activity feed |
| Analytics | `/admin/analytics` | Deep financial dashboard — filters, comparative charts, subscription health, leaderboards |
| Reports | `/admin/reports` | 7 tabular reports · CSV / Excel / PDF exports · filters + pagination |
| Users | `/admin/users` | User roster · search · status change · password reset · profile modal |
| Payments | `/admin/payments` | Transactions · refund · GST settings |
| Referrals | `/admin/referrals` | Commissions · bulk-approve · Payouts queue · Settings |
| Notifications | `/admin/notifications` | Compose & broadcast in-app notifications |
| Banners | `/admin/banners` | Home / offer banners with schedule |
| CMS | `/admin/cms` | Terms, Privacy, Refund, About, Contact, FAQ, Support pages |
| System | `/admin/system` | Company info, social links, application settings, security thresholds |
| Audit log | `/admin/audit` | Every admin write action with filter + pagination |
| QA / BRV | `/admin/qa` | Business Rule Validation runner + PDF report |

## 3. Common Tasks
### Approve a commission
1. Go to **Referrals → Commissions** tab.
2. Filter by `status=Pending`.
3. Select rows → **Bulk approve** OR click a single row → **Approve**.

### Create a payout
1. **Referrals → Payouts → New payout**.
2. Choose the member from *pending by user* list.
3. Select the commissions to include, pick a method (Bank/UPI/Manual) → Create.
4. Later, **Mark paid** with the bank reference.

### Send a broadcast notification
1. **Notifications → Compose**.
2. Toggle **Broadcast** ON to send to all users.
3. Choose category (announcement / offer / renewal / system / program / activity).
4. Type title + body → **Send**.

### Publish a CMS page
1. **CMS** → choose slug in sidebar.
2. Edit body (Markdown allowed) → **Publish**.
3. Previous versions are kept as snapshots.

### Run BRV before go-live
1. **QA / BRV → Run BRV**.
2. Review the category cards; every rule should be green (Pass).
3. Click **Download PDF report** for records. Do NOT deploy if verdict = FAIL.

## 4. Reports & Exports
Every report supports **CSV / Excel / PDF** export. Exports include ALL matching
rows (up to 20k) — not just the current page.

## 5. System settings
- **Application version**, **maintenance mode**, **support email/mobile**,
  **social links** — all editable from `/admin/system`.
- **Security thresholds** (password length, OTP TTL, login attempt limit,
  session timeout) live in a separate `Security` tab.

## 6. Emergency
- Suspend a user → **Users → row → Status = suspended** (also revokes all
  their refresh tokens).
- Reset a user password → **Users → row → Reset password**.

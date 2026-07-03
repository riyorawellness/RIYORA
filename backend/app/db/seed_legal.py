"""Default placeholder content for the legal + support CMS pages.

Seeded on backend startup — only inserts a page if one doesn't already exist,
so admin edits are never overwritten. Editable at any time from /admin/cms.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase


_DEFAULTS = {
    "privacy": {
        "title": "Privacy Policy",
        "meta_description": "How RIYORA Wellness collects, uses and safeguards your data.",
        "body": """# Privacy Policy

**Last updated:** 03 Jul 2026

## 1. Introduction
Welcome to RIYORA Wellness. We take your privacy seriously. This policy explains what data we collect, why we collect it, and how we keep it safe.

## 2. Information We Collect
- **Account data** — mobile number, name, referral ID, city and state provided at registration.
- **Payment data** — invoice records and Razorpay payment references (we never store card numbers).
- **Usage data** — program progress, module completion, session logs, referral earnings, in-app notifications.
- **Device data** — installed PWA metadata, browser type and IP address for security auditing.

## 3. How We Use Your Data
- Provide access to your purchased programs, subscription and community features.
- Compute commissions and Activity Meter status for the 3-level referral system.
- Send in-app notifications for renewal reminders, activity milestones and announcements.
- Generate GST-compliant invoices and PDF reports.
- Prevent fraud and secure your account.

## 4. Sharing
We never sell your data. Limited data is shared only with:
- **Razorpay** for payment processing (order creation + signature verification).
- **Regulatory authorities** if required by Indian law.
- **Service providers** under strict confidentiality (hosting, email/SMS delivery).

## 5. Your Rights
- Access, correction or deletion of your data at any time — email us.
- Withdraw consent by requesting account deletion (subject to retention required by tax law).
- Data portability — export your reports as PDF/Excel/CSV from the app.

## 6. Retention
Account and transaction records are retained for a minimum of 7 years for tax compliance. Non-essential data is purged after 12 months of inactivity.

## 7. Contact
For any privacy questions, email us at **info@riyorawellness.com**.
""",
        "is_published": True,
    },
    "terms": {
        "title": "Terms of Service",
        "meta_description": "The terms and conditions governing your use of RIYORA Wellness.",
        "body": """# Terms of Service

**Last updated:** 03 Jul 2026

## 1. Acceptance
By creating an account, subscribing or otherwise using RIYORA Wellness (the "Service"), you agree to these Terms.

## 2. Eligibility
You must be 18+ and provide a valid Indian mobile number. You are responsible for the accuracy of the information you provide.

## 3. Membership
- On successful registration, a permanent Membership ID (format `RW######`) is issued.
- Referral IDs are mandatory. The company account `RW000000` is the root of the referral tree.
- Membership IDs are non-transferable.

## 4. Programs & Access
- Access to a program is granted only after successful payment verification.
- Certain programs (Levels 2–5) require prior completion of predecessor programs.
- Subscription programs (Inner Peace) auto-renew per the selected plan and can be cancelled at any time.
- All content is streaming-only; downloading, printing or redistributing content is prohibited and may result in permanent suspension.

## 5. Refer & Earn
- 3-level referral commissions are computed on eligible purchases as per current admin settings.
- Commissions are payable only if the sponsor's Activity Meter is **green** at the time of the buyer's purchase.
- The 4-session rule within a subscription cycle must be met to maintain eligibility.
- The company account (`RW000000`) is excluded from commission payouts.

## 6. Payments & GST
- All prices displayed on the app are in INR, inclusive of applicable GST.
- Refunds, when applicable, are processed via Razorpay within 5–7 working days.
- Duplicate payments are automatically detected and reversed.

## 7. Payouts
- Approved commissions are paid to the bank account you have verified in the app.
- Payout requests are processed manually by an admin. TDS may be deducted as per Indian tax law.

## 8. Acceptable Use
You agree not to:
- Share account credentials or content;
- Automate registration or referral creation;
- Attempt to reverse-engineer, hack or overload the service.

## 9. Termination
We may suspend or terminate any account that breaches these terms. On termination, unpaid commissions may be forfeited.

## 10. Governing Law
These Terms are governed by the laws of India, and any dispute is subject to the exclusive jurisdiction of the courts of Mumbai, Maharashtra.

## 11. Contact
For any question about these Terms, email **info@riyorawellness.com**.
""",
        "is_published": True,
    },
    "data-security": {
        "title": "Data & Security",
        "meta_description": "How we protect your account, payments and content on RIYORA Wellness.",
        "body": """# Data & Security

**Last updated:** 03 Jul 2026

## Overview
RIYORA Wellness is built with security-first principles. Below is a summary of the controls in place to keep your account, data and payments safe.

## Authentication
- 6-digit OTP with 5-minute validity for registration and password reset.
- Passwords are hashed with **bcrypt** (`$2b$`) — we never store your password in plain text.
- JWT access tokens (short-lived) with rotating refresh tokens.
- Automatic **brute-force lockout** — 5 failed login attempts triggers a 15-minute cool-down.

## Transport
- All traffic is encrypted with HTTPS (TLS 1.2+).
- HSTS + Content-Security-Policy + X-Frame-Options headers are enforced.

## Payment Security
- Payment processing is handled entirely by **Razorpay** — we never see or store card details.
- Every payment is signature-verified server-side before program access is granted.
- Duplicate payments are blocked at the database layer.

## Content Protection
- Videos, audio and PDFs are streamed via time-limited signed URLs.
- Downloading, printing or copying content is disabled at the client level.
- A dynamic **watermark** with your name and Membership ID appears on all protected content.

## Data at Rest
- Data lives in a managed MongoDB with encrypted storage.
- Automated daily backups with 14-day retention.
- Access to backups is restricted to authorised personnel only.

## Your Responsibilities
- Keep your password confidential.
- Log out from shared devices.
- Report any suspicious activity to **info@riyorawellness.com** immediately.

## Reporting Vulnerabilities
If you discover a security issue, please email **info@riyorawellness.com** — we appreciate responsible disclosure and investigate every report.
""",
        "is_published": True,
    },
    "faq": {
        "title": "Help & FAQ",
        "meta_description": "Frequently asked questions about RIYORA Wellness.",
        "body": """# Help & FAQ

**Last updated:** 03 Jul 2026

### Getting Started
**Q. How do I sign up?**
Register with your Indian mobile number, verify the OTP, then complete your profile. A valid **Referral ID** is mandatory — if you don't have one, use `RW000000`.

**Q. What is a Membership ID?**
A permanent 8-character identifier (`RW######`) issued on successful registration. Share it with anyone you refer.

### Programs
**Q. Can I access all programs immediately?**
No. Advanced levels unlock only after you complete the prior program.

**Q. What is the Inner Peace subscription?**
A recurring subscription that gives access to daily meditation content + live sessions and drives the 4-session Activity Meter rule.

### Payments
**Q. Which payment methods are supported?**
UPI, cards and net-banking via Razorpay.

**Q. How do I get my invoice?**
Every successful payment generates a GST-compliant PDF invoice, available under Profile → Transactions & invoices.

### Refer & Earn
**Q. When do I earn a commission?**
When someone you referred (up to 3 levels deep) buys a program, provided your Activity Meter is green.

**Q. What is the 4-session rule?**
You must complete 4 valid activity sessions within each subscription cycle to remain eligible for referral commissions.

**Q. When do I receive payouts?**
Approved commissions are batched into a payout by the admin. Bank transfers reach your account within 3–5 working days.

### Account
**Q. How do I change my password?**
Log out, click *Forgot password* and follow the OTP flow.

**Q. How do I contact support?**
Email **info@riyorawellness.com** — we typically reply within one business day.
""",
        "is_published": True,
    },
    "contact": {
        "title": "Contact Us",
        "meta_description": "How to reach the RIYORA Wellness support team.",
        "body": """# Contact Us

We would love to hear from you.

## Support Email
**info@riyorawellness.com**
_Response time: within 1 business day._

Please use the subject line **"Support Request - RIYORA Wellness"** to help us route your query faster.

## Office
RIYORA Wellness Private Limited
Mumbai, Maharashtra, India

## Business Hours
Monday – Saturday · 10:00 – 19:00 IST
""",
        "is_published": True,
    },
}


async def seed_legal_pages(db: AsyncIOMotorDatabase) -> None:
    """Insert placeholder legal/support pages the first time only — never
    overwrite an admin's edits."""
    now = datetime.now(timezone.utc).isoformat()
    for slug, doc in _DEFAULTS.items():
        existing = await db.cms_pages.find_one({"slug": slug, "deleted_at": None})
        if existing:
            continue
        await db.cms_pages.insert_one(
            {
                "id": str(uuid.uuid4()),
                "slug": slug,
                **doc,
                "created_at": now,
                "updated_at": now,
                "updated_by": "system",
                "deleted_at": None,
            }
        )

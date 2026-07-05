"""MSG91 Flow API v5 client for sending OTP SMS to Indian mobile numbers.

Env-driven. If any of the three required env vars are missing, the module
signals "not configured" and callers must fall back to the local dev OTP.

Env vars:
    MSG91_AUTH_KEY      — from MSG91 dashboard → Auth Keys
    MSG91_TEMPLATE_ID   — DLT-approved Flow / Template ID (the one carrying
                          the ``##OTP##`` variable in the approved wording)
    MSG91_SENDER_ID     — 6-char DLT-registered sender ID (e.g. RIYORA)
    MSG91_OTP_VAR       — variable name inside the DLT template (default
                          "OTP" — must exactly match the placeholder key)
    MSG91_FLOW_URL      — override (default https://control.msg91.com/api/v5/flow)
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)


class Msg91Error(RuntimeError):
    """Raised when MSG91 returns a non-2xx response or the network fails."""


def _cfg() -> dict | None:
    """Return MSG91 config dict, or None if not fully configured."""
    auth = os.environ.get("MSG91_AUTH_KEY", "").strip()
    template = os.environ.get("MSG91_TEMPLATE_ID", "").strip()
    sender = os.environ.get("MSG91_SENDER_ID", "").strip()
    if not (auth and template and sender):
        return None
    return {
        "auth_key": auth,
        "template_id": template,
        "sender_id": sender,
        "otp_var": os.environ.get("MSG91_OTP_VAR", "OTP").strip() or "OTP",
        "url": os.environ.get(
            "MSG91_FLOW_URL", "https://control.msg91.com/api/v5/flow"
        ).strip(),
    }


def is_configured() -> bool:
    return _cfg() is not None


async def send_otp_sms(mobile: str, otp_code: str) -> bool:
    """Send an OTP SMS via MSG91 Flow API v5.

    Returns True on success. Raises Msg91Error on failure. If MSG91 is not
    configured, returns False WITHOUT raising — callers are expected to
    treat False as "SMS not sent, use dev fallback".

    ``mobile`` may be a 10-digit Indian number (prepends 91) or already
    include a country code.
    """
    cfg = _cfg()
    if cfg is None:
        return False

    # Normalise: MSG91 expects country-code prefixed digits, e.g. 919999999999.
    m = mobile.strip().lstrip("+")
    if len(m) == 10 and m.isdigit():
        m = "91" + m

    payload = {
        "template_id": cfg["template_id"],
        "sender": cfg["sender_id"],
        "short_url": "0",
        "mobiles": m,
        cfg["otp_var"]: otp_code,
    }
    headers = {
        "authkey": cfg["auth_key"],
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(cfg["url"], json=payload, headers=headers)
    except httpx.HTTPError as exc:
        logger.warning("[MSG91] network error: %s", exc)
        raise Msg91Error(f"MSG91 network error: {exc}") from exc

    if resp.status_code >= 400:
        # Never log OTP code, but do log MSG91's diagnostic message.
        body = resp.text[:400]
        logger.warning(
            "[MSG91] send failed status=%s body=%s", resp.status_code, body
        )
        raise Msg91Error(f"MSG91 send failed ({resp.status_code}): {body}")

    logger.info("[MSG91] OTP dispatched to %s (status=%s)", m, resp.status_code)
    return True

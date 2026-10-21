"""SMS verification-code delivery.

Two providers, selected by ``SMS_PROVIDER``:

- ``demo`` (default): nothing leaves the server. The code is printed to the
  server log and, when a Streamlit runtime exists, mirrored into
  ``st.session_state["_demo_last_sms"]`` so the registration page can show it.
  Every Streamlit interaction is wrapped in try/except so bare pytest and
  scripts never crash.
- ``twilio``: real SMS via the Twilio Messages REST API, using only the
  standard library (urllib + HTTP Basic auth). Missing credentials raise a
  RuntimeError that points at the Secrets configuration.
"""

from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from infra.config import (
    SMS_PROVIDER,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_FROM_NUMBER,
)

logger = logging.getLogger(__name__)

_TWILIO_API_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


def send_verification_code(phone: str, code: str) -> None:
    """Deliver *code* to *phone* via the configured provider.

    Raises on delivery failure so callers can roll back any stored state.
    """
    if SMS_PROVIDER == "twilio":
        _send_via_twilio(phone, code)
        return
    _send_via_demo(phone, code)


def _send_via_demo(phone: str, code: str) -> None:
    """Log the code and mirror it into session state for the demo UI."""
    print(f"[sms-demo] code for {phone}: {code}")
    logger.info("[sms-demo] code for %s: %s", phone, code)
    try:
        from streamlit import runtime

        if not runtime.exists():
            return
        import streamlit as st

        st.session_state["_demo_last_sms"] = {"phone": phone, "code": code}
    except Exception:
        # The session mirror is a convenience; the log line is the record.
        pass


def _send_via_twilio(phone: str, code: str) -> None:
    """Send a real SMS through the Twilio Messages API (stdlib only)."""
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER):
        raise RuntimeError(
            "SMS_PROVIDER is 'twilio' but TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / "
            "TWILIO_FROM_NUMBER are not all set — configure them in Streamlit "
            "Cloud Secrets (or env / .env locally)."
        )
    body = urllib.parse.urlencode(
        {
            "To": f"+86{phone}",
            "From": TWILIO_FROM_NUMBER,
            "Body": f"Your InstaSpark AI verification code is {code}. It expires in 5 minutes.",
        }
    ).encode("utf-8")
    credentials = base64.b64encode(f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        _TWILIO_API_URL.format(sid=TWILIO_ACCOUNT_SID),
        data=body,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        # urlopen raises HTTPError on 4xx/5xx, so error details live on the
        # exception — Twilio returns a JSON body with a readable "message".
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 400:
                raise RuntimeError(f"Twilio rejected the SMS send with HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        detail = exc.reason
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("message", detail)
        except Exception:
            pass
        raise RuntimeError(f"Twilio SMS send failed (HTTP {exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Twilio SMS send failed: {exc.reason}") from exc

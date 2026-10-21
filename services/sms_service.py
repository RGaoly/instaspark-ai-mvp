"""SMS verification-code delivery.

Three providers, selected by ``SMS_PROVIDER``:

- ``demo`` (default): nothing leaves the server. The code is printed to the
  server log and, when a Streamlit runtime exists, mirrored into
  ``st.session_state["_demo_last_sms"]`` so the registration page can show it.
  Every Streamlit interaction is wrapped in try/except so bare pytest and
  scripts never crash.
- ``twilio``: real SMS via the Twilio Messages REST API, using only the
  standard library (urllib + HTTP Basic auth). Missing credentials raise a
  RuntimeError that points at the Secrets configuration.
- ``aliyun``: Aliyun PNVS "SMS verification" (dypnsapi.aliyuncs.com, RPC
  style, ACS-HMAC-SHA1 signed GET). Aliyun generates the code itself when
  sending (``SendSmsVerifyCode`` with the ``##code##`` template placeholder),
  so the send call carries no code; verification is delegated to
  ``CheckSmsVerifyCode`` via :func:`check_code_via_aliyun`. Missing
  credentials raise a RuntimeError that points at the Secrets configuration.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from infra.config import (
    ALIYUN_ACCESS_KEY_ID,
    ALIYUN_ACCESS_KEY_SECRET,
    ALIYUN_SMS_SCHEME_NAME,
    ALIYUN_SMS_SIGN_NAME,
    ALIYUN_SMS_TEMPLATE_CODE,
    SMS_CODE_LENGTH,
    SMS_CODE_TTL_SECONDS,
    SMS_PROVIDER,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_FROM_NUMBER,
)

logger = logging.getLogger(__name__)

_TWILIO_API_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"

_ALIYUN_ENDPOINT = "https://dypnsapi.aliyuncs.com"
_ALIYUN_API_VERSION = "2017-05-25"


def send_verification_code(phone: str, code: str) -> None:
    """Deliver *code* to *phone* via the configured provider.

    Raises on delivery failure so callers can roll back any stored state.
    The aliyun provider ignores *code* — Aliyun generates the code itself.
    """
    if SMS_PROVIDER == "twilio":
        _send_via_twilio(phone, code)
        return
    if SMS_PROVIDER == "aliyun":
        _send_via_aliyun(phone)
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


# ─── Aliyun PNVS "SMS verification" (dypnsapi) ─────────────────
# RPC-style API signed with ACS-HMAC-SHA1:
#   StringToSign = "GET&%2F&" + percent_encode(canonicalized_query)
#   Signature    = Base64(HMAC-SHA1(AccessKeySecret + "&", StringToSign))
# where canonicalized_query is every parameter (public + action) sorted by
# key, each key/value RFC3986-encoded, joined with "&". SendSmsVerifyCode
# bills per carrier receipt (failures are free); CheckSmsVerifyCode is free.


def _aliyun_percent_encode(value: object) -> str:
    """RFC3986 encoding as Aliyun expects: unreserved = A-Za-z0-9-._~ only."""
    return urllib.parse.quote(str(value), safe="~")


def _aliyun_signed_query(
    action: str,
    params: dict[str, str],
    *,
    nonce: str | None = None,
    timestamp: str | None = None,
) -> str:
    """Return the full signed query string for an Aliyun RPC GET call.

    ``nonce``/``timestamp`` are injectable so tests can pin the signature.
    """
    all_params = {
        "Format": "JSON",
        "Version": _ALIYUN_API_VERSION,
        "AccessKeyId": ALIYUN_ACCESS_KEY_ID,
        "SignatureMethod": "HMAC-SHA1",
        "Timestamp": timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "SignatureVersion": "1.0",
        "SignatureNonce": nonce or str(uuid.uuid4()),
        "Action": action,
        **params,
    }
    canonical = "&".join(
        f"{_aliyun_percent_encode(key)}={_aliyun_percent_encode(value)}"
        for key, value in sorted(all_params.items())
    )
    string_to_sign = "GET&%2F&" + _aliyun_percent_encode(canonical)
    digest = hmac.new(
        (ALIYUN_ACCESS_KEY_SECRET + "&").encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    signature = base64.b64encode(digest).decode("ascii")
    return f"{canonical}&Signature={_aliyun_percent_encode(signature)}"


def _aliyun_rpc(action: str, params: dict[str, str]) -> dict:
    """Call a dypnsapi RPC action and return the parsed response Body.

    Raises RuntimeError on transport errors, HTTP errors (Aliyun error JSON
    carries ``Code``/``Message``) and business failures (HTTP 200 but
    ``Body.Code != "OK"``).
    """
    query = _aliyun_signed_query(action, params)
    request = urllib.request.Request(f"{_ALIYUN_ENDPOINT}?{query}", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.reason
        try:
            body = json.loads(exc.read().decode("utf-8"))
            detail = body.get("Message") or body.get("Code") or detail
        except Exception:
            pass
        raise RuntimeError(f"Aliyun SMS {action} failed (HTTP {exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Aliyun SMS {action} failed: {exc.reason}") from exc
    if payload.get("Code") != "OK":
        raise RuntimeError(
            f"Aliyun SMS {action} rejected: {payload.get('Code')} — {payload.get('Message', '')}"
        )
    return payload


def _aliyun_access_keys_missing() -> bool:
    return not (ALIYUN_ACCESS_KEY_ID and ALIYUN_ACCESS_KEY_SECRET)


def _send_via_aliyun(phone: str) -> None:
    """Send an Aliyun-generated verification code via SendSmsVerifyCode."""
    if _aliyun_access_keys_missing() or not (ALIYUN_SMS_SIGN_NAME and ALIYUN_SMS_TEMPLATE_CODE):
        raise RuntimeError(
            "SMS_PROVIDER is 'aliyun' but ALIYUN_ACCESS_KEY_ID / ALIYUN_ACCESS_KEY_SECRET / "
            "ALIYUN_SMS_SIGN_NAME / ALIYUN_SMS_TEMPLATE_CODE are not all set — configure them "
            "in Streamlit Cloud Secrets (or env / .env locally)."
        )
    params = {
        "PhoneNumber": phone,
        "SignName": ALIYUN_SMS_SIGN_NAME,
        "TemplateCode": ALIYUN_SMS_TEMPLATE_CODE,
        # "##code##" makes Aliyun generate the code (required for it to be
        # checkable via CheckSmsVerifyCode); "min" fills the template's
        # validity placeholder.
        "TemplateParam": json.dumps(
            {"code": "##code##", "min": str(SMS_CODE_TTL_SECONDS // 60)},
            separators=(",", ":"),
        ),
        # Keep Aliyun-side code length / TTL aligned with local semantics.
        "CodeLength": str(SMS_CODE_LENGTH),
        "ValidTime": str(SMS_CODE_TTL_SECONDS),
    }
    if ALIYUN_SMS_SCHEME_NAME:
        params["SchemeName"] = ALIYUN_SMS_SCHEME_NAME
    _aliyun_rpc("SendSmsVerifyCode", params)


def check_code_via_aliyun(phone: str, code: str) -> bool:
    """Ask Aliyun whether *code* passes for *phone* (CheckSmsVerifyCode).

    Returns True only when ``Body.Model.VerifyResult == "PASS"``; a rejected
    code returns False. Raises RuntimeError when the call itself fails
    (network, credentials, or a business error) so the UI can tell the user
    the verification service is unavailable instead of burning an attempt.
    """
    if _aliyun_access_keys_missing():
        raise RuntimeError(
            "SMS_PROVIDER is 'aliyun' but ALIYUN_ACCESS_KEY_ID / ALIYUN_ACCESS_KEY_SECRET "
            "are not both set — configure them in Streamlit Cloud Secrets (or env / .env locally)."
        )
    params = {"PhoneNumber": phone, "VerifyCode": code}
    if ALIYUN_SMS_SCHEME_NAME:
        params["SchemeName"] = ALIYUN_SMS_SCHEME_NAME
    payload = _aliyun_rpc("CheckSmsVerifyCode", params)
    model = payload.get("Model") or {}
    return str(model.get("VerifyResult", "")).upper() == "PASS"

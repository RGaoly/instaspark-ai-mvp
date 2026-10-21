"""Tests for the aliyun SMS provider (Aliyun PNVS "SMS verification").

Everything network-facing is mocked at urllib.request.urlopen — no real
HTTP calls, no real credentials. Covers the ACS-HMAC-SHA1 signing, the
SendSmsVerifyCode / CheckSmsVerifyCode wrappers, and the delegated
issue/verify flow in infra.auth.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from types import SimpleNamespace

import pytest

import services.sms_service as sms_service
from infra import auth
from infra.auth import issue_sms_code, verify_sms_code
from infra.config import SMS_DAILY_CAP_PER_PHONE, SMS_MAX_VERIFY_ATTEMPTS
from infra.database import get_connection

PHONE = "13812345678"
AK_ID = "test-access-key-id"
AK_SECRET = "test-access-key-secret"
SIGN_NAME = "赠送签名"
TEMPLATE_CODE = "100001"
NONCE = "123e4567-e89b-12d3-a456-426614174000"
TIMESTAMP = "2026-01-01T00:00:00Z"


# ─── helpers / fixtures ────────────────────────────────────────


@pytest.fixture
def aliyun_credentials(monkeypatch):
    """Give services.sms_service a full set of fake aliyun credentials."""
    monkeypatch.setattr(sms_service, "ALIYUN_ACCESS_KEY_ID", AK_ID)
    monkeypatch.setattr(sms_service, "ALIYUN_ACCESS_KEY_SECRET", AK_SECRET)
    monkeypatch.setattr(sms_service, "ALIYUN_SMS_SIGN_NAME", SIGN_NAME)
    monkeypatch.setattr(sms_service, "ALIYUN_SMS_TEMPLATE_CODE", TEMPLATE_CODE)
    monkeypatch.setattr(sms_service, "ALIYUN_SMS_SCHEME_NAME", "")


class _FakeResponse:
    """Minimal stand-in for the object urlopen returns."""

    def __init__(self, payload: dict, status: int = 200):
        self._body = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _patch_urlopen(monkeypatch, responder):
    """Route urllib.request.urlopen to *responder*; return captured requests.

    The responder maps a Request to either a _FakeResponse or an Exception
    instance (which is then raised, mimicking urlopen's behavior).
    """
    calls: list[urllib.request.Request] = []

    def fake_urlopen(request, timeout=10, **kwargs):
        calls.append(request)
        result = responder(request)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


def _http_error(code: int, payload: dict) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://dypnsapi.aliyuncs.com",
        code,
        f"HTTP {code}",
        {},
        io.BytesIO(json.dumps(payload).encode("utf-8")),
    )


def _query_of(request: urllib.request.Request) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)


# ─── signature ─────────────────────────────────────────────────


def test_signature_matches_independent_hmac(aliyun_credentials):
    params = {
        "PhoneNumber": PHONE,
        "SignName": SIGN_NAME,
        "TemplateCode": TEMPLATE_CODE,
        "TemplateParam": '{"code":"##code##","min":"5"}',
    }
    query = sms_service._aliyun_signed_query(
        "SendSmsVerifyCode", params, nonce=NONCE, timestamp=TIMESTAMP
    )
    canonical, sep, signature = query.rpartition("&Signature=")
    assert sep == "&Signature="

    # Params in the canonical part must be sorted by key.
    keys = [pair.split("=", 1)[0] for pair in canonical.split("&")]
    assert keys == sorted(keys)

    # Recompute the signature from scratch: StringToSign is
    # "GET&%2F&" + RFC3986(canonical), keyed with secret + "&".
    string_to_sign = "GET&%2F&" + urllib.parse.quote(canonical, safe="~")
    expected = base64.b64encode(
        hmac.new(
            (AK_SECRET + "&").encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha1,
        ).digest()
    ).decode("ascii")
    assert urllib.parse.unquote(signature) == expected


def test_signed_query_contains_required_params(aliyun_credentials):
    params = {
        "PhoneNumber": PHONE,
        "SignName": SIGN_NAME,
        "TemplateCode": TEMPLATE_CODE,
    }
    query = sms_service._aliyun_signed_query(
        "SendSmsVerifyCode", params, nonce=NONCE, timestamp=TIMESTAMP
    )
    parsed = urllib.parse.parse_qs(query)
    assert parsed["Action"] == ["SendSmsVerifyCode"]
    assert parsed["Version"] == ["2017-05-25"]
    assert parsed["Format"] == ["JSON"]
    assert parsed["SignatureMethod"] == ["HMAC-SHA1"]
    assert parsed["SignatureVersion"] == ["1.0"]
    assert parsed["AccessKeyId"] == [AK_ID]
    assert parsed["Timestamp"] == [TIMESTAMP]
    assert parsed["SignatureNonce"] == [NONCE]
    assert parsed["PhoneNumber"] == [PHONE]
    assert parsed["SignName"] == [SIGN_NAME]
    assert parsed["TemplateCode"] == [TEMPLATE_CODE]
    assert "Signature" in parsed


# ─── _send_via_aliyun ──────────────────────────────────────────


def test_send_via_aliyun_success(aliyun_credentials, monkeypatch):
    calls = _patch_urlopen(
        monkeypatch,
        lambda req: _FakeResponse(
            {"Code": "OK", "Success": True, "Message": "OK", "Model": {"BizId": "1^1"}}
        ),
    )
    sms_service._send_via_aliyun(PHONE)
    assert len(calls) == 1
    request = calls[0]
    assert request.full_url.startswith("https://dypnsapi.aliyuncs.com?")
    assert request.get_method() == "GET"
    parsed = _query_of(request)
    assert parsed["Action"] == ["SendSmsVerifyCode"]
    assert parsed["PhoneNumber"] == [PHONE]
    assert parsed["SignName"] == [SIGN_NAME]
    assert parsed["TemplateCode"] == [TEMPLATE_CODE]
    # The code is generated Aliyun-side via the ##code## placeholder — no
    # plaintext code ever appears in the request.
    assert parsed["TemplateParam"] == ['{"code":"##code##","min":"5"}']
    assert "VerifyCode" not in parsed


def test_send_via_aliyun_business_failure_raises(aliyun_credentials, monkeypatch):
    _patch_urlopen(
        monkeypatch,
        lambda req: _FakeResponse(
            {"Code": "InvalidPhoneNumber", "Message": "The mobile number is illegal."}
        ),
    )
    with pytest.raises(RuntimeError, match="The mobile number is illegal."):
        sms_service._send_via_aliyun(PHONE)


def test_send_via_aliyun_http_error_raises(aliyun_credentials, monkeypatch):
    _patch_urlopen(
        monkeypatch,
        lambda req: _http_error(
            403, {"Code": "SignatureDoesNotMatch", "Message": "signature mismatch"}
        ),
    )
    with pytest.raises(RuntimeError, match=r"HTTP 403.*signature mismatch"):
        sms_service._send_via_aliyun(PHONE)


def test_send_via_aliyun_network_error_raises(aliyun_credentials, monkeypatch):
    _patch_urlopen(monkeypatch, lambda req: urllib.error.URLError("timed out"))
    with pytest.raises(RuntimeError, match="SendSmsVerifyCode failed"):
        sms_service._send_via_aliyun(PHONE)


@pytest.mark.parametrize(
    "missing",
    ["ALIYUN_ACCESS_KEY_ID", "ALIYUN_ACCESS_KEY_SECRET", "ALIYUN_SMS_SIGN_NAME", "ALIYUN_SMS_TEMPLATE_CODE"],
)
def test_send_via_aliyun_missing_credential_raises(aliyun_credentials, monkeypatch, missing):
    monkeypatch.setattr(sms_service, missing, "")
    with pytest.raises(RuntimeError, match="Secrets") as excinfo:
        sms_service._send_via_aliyun(PHONE)
    assert missing in str(excinfo.value)


# ─── send_verification_code dispatch ───────────────────────────


def test_dispatch_aliyun_ignores_code_arg(aliyun_credentials, monkeypatch):
    monkeypatch.setattr(sms_service, "SMS_PROVIDER", "aliyun")
    calls = _patch_urlopen(
        monkeypatch,
        lambda req: _FakeResponse({"Code": "OK", "Success": True, "Model": {}}),
    )
    sms_service.send_verification_code(PHONE, "123456")
    assert len(calls) == 1
    parsed = _query_of(calls[0])
    assert parsed["Action"] == ["SendSmsVerifyCode"]
    # The local code argument is ignored: Aliyun generates the code, so the
    # request must carry neither VerifyCode nor the plaintext code value.
    assert "VerifyCode" not in parsed
    assert "123456" not in {v for values in parsed.values() for v in values}


def test_dispatch_aliyun_missing_credentials_points_at_secrets(monkeypatch):
    monkeypatch.setattr(sms_service, "SMS_PROVIDER", "aliyun")
    monkeypatch.setattr(sms_service, "ALIYUN_ACCESS_KEY_ID", "")
    monkeypatch.setattr(sms_service, "ALIYUN_ACCESS_KEY_SECRET", "")
    monkeypatch.setattr(sms_service, "ALIYUN_SMS_SIGN_NAME", "")
    monkeypatch.setattr(sms_service, "ALIYUN_SMS_TEMPLATE_CODE", "")
    with pytest.raises(RuntimeError, match="Secrets") as excinfo:
        sms_service.send_verification_code(PHONE, "123456")
    message = str(excinfo.value)
    assert "ALIYUN_ACCESS_KEY_ID" in message
    assert "ALIYUN_SMS_TEMPLATE_CODE" in message


def test_dispatch_demo_and_twilio_unchanged(monkeypatch):
    """demo still receives the code; twilio still routes to the twilio sender."""
    monkeypatch.setattr(sms_service, "SMS_PROVIDER", "demo")
    seen = []
    monkeypatch.setattr(sms_service, "_send_via_demo", lambda phone, code: seen.append((phone, code)))
    sms_service.send_verification_code(PHONE, "123456")
    assert seen == [(PHONE, "123456")]

    monkeypatch.setattr(sms_service, "SMS_PROVIDER", "twilio")
    seen_twilio = []
    monkeypatch.setattr(
        sms_service, "_send_via_twilio", lambda phone, code: seen_twilio.append((phone, code))
    )
    sms_service.send_verification_code(PHONE, "123456")
    assert seen_twilio == [(PHONE, "123456")]


# ─── check_code_via_aliyun ─────────────────────────────────────


def test_check_code_pass_returns_true(aliyun_credentials, monkeypatch):
    calls = _patch_urlopen(
        monkeypatch,
        lambda req: _FakeResponse(
            {"Code": "OK", "Success": True, "Model": {"VerifyResult": "PASS"}}
        ),
    )
    assert sms_service.check_code_via_aliyun(PHONE, "654321") is True
    parsed = _query_of(calls[0])
    assert parsed["Action"] == ["CheckSmsVerifyCode"]
    assert parsed["PhoneNumber"] == [PHONE]
    assert parsed["VerifyCode"] == ["654321"]


def test_check_code_unknown_returns_false(aliyun_credentials, monkeypatch):
    _patch_urlopen(
        monkeypatch,
        lambda req: _FakeResponse(
            {"Code": "OK", "Success": True, "Model": {"VerifyResult": "UNKNOWN"}}
        ),
    )
    assert sms_service.check_code_via_aliyun(PHONE, "000000") is False


def test_check_code_http_error_raises(aliyun_credentials, monkeypatch):
    _patch_urlopen(
        monkeypatch,
        lambda req: _http_error(400, {"Code": "INVALID_PARAMETERS", "Message": "bad param"}),
    )
    with pytest.raises(RuntimeError, match="bad param"):
        sms_service.check_code_via_aliyun(PHONE, "654321")


def test_check_code_business_error_raises_not_false(aliyun_credentials, monkeypatch):
    """A failed CheckSmsVerifyCode *call* is a service error, not a wrong code."""
    _patch_urlopen(
        monkeypatch,
        lambda req: _FakeResponse({"Code": "isv.BUSINESS_LIMIT_CONTROL", "Message": "limited"}),
    )
    with pytest.raises(RuntimeError, match="limited"):
        sms_service.check_code_via_aliyun(PHONE, "654321")


def test_check_code_missing_credentials_raises(monkeypatch):
    monkeypatch.setattr(sms_service, "ALIYUN_ACCESS_KEY_ID", "")
    monkeypatch.setattr(sms_service, "ALIYUN_ACCESS_KEY_SECRET", "")
    with pytest.raises(RuntimeError, match="Secrets"):
        sms_service.check_code_via_aliyun(PHONE, "654321")


# ─── infra.auth delegated issue / verify ───────────────────────


@pytest.fixture
def aliyun_auth(monkeypatch):
    """Run infra.auth against the aliyun provider with in-memory send/check."""
    sent: list[tuple[str, str]] = []
    state = SimpleNamespace(passes=True, check_calls=[])

    def _check(phone, code):
        state.check_calls.append((phone, code))
        if isinstance(state.passes, Exception):
            raise state.passes
        return state.passes

    monkeypatch.setattr(auth, "SMS_PROVIDER", "aliyun")
    monkeypatch.setattr(auth, "send_verification_code", lambda phone, code: sent.append((phone, code)))
    monkeypatch.setattr(auth, "check_code_via_aliyun", _check)
    state.sent = sent
    return state


def _sms_code_row(phone: str):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT code_hash, expires_at, attempts FROM sms_codes WHERE phone = ?",
            (phone,),
        ).fetchone()
    finally:
        conn.close()


def test_aliyun_issue_writes_delegated_row(aliyun_auth):
    assert issue_sms_code(PHONE) == (True, "ok")
    # No local code is generated; the sender gets an empty code string.
    assert aliyun_auth.sent == [(PHONE, "")]
    row = _sms_code_row(PHONE)
    assert row is not None
    assert row["code_hash"] == "delegated:aliyun"
    assert row["attempts"] == 0
    assert int(row["expires_at"]) > int(time.time())


def test_aliyun_verify_pass_consumes_row(aliyun_auth):
    issue_sms_code(PHONE)
    assert verify_sms_code(PHONE, "654321") is True
    assert aliyun_auth.check_calls == [(PHONE, "654321")]
    assert _sms_code_row(PHONE) is None
    # The code was single-use: a second verify has no row to check against.
    assert verify_sms_code(PHONE, "654321") is False
    assert len(aliyun_auth.check_calls) == 1


def test_aliyun_verify_miss_spends_attempts_then_locks(aliyun_auth):
    issue_sms_code(PHONE)
    aliyun_auth.passes = False
    for _ in range(SMS_MAX_VERIFY_ATTEMPTS):
        assert verify_sms_code(PHONE, "000000") is False
    assert _sms_code_row(PHONE)["attempts"] == SMS_MAX_VERIFY_ATTEMPTS
    # Attempt budget spent: even a passing check is rejected without a call.
    aliyun_auth.passes = True
    calls_before = len(aliyun_auth.check_calls)
    assert verify_sms_code(PHONE, "654321") is False
    assert len(aliyun_auth.check_calls) == calls_before


def test_aliyun_verify_service_error_propagates(aliyun_auth):
    issue_sms_code(PHONE)
    aliyun_auth.passes = RuntimeError("aliyun unreachable")
    with pytest.raises(RuntimeError, match="aliyun unreachable"):
        verify_sms_code(PHONE, "654321")
    # The failed call did not consume the row or spend an attempt.
    row = _sms_code_row(PHONE)
    assert row is not None and row["attempts"] == 0


def test_aliyun_expired_delegated_row_is_rejected_without_check(aliyun_auth):
    issue_sms_code(PHONE)
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE sms_codes SET expires_at = ? WHERE phone = ?",
            (int(time.time()) - 1, PHONE),
        )
        conn.commit()
    finally:
        conn.close()
    assert verify_sms_code(PHONE, "654321") is False
    assert aliyun_auth.check_calls == []


def test_aliyun_resend_cooldown_blocks_second_issue(aliyun_auth):
    assert issue_sms_code(PHONE) == (True, "ok")
    assert issue_sms_code(PHONE) == (False, "cooldown")
    assert len(aliyun_auth.sent) == 1


def test_aliyun_daily_cap_blocks_issue(aliyun_auth):
    now = int(time.time())
    conn = get_connection()
    try:
        for _ in range(SMS_DAILY_CAP_PER_PHONE):
            conn.execute("INSERT INTO sms_send_log (phone, sent_at) VALUES (?, ?)", (PHONE, now))
        conn.commit()
    finally:
        conn.close()
    assert issue_sms_code(PHONE) == (False, "daily_cap")
    assert aliyun_auth.sent == []


def test_aliyun_failed_send_rolls_back_state(aliyun_auth, monkeypatch):
    def _boom(phone, code):
        raise RuntimeError("provider down")

    monkeypatch.setattr(auth, "send_verification_code", _boom)
    assert issue_sms_code(PHONE) == (False, "send_failed")
    assert _sms_code_row(PHONE) is None
    conn = get_connection()
    try:
        assert (
            conn.execute("SELECT COUNT(*) AS c FROM sms_send_log WHERE phone = ?", (PHONE,)).fetchone()["c"]
            == 0
        )
    finally:
        conn.close()
    # No cooldown was armed, so a retry with a healthy provider succeeds.
    monkeypatch.setattr(
        auth, "send_verification_code", lambda phone, code: aliyun_auth.sent.append((phone, code))
    )
    assert issue_sms_code(PHONE) == (True, "ok")
    assert _sms_code_row(PHONE)["code_hash"] == "delegated:aliyun"

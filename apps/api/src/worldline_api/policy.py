from __future__ import annotations

import re

ALLOWED_ACCESS_MODES = {
    "test_fixture",
    "public_web",
    "official_api",
    "authorized_export",
    "manual_upload",
    "third_party_contract",
}

BLOCKED_ACCESS_MODES = {
    "private_or_bypassed",
    "cookie_pool",
    "captcha_bypass",
    "private_chat",
    "unknown",
}

SENSITIVE_PATTERNS = [
    re.compile(r"minor name:?\s*[A-Za-z\u4e00-\u9fff]{1,12}", re.IGNORECASE),
    re.compile(r"class\s*\d+[-\w]*", re.IGNORECASE),
    re.compile(r"\b1[3-9]\d{9}\b"),
    re.compile(r"\b\d{17}[\dXx]\b"),
]


def source_allowed(access_mode: str, status: str) -> tuple[bool, str | None]:
    if status != "active":
        return False, "source_inactive"
    if access_mode in BLOCKED_ACCESS_MODES:
        return False, "source_not_allowed_for_p0"
    if access_mode not in ALLOWED_ACCESS_MODES:
        return False, "source_not_allowed_for_p0"
    return True, None


def mask_sensitive_text(text: str) -> str:
    masked = text
    for pattern in SENSITIVE_PATTERNS:
        masked = pattern.sub("[MASKED]", masked)
    return masked


def sensitivity_level(text: str, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    return "sensitive_person_minor" if mask_sensitive_text(text) != text else "normal"


ALLOWED_ACCESS_MODES = {
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


def is_source_allowed(source):
    """Return whether a source can be collected in P0."""
    mode = source.get("access_mode", "unknown")
    status = source.get("status", "inactive")
    if status != "active":
        return False
    if mode in BLOCKED_ACCESS_MODES:
        return False
    return mode in ALLOWED_ACCESS_MODES

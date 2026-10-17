"""API-key storage.

Keys are kept in the operating system credential store (Windows Credential
Manager / macOS Keychain) when possible.  ``SUBLOOM_API_KEY`` always wins,
which is convenient for CI and power users.  Keys are never written to the
JSON config or the repository.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

SERVICE = "SubLoom"
ACCOUNT = "translation-api"
ENV_KEY = "SUBLOOM_API_KEY"


def get_api_key() -> str:
    env = os.environ.get(ENV_KEY, "").strip()
    if env:
        return env
    try:
        import keyring

        return (keyring.get_password(SERVICE, ACCOUNT) or "").strip()
    except Exception as exc:  # keyring backends can be missing/broken
        log.debug("Keyring read failed: %s", exc)
        return ""


def set_api_key(value: str) -> tuple[bool, str]:
    value = value.strip()
    try:
        import keyring

        if value:
            keyring.set_password(SERVICE, ACCOUNT, value)
        else:
            try:
                keyring.delete_password(SERVICE, ACCOUNT)
            except keyring.errors.PasswordDeleteError:
                pass
        return True, ""
    except Exception as exc:
        log.warning("Keyring write failed: %s", exc)
        return False, str(exc)


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "•" * len(key)
    return f"{key[:4]}{'•' * 8}{key[-4:]}"


def has_api_key() -> bool:
    return bool(get_api_key())

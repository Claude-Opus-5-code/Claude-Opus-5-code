"""Device fingerprint and request headers.

Migrated from source L100-125.

CLASSIFICATION NOTE (README §17 zero-dropped-logic):
`generate_fake_ip` and the three IP headers (`X-Forwarded-For`, `X-Real-IP`,
`Client-IP`) are QUARANTINED behavior: they are preserved exactly as the source
wrote them and remain enabled by default, but they are isolated in this one
module behind a single flag so an operator can disable them without touching
any other migrated logic.

Live differential evidence (workspace/working/overchat/CAPABILITY_INVENTORY.md,
"IP header finding") shows guest admission succeeded WITHOUT these headers and
that later 502s occurred with and without them, so no server-side effect is
established. That evidence does NOT authorize removing them, so the default is
unchanged from the source.
"""

from __future__ import annotations

import random
import string

#: Alphabet for the device uuid, source L107.
DEVICE_UUID_ALPHABET = string.ascii_lowercase + string.digits

#: Length of the device uuid, source L107 (k=16).
DEVICE_UUID_LENGTH = 16

#: The three IP-masking headers, source L113-115.
IP_SPOOF_HEADER_NAMES = ("X-Forwarded-For", "X-Real-IP", "Client-IP")


def generate_fake_ip() -> str:
    """Generate a masking IP address.

    Source L100-102, identical::

        f"{random.randint(1,255)}.{random.randint(1,255)}."
        f"{random.randint(1,255)}.{random.randint(1,255)}"

    Note the range is 1..255 inclusive: octet 0 never occurs and 255 does. This
    is preserved verbatim rather than "corrected" to a valid-IP generator.
    """
    return (
        f"{random.randint(1, 255)}.{random.randint(1, 255)}."
        f"{random.randint(1, 255)}.{random.randint(1, 255)}"
    )


def generate_device_uuid() -> str:
    """Generate the 16-char device fingerprint (source L107)."""
    return "".join(random.choices(DEVICE_UUID_ALPHABET, k=DEVICE_UUID_LENGTH))


def build_mobile_headers(
    *,
    include_ip_spoof_headers: bool = True,
) -> tuple[dict[str, str], str, str]:
    """Build the Android/OkHttp base headers.

    Source L104-125. Returns the same 3-tuple as the source:
    ``(headers, device_uuid, fake_ip)``.

    The header set, values, and insertion order are identical to the source.
    `include_ip_spoof_headers` defaults to True, which reproduces source
    behavior exactly; when False the three quarantined IP headers are omitted
    and everything else is unchanged.

    A fresh uuid and IP are minted on every call, because the source calls this
    per request (source L191) - each request therefore presents a new device.
    """
    fake_ip = generate_fake_ip()
    random_device_uuid = generate_device_uuid()

    headers: dict[str, str] = {
        "User-Agent": "okhttp/4.12.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip",
    }

    if include_ip_spoof_headers:
        headers["X-Forwarded-For"] = fake_ip
        headers["X-Real-IP"] = fake_ip
        headers["Client-IP"] = fake_ip

    headers.update(
        {
            "x-device-platform": "android",
            "x-device-version": "12",
            "x-device-brand": "samsung",
            "x-device-id": "exynos9611",
            "x-device-uuid": random_device_uuid,
            "x-app-build-number": "80",
            "x-app-version": "1.0",
            "x-app-default-lang": "ar",
        }
    )

    return headers, random_device_uuid, fake_ip

"""Device fingerprint / header parity (source L100-125).

The header set is what makes this provider work at all: upstream auto-provisions
a guest identity from the `x-device-*` headers. So the exact names, values and
count are contractual.
"""

from __future__ import annotations

import random
import string

from overchat.runtime.headers import (
    DEVICE_UUID_ALPHABET,
    DEVICE_UUID_LENGTH,
    IP_SPOOF_HEADER_NAMES,
    build_mobile_headers,
    generate_device_uuid,
    generate_fake_ip,
)

#: Transcribed from source L109-124 — the full expected header set.
SOURCE_HEADERS = {
    "User-Agent": "okhttp/4.12.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip",
    "x-device-platform": "android",
    "x-device-version": "12",
    "x-device-brand": "samsung",
    "x-device-id": "exynos9611",
    "x-app-build-number": "80",
    "x-app-version": "1.0",
    "x-app-default-lang": "ar",
}


def test_header_set_is_exactly_fourteen_keys() -> None:
    """Source L109-124 defines exactly 14 headers."""
    headers, _uuid, _ip = build_mobile_headers()
    assert len(headers) == 14


def test_all_fixed_header_values_match_source() -> None:
    headers, _uuid, _ip = build_mobile_headers()
    for name, value in SOURCE_HEADERS.items():
        assert headers[name] == value, name


def test_returns_source_three_tuple_consistent_with_headers() -> None:
    """Source L125 returns `(headers, random_device_uuid, fake_ip)`; the returned
    values must be the ones actually placed in the headers."""
    headers, device_uuid, fake_ip = build_mobile_headers()
    assert headers["x-device-uuid"] == device_uuid
    assert headers["X-Forwarded-For"] == fake_ip


def test_same_fake_ip_is_reused_across_all_three_ip_headers() -> None:
    """Source L113-115 assigns the SAME `fake_ip` to all three."""
    headers, _uuid, fake_ip = build_mobile_headers()
    assert (
        headers["X-Forwarded-For"] == headers["X-Real-IP"] == headers["Client-IP"] == fake_ip
    )


def test_device_uuid_length_and_alphabet() -> None:
    """Source L107: k=16 from ascii_lowercase + digits (no uppercase)."""
    assert DEVICE_UUID_LENGTH == 16
    assert DEVICE_UUID_ALPHABET == string.ascii_lowercase + string.digits
    for _ in range(50):
        value = generate_device_uuid()
        assert len(value) == 16
        assert set(value) <= set(string.ascii_lowercase + string.digits)
        assert not any(c.isupper() for c in value)


def test_identity_is_fresh_on_every_call() -> None:
    """Source calls build_mobile_headers() per request (L191), so each request
    presents a NEW device. Collisions across 20 draws would indicate caching."""
    uuids = {build_mobile_headers()[1] for _ in range(20)}
    assert len(uuids) == 20


def test_fake_ip_octets_use_source_range_1_to_255() -> None:
    """Source L102 uses randint(1,255): octet 0 NEVER occurs, 255 CAN.

    This is preserved verbatim rather than 'fixed' to a valid-IP generator.
    """
    seen: set[int] = set()
    for _ in range(2000):
        octets = [int(p) for p in generate_fake_ip().split(".")]
        assert len(octets) == 4
        assert all(1 <= o <= 255 for o in octets)
        seen.update(octets)
    assert 0 not in seen
    # With 8000 draws from 1..255, hitting the boundary values is near-certain;
    # this proves the range is inclusive rather than 1..254.
    assert 255 in seen
    assert 1 in seen


def test_fake_ip_is_deterministic_under_seeded_random() -> None:
    """Proves generation goes through `random` exactly as the source does, i.e.
    four sequential randint(1,255) draws in one order."""
    random.seed(12345)
    expected = ".".join(str(random.randint(1, 255)) for _ in range(4))
    random.seed(12345)
    assert generate_fake_ip() == expected


def test_quarantined_ip_headers_can_be_disabled_without_touching_the_rest() -> None:
    """Quarantine boundary: with the flag off, exactly the 3 IP headers vanish
    and all 11 remaining headers are unchanged."""
    headers, _uuid, _ip = build_mobile_headers(include_ip_spoof_headers=False)
    assert len(headers) == 11
    for name in IP_SPOOF_HEADER_NAMES:
        assert name not in headers
    for name, value in SOURCE_HEADERS.items():
        assert headers[name] == value
    assert len(headers["x-device-uuid"]) == 16


def test_ip_spoof_header_names_are_the_source_three() -> None:
    assert IP_SPOOF_HEADER_NAMES == ("X-Forwarded-For", "X-Real-IP", "Client-IP")

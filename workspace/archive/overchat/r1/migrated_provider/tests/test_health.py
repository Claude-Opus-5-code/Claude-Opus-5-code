"""Health check tests.

CLASSIFICATION: SANITIZED (adapter-added). The source has NO health check; V3
§4.1/§11 require one. The critical property proven here is that health invents
NO new upstream behavior: it reuses only the read-only `GET /v1/auth/me` that is
already step 2 of every generation request.
"""

from __future__ import annotations

from overchat.config import OverchatConfig
from overchat.health import DEGRADED, HEALTHY, UNAVAILABLE, check_health

from .conftest import FakeResponse, RecordingTransport, make_transport


def _transport(response: FakeResponse) -> RecordingTransport:
    return RecordingTransport(handler=lambda method, url: response)


def test_health_probe_contacts_only_the_existing_auth_endpoint() -> None:
    """No new endpoint may be invented (README §16)."""
    transport = _transport(FakeResponse(200, payload={"id": "g"}))
    check_health(transport)

    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call.method == "GET"
    assert call.url == "https://api.overchat.ai/v1/auth/me"


def test_health_probe_is_read_only() -> None:
    """Health must never create a chat or send a generation request."""
    transport = _transport(FakeResponse(200, payload={"id": "g"}))
    check_health(transport)

    assert [c.method for c in transport.calls] == ["GET"]
    assert all("/v2/chat/responses" not in c.url for c in transport.calls)
    assert all(c.body is None for c in transport.calls)


def test_successful_auth_is_healthy() -> None:
    report = check_health(_transport(FakeResponse(200, payload={"id": "g"})))
    assert report.status == HEALTHY
    assert report.error is None
    assert report.provider_id == "overchat"


def test_201_is_also_healthy() -> None:
    report = check_health(_transport(FakeResponse(201, payload={"id": "g"})))
    assert report.status == HEALTHY


def test_rate_limited_is_degraded_not_unavailable() -> None:
    """429 means the provider is UP but throttling (V3 §11)."""
    report = check_health(_transport(FakeResponse(429, text="slow down")))
    assert report.status == DEGRADED
    assert report.error is not None
    assert report.error.category == "rate_limited"


def test_502_is_unavailable() -> None:
    """502 is the status actually observed live against api.overchat.ai."""
    report = check_health(_transport(FakeResponse(502, text="Bad Gateway")))
    assert report.status == UNAVAILABLE


def test_network_failure_is_unavailable() -> None:
    transport = RecordingTransport(raise_on={"/v1/auth/me": ConnectionError("dns")})
    report = check_health(transport)
    assert report.status == UNAVAILABLE


def test_client_error_is_degraded_because_provider_is_reachable() -> None:
    report = check_health(_transport(FakeResponse(400, text="bad")))
    assert report.status == DEGRADED


def test_health_message_never_contains_raw_body() -> None:
    report = check_health(_transport(FakeResponse(500, text="secret-internal-trace")))
    assert report.message is not None
    assert "secret-internal-trace" not in report.message


def test_to_dict_excludes_the_error_object() -> None:
    """The serialized health view is safe for logs/API: no provider internals."""
    payload = check_health(_transport(FakeResponse(500, text="trace"))).to_dict()
    assert set(payload) == {"provider_id", "status", "message"}
    assert "trace" not in str(payload)


def test_health_status_values_match_v3_health_enum() -> None:
    """Supplemental cross-check against Core's enum when importable."""
    import pytest

    contracts = pytest.importorskip(
        "core.contracts.providers", reason="Core not on sys.path (standalone mode)"
    )
    valid = {s.value for s in contracts.ProviderHealthStatus}
    assert {HEALTHY, DEGRADED, UNAVAILABLE} <= valid


def test_health_honors_ip_spoof_header_switch() -> None:
    transport = make_transport(gen_lines=[])
    check_health(transport, OverchatConfig().with_values(include_ip_spoof_headers=False))
    assert "X-Forwarded-For" not in transport.calls[0].headers


def test_health_uses_configured_base_url() -> None:
    transport = _transport(FakeResponse(200, payload={"id": "g"}))
    check_health(transport, OverchatConfig().with_values(base_url="https://example.test"))
    assert transport.calls[0].url == "https://example.test/v1/auth/me"

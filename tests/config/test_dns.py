from __future__ import annotations

import pytest

from config.dns import DnsResolutionError, resolve_endpoint


def test_primary_dns_resolution_does_not_use_fallback() -> None:
    calls: list[tuple[str, int]] = []

    def resolver(host: str, port: int):
        calls.append((host, port))
        return [(None, None, None, None, ("192.0.2.10", port))]

    result = resolve_endpoint("esp32-boutons.home.arpa", port=80, fallback="192.0.2.10", allow_fallback=True, resolver=resolver)
    assert result.selected_host == "esp32-boutons.home.arpa"
    assert result.used_fallback is False
    assert calls == [("esp32-boutons.home.arpa", 80)]


def test_dns_failure_never_falls_back_silently() -> None:
    def resolver(host: str, port: int):
        raise TimeoutError("simulated timeout")

    with pytest.raises(DnsResolutionError, match="résolution indisponible"):
        resolve_endpoint("esp32-boutons.home.arpa", port=80, fallback="192.0.2.10", resolver=resolver)


def test_explicit_fallback_is_reported() -> None:
    def resolver(host: str, port: int):
        raise OSError("simulated DNS absence")

    result = resolve_endpoint("esp32-boutons.home.arpa", port=80, fallback="192.0.2.10", allow_fallback=True, resolver=resolver)
    assert result.selected_host == "192.0.2.10"
    assert result.used_fallback is True


@pytest.mark.parametrize("name", ["http://esp32-boutons.home.arpa", "192.0.2.10", "bad name"])
def test_primary_endpoint_must_be_a_dns_name(name: str) -> None:
    with pytest.raises(DnsResolutionError, match="DNS"):
        resolve_endpoint(name, port=80, resolver=lambda *_: [])

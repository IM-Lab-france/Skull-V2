"""Explicit, injectable endpoint resolution for internal service names."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re
import socket
from collections.abc import Callable, Sequence

from .schema import ConfigurationError


_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
Resolver = Callable[[str, int], Sequence[object]]


class DnsResolutionError(ConfigurationError):
    """A bounded DNS failure without echoing resolver details."""


@dataclass(frozen=True)
class EndpointResolution:
    configured_name: str
    selected_host: str
    used_fallback: bool = False


def _valid_host(value: str, field: str, *, allow_ip: bool) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DnsResolutionError(f"DNS: {field}: valeur absente")
    host = value.strip().rstrip(".").lower()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if any(not part or not _LABEL.fullmatch(part) for part in host.split(".")):
            raise DnsResolutionError(f"DNS: {field}: nom ou adresse invalide")
    else:
        if not allow_ip:
            raise DnsResolutionError(f"DNS: {field}: nom DNS requis")
    return host


def resolve_endpoint(
    name: str,
    *,
    port: int,
    fallback: str = "",
    allow_fallback: bool = False,
    resolver: Resolver | None = None,
) -> EndpointResolution:
    """Resolve a primary DNS name; use fallback only when explicitly enabled."""
    primary = _valid_host(name, "name", allow_ip=False)
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise DnsResolutionError("DNS: port: hors plage")
    lookup = resolver or (lambda host, service: socket.getaddrinfo(host, service, type=socket.SOCK_STREAM))
    try:
        answers = lookup(primary, port)
        if not answers:
            raise OSError("empty resolution")
        return EndpointResolution(primary, primary, False)
    except (OSError, TimeoutError, socket.gaierror) as exc:
        if not allow_fallback or not fallback:
            raise DnsResolutionError("DNS: résolution indisponible") from exc
        selected = _valid_host(fallback, "fallback", allow_ip=True)
        return EndpointResolution(primary, selected, True)


__all__ = ["DnsResolutionError", "EndpointResolution", "resolve_endpoint"]

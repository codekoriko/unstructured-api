"""Secure fetch and outbound URL validation for async partition requests."""

from __future__ import annotations

import ipaddress
import os
import socket
from typing import Any, Optional
from urllib.parse import urlparse

import requests
import urllib3

BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
    }
)

DEFAULT_OUTBOUND_HOST_SUFFIXES = ".supabase.co"
DEFAULT_MAX_BYTES = 500 * 1024 * 1024
DEFAULT_FETCH_TIMEOUT_SECONDS = 300
DEFAULT_OUTBOUND_TIMEOUT_SECONDS = 300

OUTBOUND_ALLOWED_SUFFIXES_ENV = "OUTBOUND_URL_ALLOWED_HOST_SUFFIXES"
OUTBOUND_ALLOWED_HOSTS_ENV = "OUTBOUND_URL_ALLOWED_HOSTS"
OUTBOUND_ALLOW_HTTP_ENV = "OUTBOUND_URL_ALLOW_HTTP"


class SourceUrlValidationError(ValueError):
    """Raised when an outbound async URL fails security validation."""


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def _parse_csv_env(name: str) -> frozenset[str]:
    raw = os.environ.get(name, "")
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())


def _parse_suffix_env(name: str, default: str) -> frozenset[str]:
    raw = os.environ.get(name, default)
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())


def _http_allowed() -> bool:
    return _truthy_env(OUTBOUND_ALLOW_HTTP_ENV) or _truthy_env("SOURCE_URL_ALLOW_HTTP")


def _max_bytes() -> int:
    return int(os.environ.get("SOURCE_URL_MAX_BYTES", str(DEFAULT_MAX_BYTES)))


def _fetch_timeout_seconds() -> int:
    return int(os.environ.get("SOURCE_URL_FETCH_TIMEOUT_SECONDS", str(DEFAULT_FETCH_TIMEOUT_SECONDS)))


def _outbound_timeout_seconds() -> int:
    return int(os.environ.get("OUTBOUND_URL_TIMEOUT_SECONDS", str(DEFAULT_OUTBOUND_TIMEOUT_SECONDS)))


def _allowed_hosts() -> frozenset[str]:
    return _parse_csv_env(OUTBOUND_ALLOWED_HOSTS_ENV)


def _allowed_suffixes() -> frozenset[str]:
    suffixes = _parse_csv_env(OUTBOUND_ALLOWED_SUFFIXES_ENV)
    if suffixes:
        return suffixes
    return _parse_suffix_env(OUTBOUND_ALLOWED_SUFFIXES_ENV, DEFAULT_OUTBOUND_HOST_SUFFIXES)


def _strip_mime_parameters(content_type: str | None) -> str | None:
    if not content_type:
        return content_type
    return content_type.split(";", 1)[0].strip()


def _hostname_matches_suffix(host: str, suffix: str) -> bool:
    """True when host equals suffix or is a proper subdomain (dot-boundary match)."""
    normalized_suffix = suffix.lower().lstrip(".")
    if not normalized_suffix:
        return False
    normalized_host = host.lower().rstrip(".")
    if normalized_host == normalized_suffix:
        return True
    return normalized_host.endswith(f".{normalized_suffix}")


def _ip_is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip == ipaddress.ip_address("169.254.169.254")
    )


def _hostname_is_allowed(
    hostname: str,
    *,
    allowed_hosts: frozenset[str],
    allowed_suffixes: frozenset[str],
) -> bool:
    host = hostname.lower().rstrip(".")
    if host in allowed_hosts:
        return True
    if host in BLOCKED_HOSTNAMES:
        return False
    return any(_hostname_matches_suffix(host, suffix) for suffix in allowed_suffixes)


def _first_allowed_ip(hostname: str) -> str:
    try:
        addrinfo = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SourceUrlValidationError(f"Cannot resolve URL host: {hostname}") from exc

    for _, _, _, _, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _ip_is_blocked(ip):
            raise SourceUrlValidationError(f"URL resolves to blocked address: {ip_str}")
        return ip_str

    raise SourceUrlValidationError(f"Cannot resolve URL host: {hostname}")


def _check_resolved_ips(hostname: str) -> None:
    _first_allowed_ip(hostname)


def _validate_outbound_url(
    url: str,
    *,
    url_label: str,
    allowed_hosts: frozenset[str],
    allowed_suffixes: frozenset[str],
    resolve_dns: bool,
) -> str:
    cleaned = url.strip()
    if not cleaned:
        raise SourceUrlValidationError(f"{url_label} is empty")

    parsed = urlparse(cleaned)
    scheme = (parsed.scheme or "").lower()
    if scheme == "https":
        pass
    elif scheme == "http" and _http_allowed():
        pass
    else:
        raise SourceUrlValidationError(f"{url_label} must use https")

    hostname = parsed.hostname
    if not hostname:
        raise SourceUrlValidationError(f"{url_label} is missing a host")

    if parsed.username or parsed.password:
        raise SourceUrlValidationError(f"{url_label} must not contain embedded credentials")

    if not allowed_hosts and not allowed_suffixes:
        raise SourceUrlValidationError(
            f"{url_label} host is not allowed (no outbound allowlist configured)",
        )

    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        if not _hostname_is_allowed(
            hostname,
            allowed_hosts=allowed_hosts,
            allowed_suffixes=allowed_suffixes,
        ):
            raise SourceUrlValidationError(f"{url_label} host is not allowed")
        if resolve_dns:
            _check_resolved_ips(hostname)
    else:
        explicitly_allowed = hostname.lower() in allowed_hosts
        if _ip_is_blocked(ip) and not explicitly_allowed:
            raise SourceUrlValidationError(f"{url_label} host IP is not allowed")
        if not _hostname_is_allowed(
            hostname,
            allowed_hosts=allowed_hosts,
            allowed_suffixes=allowed_suffixes,
        ):
            raise SourceUrlValidationError(f"{url_label} host is not allowed")

    return cleaned


def _validate_role_url(url: str, *, url_label: str) -> str:
    return _validate_outbound_url(
        url,
        url_label=url_label,
        allowed_hosts=_allowed_hosts(),
        allowed_suffixes=_allowed_suffixes(),
        resolve_dns=True,
    )


def validate_source_url(url: str) -> str:
    """Validate a signed download URL before the worker fetches the input file."""
    return _validate_role_url(url, url_label="source_url")


def validate_destination_url(url: str) -> str:
    """Validate the signed upload URL where extraction JSON is written."""
    return _validate_role_url(url, url_label="destination_url")


def validate_callback_url(url: str) -> str:
    """Validate the orchestrator webhook URL resumed after async extraction."""
    return _validate_role_url(url, url_label="callback_url")


def validate_source_filename(filename: str | None) -> str:
    """Return a basename-only filename for source_url requests."""
    if filename is None or not filename.strip():
        raise SourceUrlValidationError("source_filename is required when source_url is provided")

    stripped = filename.strip()
    if ".." in stripped or "/" in stripped or "\\" in stripped:
        raise SourceUrlValidationError("source_filename must be a basename")

    basename = os.path.basename(stripped)
    if not basename or basename in {".", ".."}:
        raise SourceUrlValidationError("source_filename is invalid")

    return basename


def _request_path_and_query(parsed) -> str:
    path = parsed.path or "/"
    if parsed.query:
        return f"{path}?{parsed.query}"
    return path


def _pinned_pool(parsed, pinned_ip: str, timeout_seconds: int):
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    timeout = urllib3.Timeout(connect=timeout_seconds, read=timeout_seconds)
    if parsed.scheme == "https":
        return urllib3.HTTPSConnectionPool(
            pinned_ip,
            port=port,
            server_hostname=parsed.hostname,
            timeout=timeout,
        )
    return urllib3.HTTPConnectionPool(pinned_ip, port=port, timeout=timeout)


def outbound_request(
    method: str,
    url: str,
    *,
    url_label: str,
    timeout_seconds: int | None = None,
    **kwargs: Any,
) -> requests.Response:
    """Issue an allowlisted outbound HTTP request without following redirects."""
    validated_url = _validate_role_url(url, url_label=url_label)
    timeout = timeout_seconds if timeout_seconds is not None else _outbound_timeout_seconds()
    return requests.request(
        method,
        validated_url,
        timeout=timeout,
        allow_redirects=False,
        **kwargs,
    )


def fetch_source_file(url: str) -> tuple[bytes, Optional[str]]:
    """Download a validated source file with DNS pinning, size limits, and no redirects."""
    validated_url = validate_source_url(url)
    max_bytes = _max_bytes()
    timeout = _fetch_timeout_seconds()
    parsed = urlparse(validated_url)
    hostname = parsed.hostname
    if not hostname:
        raise SourceUrlValidationError("source_url is missing a host")

    pinned_ip = _first_allowed_ip(hostname)
    pool = _pinned_pool(parsed, pinned_ip, timeout)
    http_response = pool.request(
        "GET",
        _request_path_and_query(parsed),
        headers={"Host": hostname},
        preload_content=False,
        redirect=False,
    )

    if http_response.status >= 400:
        raise SourceUrlValidationError(
            f"source_url fetch failed with status {http_response.status}"
        )

    content_length = http_response.headers.get("Content-Length")
    if content_length is not None:
        try:
            content_length_int = int(content_length)
        except ValueError as exc:
            raise SourceUrlValidationError("source file Content-Length is invalid") from exc
        if content_length_int > max_bytes:
            raise SourceUrlValidationError(
                f"source file exceeds max size ({max_bytes} bytes)"
            )

    chunks: list[bytes] = []
    total = 0
    for chunk in http_response.stream(1024 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise SourceUrlValidationError(f"source file exceeds max size ({max_bytes} bytes)")
        chunks.append(chunk)

    content_type = _strip_mime_parameters(http_response.headers.get("Content-Type"))
    return b"".join(chunks), content_type

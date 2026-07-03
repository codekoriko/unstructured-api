"""Secure fetch and outbound URL validation for async partition requests."""

from __future__ import annotations

import ipaddress
import os
import socket
from typing import Optional
from urllib.parse import urlparse

import requests

BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
    }
)

DEFAULT_SOURCE_HOST_SUFFIXES = ".supabase.co"
DEFAULT_DESTINATION_HOST_SUFFIXES = ".supabase.co"
DEFAULT_MAX_BYTES = 500 * 1024 * 1024
DEFAULT_FETCH_TIMEOUT_SECONDS = 300

SOURCE_ALLOWED_SUFFIXES_ENV = "SOURCE_URL_ALLOWED_HOST_SUFFIXES"
SOURCE_ALLOWED_HOSTS_ENV = "SOURCE_URL_ALLOWED_HOSTS"
DESTINATION_ALLOWED_SUFFIXES_ENV = "DESTINATION_URL_ALLOWED_HOST_SUFFIXES"
DESTINATION_ALLOWED_HOSTS_ENV = "DESTINATION_URL_ALLOWED_HOSTS"
CALLBACK_ALLOWED_SUFFIXES_ENV = "CALLBACK_URL_ALLOWED_HOST_SUFFIXES"
CALLBACK_ALLOWED_HOSTS_ENV = "CALLBACK_URL_ALLOWED_HOSTS"
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


def _check_resolved_ips(hostname: str) -> None:
    try:
        addrinfo = socket.getaddrinfo(hostname, None)
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


def validate_source_url(url: str) -> str:
    """Validate a signed download URL before the worker fetches the input file."""
    return _validate_outbound_url(
        url,
        url_label="source_url",
        allowed_hosts=_parse_csv_env(SOURCE_ALLOWED_HOSTS_ENV),
        allowed_suffixes=_parse_suffix_env(
            SOURCE_ALLOWED_SUFFIXES_ENV,
            DEFAULT_SOURCE_HOST_SUFFIXES,
        ),
        resolve_dns=True,
    )


def validate_destination_url(url: str) -> str:
    """Validate the signed upload URL where extraction JSON is written."""
    return _validate_outbound_url(
        url,
        url_label="destination_url",
        allowed_hosts=_parse_csv_env(DESTINATION_ALLOWED_HOSTS_ENV),
        allowed_suffixes=_parse_suffix_env(
            DESTINATION_ALLOWED_SUFFIXES_ENV,
            DEFAULT_DESTINATION_HOST_SUFFIXES,
        ),
        resolve_dns=True,
    )


def validate_callback_url(url: str) -> str:
    """Validate the orchestrator webhook URL resumed after async extraction."""
    return _validate_outbound_url(
        url,
        url_label="callback_url",
        allowed_hosts=_parse_csv_env(CALLBACK_ALLOWED_HOSTS_ENV),
        allowed_suffixes=_parse_suffix_env(CALLBACK_ALLOWED_SUFFIXES_ENV, ""),
        resolve_dns=True,
    )


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


def fetch_source_file(url: str) -> tuple[bytes, Optional[str]]:
    """Download a validated source file with size limits and redirect blocking."""
    validated_url = validate_source_url(url)
    max_bytes = _max_bytes()
    timeout = _fetch_timeout_seconds()

    response = requests.get(
        validated_url,
        stream=True,
        timeout=timeout,
        allow_redirects=False,
    )
    response.raise_for_status()

    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            if int(content_length) > max_bytes:
                raise SourceUrlValidationError(
                    f"source file exceeds max size ({max_bytes} bytes)"
                )
        except ValueError as exc:
            raise SourceUrlValidationError("source file Content-Length is invalid") from exc

    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=1024 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise SourceUrlValidationError(f"source file exceeds max size ({max_bytes} bytes)")
        chunks.append(chunk)

    content_type = _strip_mime_parameters(response.headers.get("Content-Type"))
    return b"".join(chunks), content_type

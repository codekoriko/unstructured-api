"""Secure fetch helpers for async partition requests that reference a remote file."""

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

DEFAULT_ALLOWED_HOST_SUFFIXES = ".supabase.co"
DEFAULT_MAX_BYTES = 500 * 1024 * 1024
DEFAULT_FETCH_TIMEOUT_SECONDS = 300


class SourceUrlValidationError(ValueError):
    """Raised when a source_url fails security validation."""


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def _parse_csv_env(name: str) -> frozenset[str]:
    raw = os.environ.get(name, "")
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())


def _allowed_host_suffixes() -> frozenset[str]:
    raw = os.environ.get("SOURCE_URL_ALLOWED_HOST_SUFFIXES", DEFAULT_ALLOWED_HOST_SUFFIXES)
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())


def _allowed_hosts() -> frozenset[str]:
    return _parse_csv_env("SOURCE_URL_ALLOWED_HOSTS")


def _http_allowed() -> bool:
    return _truthy_env("SOURCE_URL_ALLOW_HTTP")


def _max_bytes() -> int:
    return int(os.environ.get("SOURCE_URL_MAX_BYTES", str(DEFAULT_MAX_BYTES)))


def _fetch_timeout_seconds() -> int:
    return int(os.environ.get("SOURCE_URL_FETCH_TIMEOUT_SECONDS", str(DEFAULT_FETCH_TIMEOUT_SECONDS)))


def _strip_mime_parameters(content_type: str | None) -> str | None:
    if not content_type:
        return content_type
    return content_type.split(";", 1)[0].strip()


def _ip_is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip == ipaddress.ip_address("169.254.169.254")
    )


def _hostname_is_allowed(hostname: str) -> bool:
    host = hostname.lower().rstrip(".")
    if host in _allowed_hosts():
        return True
    if host in BLOCKED_HOSTNAMES:
        return False
    return any(host.endswith(suffix) for suffix in _allowed_host_suffixes())


def _check_resolved_ips(hostname: str) -> None:
    try:
        addrinfo = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise SourceUrlValidationError(f"Cannot resolve source_url host: {hostname}") from exc

    for _, _, _, _, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _ip_is_blocked(ip):
            raise SourceUrlValidationError(f"source_url resolves to blocked address: {ip_str}")


def validate_source_url(url: str) -> str:
    """Validate a remote file URL before the worker fetches it.

  Security controls:
  - HTTPS only by default (`SOURCE_URL_ALLOW_HTTP=true` for local dev)
  - Host allowlist via suffixes (`SOURCE_URL_ALLOWED_HOST_SUFFIXES`) and/or exact hosts
    (`SOURCE_URL_ALLOWED_HOSTS`)
  - Blocks private, loopback, link-local, and metadata-style targets
  - Rejects embedded credentials and non-http(s) schemes
  - DNS resolution checked to reduce SSRF via allowed-looking hostnames
    """
    cleaned = url.strip()
    if not cleaned:
        raise SourceUrlValidationError("source_url is empty")

    parsed = urlparse(cleaned)
    scheme = (parsed.scheme or "").lower()
    if scheme == "https":
        pass
    elif scheme == "http" and _http_allowed():
        pass
    else:
        raise SourceUrlValidationError("source_url must use https")

    hostname = parsed.hostname
    if not hostname:
        raise SourceUrlValidationError("source_url is missing a host")

    if parsed.username or parsed.password:
        raise SourceUrlValidationError("source_url must not contain embedded credentials")

    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        if not _hostname_is_allowed(hostname):
            raise SourceUrlValidationError("source_url host is not allowed")
        _check_resolved_ips(hostname)
    else:
        explicitly_allowed = hostname.lower() in _allowed_hosts()
        if _ip_is_blocked(ip) and not explicitly_allowed:
            raise SourceUrlValidationError("source_url host IP is not allowed")
        if not _hostname_is_allowed(hostname):
            raise SourceUrlValidationError("source_url host is not allowed")

    return cleaned


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

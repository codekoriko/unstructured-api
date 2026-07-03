from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import socket

import pytest
import requests

from prepline_general.api.source_url import (
    SourceUrlValidationError,
    fetch_source_file,
    outbound_request,
    validate_callback_url,
    validate_destination_url,
    validate_source_filename,
    validate_source_url,
)

SUPABASE_SIGNED_DOWNLOAD = (
    "https://project.supabase.co/storage/v1/object/sign/bucket/doc.pdf?token=abc"
)
SUPABASE_SIGNED_UPLOAD = (
    "https://project.supabase.co/storage/v1/object/upload/sign/bucket/out.json?token=abc"
)


def _fake_public_getaddrinfo(host, port, *_args, **_kwargs):
    return [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("52.0.0.0", 0)),
    ]


@pytest.fixture
def public_dns(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "prepline_general.api.source_url.socket.getaddrinfo",
        _fake_public_getaddrinfo,
    )


@pytest.mark.parametrize(
    ("host", "suffix", "expected"),
    [
        ("project.supabase.co", ".supabase.co", True),
        ("supabase.co", "supabase.co", True),
        ("attacker-supabase.co", ".supabase.co", False),
        ("notsupabase.co", ".supabase.co", False),
        ("evil.supabase.co.attacker.com", ".supabase.co", False),
    ],
)
def test_hostname_suffix_boundary_via_validation(
    host: str,
    suffix: str,
    expected: bool,
    monkeypatch: pytest.MonkeyPatch,
    public_dns: None,
):
    monkeypatch.setenv("OUTBOUND_URL_ALLOWED_HOST_SUFFIXES", suffix)
    monkeypatch.delenv("OUTBOUND_URL_ALLOWED_HOSTS", raising=False)
    url = f"https://{host}/file.pdf"
    if expected:
        assert validate_source_url(url) == url
    else:
        with pytest.raises(SourceUrlValidationError, match="not allowed"):
            validate_source_url(url)


def test_validate_source_url_allows_exact_host(monkeypatch: pytest.MonkeyPatch, public_dns: None):
    monkeypatch.delenv("OUTBOUND_URL_ALLOWED_HOST_SUFFIXES", raising=False)
    monkeypatch.setenv("OUTBOUND_URL_ALLOWED_HOSTS", "storage.internal")
    url = "https://storage.internal/signed/doc.pdf"
    assert validate_source_url(url) == url


def test_legacy_per_role_env_vars_are_merged(monkeypatch: pytest.MonkeyPatch, public_dns: None):
    monkeypatch.delenv("OUTBOUND_URL_ALLOWED_HOST_SUFFIXES", raising=False)
    monkeypatch.delenv("OUTBOUND_URL_ALLOWED_HOSTS", raising=False)
    monkeypatch.setenv("CALLBACK_URL_ALLOWED_HOSTS", "kestra.internal")
    url = "https://kestra.internal/api/v1/main/executions/1/resume"
    assert validate_callback_url(url) == url


def test_validate_source_url_rejects_dns_to_private_ip(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "prepline_general.api.source_url.socket.getaddrinfo",
        lambda host, port, *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 0)),
        ],
    )
    with pytest.raises(SourceUrlValidationError, match="blocked address"):
        validate_source_url(SUPABASE_SIGNED_DOWNLOAD)


def test_validate_destination_url_rejects_fake_supabase_suffix(
    monkeypatch: pytest.MonkeyPatch,
    public_dns: None,
):
    monkeypatch.delenv("OUTBOUND_URL_ALLOWED_HOSTS", raising=False)
    with pytest.raises(SourceUrlValidationError, match="not allowed"):
        validate_destination_url("https://attacker-supabase.co/upload")


def test_validate_callback_url_allows_configured_suffix(
    monkeypatch: pytest.MonkeyPatch,
    public_dns: None,
):
    monkeypatch.delenv("OUTBOUND_URL_ALLOWED_HOSTS", raising=False)
    monkeypatch.setenv("OUTBOUND_URL_ALLOWED_HOST_SUFFIXES", ".kestra.example.com")
    url = "https://kestra.example.com/api/v1/main/executions/1/resume"
    assert validate_callback_url(url) == url


def test_validate_outbound_url_allows_http_when_configured(
    monkeypatch: pytest.MonkeyPatch,
    public_dns: None,
):
    monkeypatch.setenv("OUTBOUND_URL_ALLOW_HTTP", "true")
    monkeypatch.setenv("OUTBOUND_URL_ALLOWED_HOSTS", "kong")
    url = "http://kong/storage/v1/object/sign/bucket/doc.pdf"
    assert validate_source_url(url) == url


@patch("prepline_general.api.source_url.requests.request")
def test_outbound_request_disables_redirects(
    mock_request: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    public_dns: None,
):
    monkeypatch.setenv("OUTBOUND_URL_ALLOWED_HOSTS", "example.com")
    mock_request.return_value = MagicMock(ok=True, status_code=200, text="")
    outbound_request("POST", "https://example.com/callback", url_label="callback_url")
    assert mock_request.call_args.kwargs["allow_redirects"] is False


@patch("prepline_general.api.source_url._pinned_pool")
def test_fetch_source_file_returns_body_and_strips_content_type(
    mock_pool: MagicMock,
    public_dns: None,
):
    mock_http_response = MagicMock()
    mock_http_response.status = 200
    mock_http_response.headers = {"Content-Type": "application/pdf; charset=binary"}
    mock_http_response.stream.return_value = [b"pdf-bytes"]
    mock_pool.return_value.request.return_value = mock_http_response

    content, content_type = fetch_source_file(SUPABASE_SIGNED_DOWNLOAD)

    assert content == b"pdf-bytes"
    assert content_type == "application/pdf"
    mock_pool.return_value.request.assert_called_once()
    assert mock_pool.return_value.request.call_args.kwargs["redirect"] is False


@patch("prepline_general.api.source_url._pinned_pool")
def test_fetch_source_file_rejects_content_length_over_max(
    mock_pool: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    public_dns: None,
):
    monkeypatch.setenv("SOURCE_URL_MAX_BYTES", "10")
    mock_http_response = SimpleNamespace(
        status=200,
        headers={"Content-Length": "11"},
        stream=lambda chunk_size: iter([]),
    )
    mock_pool.return_value.request.return_value = mock_http_response

    with pytest.raises(SourceUrlValidationError, match="exceeds max size"):
        fetch_source_file(SUPABASE_SIGNED_DOWNLOAD)


@patch("prepline_general.api.source_url._pinned_pool")
def test_fetch_source_file_rejects_streamed_body_over_max(
    mock_pool: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    public_dns: None,
):
    monkeypatch.setenv("SOURCE_URL_MAX_BYTES", "5")
    mock_http_response = MagicMock()
    mock_http_response.status = 200
    mock_http_response.headers = {}
    mock_http_response.stream.return_value = [b"123456"]
    mock_pool.return_value.request.return_value = mock_http_response

    with pytest.raises(SourceUrlValidationError, match="exceeds max size"):
        fetch_source_file(SUPABASE_SIGNED_DOWNLOAD)


@patch("prepline_general.api.source_url._pinned_pool")
def test_fetch_source_file_rejects_invalid_content_length(mock_pool: MagicMock, public_dns: None):
    mock_http_response = SimpleNamespace(
        status=200,
        headers={"Content-Length": "not-a-number"},
        stream=lambda chunk_size: iter([]),
    )
    mock_pool.return_value.request.return_value = mock_http_response

    with pytest.raises(SourceUrlValidationError, match="Content-Length is invalid"):
        fetch_source_file(SUPABASE_SIGNED_DOWNLOAD)


@patch("prepline_general.api.source_url._pinned_pool")
def test_fetch_source_file_rejects_http_error_status(mock_pool: MagicMock, public_dns: None):
    mock_http_response = SimpleNamespace(
        status=403,
        headers={},
        stream=lambda chunk_size: iter([]),
    )
    mock_pool.return_value.request.return_value = mock_http_response

    with pytest.raises(SourceUrlValidationError, match="fetch failed with status 403"):
        fetch_source_file(SUPABASE_SIGNED_DOWNLOAD)


def test_validate_source_filename_rejects_empty():
    with pytest.raises(SourceUrlValidationError, match="required"):
        validate_source_filename(None)

    with pytest.raises(SourceUrlValidationError, match="required"):
        validate_source_filename("   ")


def test_validate_destination_url_accepts_supabase_signed_upload(
    monkeypatch: pytest.MonkeyPatch,
    public_dns: None,
):
    monkeypatch.delenv("OUTBOUND_URL_ALLOWED_HOSTS", raising=False)
    assert validate_destination_url(SUPABASE_SIGNED_UPLOAD) == SUPABASE_SIGNED_UPLOAD

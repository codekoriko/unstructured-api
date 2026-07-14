import socket
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from prepline_general.api.app import app
from prepline_general.api.source_url import (
    SourceUrlValidationError,
    validate_callback_url,
    validate_destination_url,
    validate_source_filename,
    validate_source_url,
)

MAIN_API_ROUTE = "general/v0/general"


@pytest.fixture(autouse=True)
def allow_test_outbound_hosts(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OUTBOUND_URL_ALLOWED_HOSTS", "example.com,project.supabase.co")


def _fake_public_getaddrinfo(host, port, *_args, **_kwargs):
    return [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("52.0.0.0", 0)),
    ]


@pytest.fixture(autouse=True)
def mock_supabase_dns(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "prepline_general.api.source_url.socket.getaddrinfo",
        _fake_public_getaddrinfo,
    )


def _run_async_inline(fn, *args, **kwargs):
    return fn(*args, **kwargs)


@pytest.fixture
def run_async_inline(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "prepline_general.api.general.single_worker_executor.submit",
        _run_async_inline,
    )


@patch("prepline_general.api.general.outbound_request")
@patch("prepline_general.api.general.pipeline_api")
@pytest.mark.usefixtures("run_async_inline")
def test_async_partition(mock_pipeline, mock_outbound_request):
    """
    Test that when destination_url is provided, the API returns 202 Accepted
    and the pipeline runs in the background.
    """
    client = TestClient(app)
    test_file = Path("sample-docs") / "fake-text.txt"

    mock_pipeline.return_value = [{"text": "Hello async", "type": "Text"}]
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.text = ""
    mock_outbound_request.return_value = mock_response

    with open(test_file, "rb") as f:
        response = client.post(
            MAIN_API_ROUTE,
            files=[("files", (str(test_file), f, "text/plain"))],
            data={
                "destination_url": "https://example.com/upload",
                "callback_url": "https://example.com/callback",
                "callback_headers": '{"Authorization": "Bearer secret"}',
            },
        )

    assert response.status_code == 202
    assert response.json() == {"detail": "Accepted for processing"}

    mock_pipeline.assert_called_once()
    put_call, post_call = mock_outbound_request.call_args_list
    assert put_call.args == ("PUT", "https://example.com/upload")
    assert put_call.kwargs["data"] == b'[{"text": "Hello async", "type": "Text"}]'
    assert put_call.kwargs["headers"] == {"Content-Type": "application/json"}
    assert post_call.args == ("POST", "https://example.com/callback")
    assert post_call.kwargs["headers"] == {"Authorization": "Bearer secret"}


@patch("prepline_general.api.general.outbound_request")
@patch("prepline_general.api.general.pipeline_api")
@patch("prepline_general.api.general.fetch_source_file")
@pytest.mark.usefixtures("run_async_inline")
def test_async_partition_with_source_url(
    mock_fetch_source_file,
    mock_pipeline,
    mock_outbound_request,
):
    client = TestClient(app)
    mock_fetch_source_file.return_value = (b"hello from signed url", "text/plain")
    mock_pipeline.return_value = [{"text": "Hello source", "type": "Text"}]
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.text = ""
    mock_outbound_request.return_value = mock_response

    response = client.post(
        MAIN_API_ROUTE,
        data={
            "destination_url": "https://example.com/upload",
            "source_url": "https://project.supabase.co/storage/v1/object/sign/bucket/doc.pdf?token=abc",
            "source_filename": "doc.pdf",
            "callback_url": "https://example.com/callback",
        },
    )

    assert response.status_code == 202
    mock_fetch_source_file.assert_called_once()
    mock_pipeline.assert_called_once()
    assert mock_outbound_request.call_count == 2


@patch("prepline_general.api.general.outbound_request")
@patch("prepline_general.api.general.fetch_source_file")
@pytest.mark.usefixtures("run_async_inline")
def test_async_partition_sends_callback_when_source_fetch_fails(
    mock_fetch_source_file,
    mock_outbound_request,
):
    client = TestClient(app)
    mock_fetch_source_file.side_effect = SourceUrlValidationError("source file exceeds max size")
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.text = ""
    mock_outbound_request.return_value = mock_response

    response = client.post(
        MAIN_API_ROUTE,
        data={
            "destination_url": "https://example.com/upload",
            "source_url": "https://project.supabase.co/storage/v1/object/sign/bucket/doc.pdf?token=abc",
            "source_filename": "doc.pdf",
            "callback_url": "https://example.com/callback",
        },
    )

    assert response.status_code == 202
    mock_outbound_request.assert_called_once_with(
        "POST",
        "https://example.com/callback",
        url_label="callback_url",
    )


def test_async_partition_rejects_source_url_and_files():
    client = TestClient(app)
    test_file = Path("sample-docs") / "fake-text.txt"

    with open(test_file, "rb") as f:
        response = client.post(
            MAIN_API_ROUTE,
            files=[("files", (str(test_file), f, "text/plain"))],
            data={
                "destination_url": "https://example.com/upload",
                "source_url": "https://project.supabase.co/storage/v1/object/sign/bucket/doc.pdf?token=abc",
                "source_filename": "doc.pdf",
            },
        )

    assert response.status_code == 400
    assert "not both" in response.json()["detail"]


def test_async_partition_rejects_disallowed_source_url():
    client = TestClient(app)

    response = client.post(
        MAIN_API_ROUTE,
        data={
            "destination_url": "https://example.com/upload",
            "source_url": "https://evil.example/object/file.pdf",
            "source_filename": "file.pdf",
        },
    )

    assert response.status_code == 400
    assert "not allowed" in response.json()["detail"]


def test_async_partition_rejects_missing_source_filename():
    client = TestClient(app)

    response = client.post(
        MAIN_API_ROUTE,
        data={
            "destination_url": "https://example.com/upload",
            "source_url": "https://project.supabase.co/storage/v1/object/sign/bucket/doc.pdf?token=abc",
        },
    )

    assert response.status_code == 400
    assert "source_filename" in response.json()["detail"]


@patch.dict("os.environ", {"UNSTRUCTURED_API_KEY": "secret-key"}, clear=False)
def test_partition_rejects_invalid_api_key_without_echoing_value():
    client = TestClient(app)
    test_file = Path("sample-docs") / "fake-text.txt"

    with open(test_file, "rb") as f:
        response = client.post(
            MAIN_API_ROUTE,
            files=[("files", (str(test_file), f, "text/plain"))],
            headers={"unstructured-api-key": "wrong-key"},
        )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail == "Invalid or missing API key"
    assert "wrong-key" not in detail
    assert "secret-key" not in detail


def test_async_partition_rejects_disallowed_destination_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OUTBOUND_URL_ALLOWED_HOSTS", "project.supabase.co,example.com")
    client = TestClient(app)
    test_file = Path("sample-docs") / "fake-text.txt"

    with open(test_file, "rb") as f:
        response = client.post(
            MAIN_API_ROUTE,
            files=[("files", (str(test_file), f, "text/plain"))],
            data={
                "destination_url": "https://evil.example/upload",
                "callback_url": "https://example.com/callback",
            },
        )

    assert response.status_code == 400
    assert "destination_url" in response.json()["detail"]


def test_async_partition_rejects_disallowed_callback_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OUTBOUND_URL_ALLOWED_HOSTS", "project.supabase.co,example.com")
    client = TestClient(app)
    test_file = Path("sample-docs") / "fake-text.txt"

    with open(test_file, "rb") as f:
        response = client.post(
            MAIN_API_ROUTE,
            files=[("files", (str(test_file), f, "text/plain"))],
            data={
                "destination_url": "https://example.com/upload",
                "callback_url": "https://evil.example/callback",
            },
        )

    assert response.status_code == 400
    assert "callback_url" in response.json()["detail"]


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/file.pdf",
        "https://localhost/file.pdf",
        "https://metadata.google.internal/file.pdf",
        "ftp://project.supabase.co/file.pdf",
        "https://user:pass@project.supabase.co/file.pdf",
    ],
)
def test_validate_source_url_blocks_unsafe_targets(url: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SOURCE_URL_ALLOW_HTTP", raising=False)
    monkeypatch.delenv("OUTBOUND_URL_ALLOW_HTTP", raising=False)
    monkeypatch.setenv("OUTBOUND_URL_ALLOWED_HOSTS", "project.supabase.co")
    with pytest.raises(SourceUrlValidationError):
        validate_source_url(url)


def test_validate_source_url_allows_supabase_host(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OUTBOUND_URL_ALLOWED_HOSTS", "project.supabase.co")
    validate_source_url(
        "https://project.supabase.co/storage/v1/object/sign/bucket/doc.pdf?token=abc"
    )


def test_validate_source_url_rejects_unlisted_host(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OUTBOUND_URL_ALLOWED_HOSTS", "project.supabase.co")
    monkeypatch.setattr(
        "prepline_general.api.source_url.socket.getaddrinfo",
        lambda host, port: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("52.0.0.0", 0)),
        ],
    )
    with pytest.raises(SourceUrlValidationError):
        validate_source_url("https://attacker-supabase.co/file.pdf")


def test_validate_destination_url_allows_supabase_host(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OUTBOUND_URL_ALLOWED_HOSTS", "project.supabase.co")
    validate_destination_url(
        "https://project.supabase.co/storage/v1/object/upload/sign/bucket/out.json?token=abc"
    )


def test_validate_callback_url_rejects_unlisted_host(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OUTBOUND_URL_ALLOWED_HOSTS", "project.supabase.co")
    with pytest.raises(SourceUrlValidationError, match="not allowed"):
        validate_callback_url("https://kestra.example.com/api/v1/main/executions/1/resume")


def test_validate_source_filename_requires_basename():
    assert validate_source_filename("doc.pdf") == "doc.pdf"

    with pytest.raises(SourceUrlValidationError):
        validate_source_filename("../doc.pdf")

    with pytest.raises(SourceUrlValidationError):
        validate_source_filename("folder/doc.pdf")

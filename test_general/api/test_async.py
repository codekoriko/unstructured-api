from pathlib import Path
from unittest.mock import patch
import socket

import pytest
from fastapi.testclient import TestClient

from prepline_general.api.app import app
from prepline_general.api.source_url import (
    SourceUrlValidationError,
    validate_source_filename,
    validate_source_url,
)

MAIN_API_ROUTE = "general/v0/general"


@patch("prepline_general.api.general.requests.put")
@patch("prepline_general.api.general.requests.post")
@patch("prepline_general.api.general.pipeline_api")
def test_async_partition(mock_pipeline, mock_post, mock_put):
    """
    Test that when destination_url is provided, the API returns 202 Accepted
    and the pipeline runs in the background.
    """
    client = TestClient(app)
    test_file = Path("sample-docs") / "fake-text.txt"

    mock_pipeline.return_value = [{"text": "Hello async", "type": "Text"}]

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

    # TestClient automatically runs background tasks inline after returning the response.
    mock_pipeline.assert_called_once()
    mock_put.assert_called_once_with(
        "https://example.com/upload",
        data=b'[{"text": "Hello async", "type": "Text"}]',
        headers={"Content-Type": "application/json"},
    )
    mock_post.assert_called_once_with(
        "https://example.com/callback",
        headers={"Authorization": "Bearer secret"},
    )


@patch("prepline_general.api.general.requests.put")
@patch("prepline_general.api.general.requests.post")
@patch("prepline_general.api.general.pipeline_api")
@patch("prepline_general.api.general.fetch_source_file")
def test_async_partition_with_source_url(
    mock_fetch_source_file,
    mock_pipeline,
    mock_post,
    mock_put,
):
    client = TestClient(app)
    mock_fetch_source_file.return_value = (b"hello from signed url", "text/plain")
    mock_pipeline.return_value = [{"text": "Hello source", "type": "Text"}]

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
    mock_put.assert_called_once()


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
    with pytest.raises(SourceUrlValidationError):
        validate_source_url(url)


def test_validate_source_url_allows_supabase_host(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "prepline_general.api.source_url.socket.getaddrinfo",
        lambda host, port: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("52.0.0.0", 0)),
        ],
    )
    validate_source_url(
        "https://project.supabase.co/storage/v1/object/sign/bucket/doc.pdf?token=abc"
    )


def test_validate_source_filename_requires_basename():
    assert validate_source_filename("doc.pdf") == "doc.pdf"

    with pytest.raises(SourceUrlValidationError):
        validate_source_filename("../doc.pdf")

    with pytest.raises(SourceUrlValidationError):
        validate_source_filename("folder/doc.pdf")

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from prepline_general.api.app import app

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

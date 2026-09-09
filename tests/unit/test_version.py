import pytest
from unittest.mock import patch, MagicMock
from listing_hub.core.version import (
    APP_VERSION,
    get_local_commit_sha,
    fetch_latest_github_info,
    get_version_status,
    _version_cache
)

def test_app_version_defined():
    assert APP_VERSION == "3.8.4"

def test_get_local_commit_sha_from_env():
    with patch.dict("os.environ", {"GIT_COMMIT_SHA": "abc1234567890"}):
        sha = get_local_commit_sha()
        assert sha == "abc1234567890"

def test_get_local_commit_sha_git_fallback():
    with patch.dict("os.environ", {"GIT_COMMIT_SHA": ""}):
        with patch("subprocess.check_output", return_value="fedcba9876543210\n"):
            sha = get_local_commit_sha()
            assert sha == "fedcba9876543210"

def test_fetch_latest_github_info_success():
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {
        "sha": "1234567890abcdef1234567890abcdef12345678",
        "commit": {
            "message": "feat: add robust version inspector\n\nDetailed notes here.",
            "author": {
                "name": "Ondřej Hála",
                "date": "2026-09-09T18:00:00Z"
            }
        },
        "html_url": "https://github.com/onhala/listing-hub/commit/1234567890"
    }

    with patch("requests.get", return_value=mock_res):
        info = fetch_latest_github_info()
        assert info["sha"] == "1234567890abcdef1234567890abcdef12345678"
        assert info["short_sha"] == "1234567"
        assert info["message"] == "feat: add robust version inspector"
        assert info["rate_limited"] is False

def test_fetch_latest_github_info_rate_limited():
    mock_res = MagicMock()
    mock_res.status_code = 403

    with patch("requests.get", return_value=mock_res):
        info = fetch_latest_github_info()
        assert info["rate_limited"] is True
        assert "Limit požadavků" in info["message"]

def test_get_version_status_diff_and_compare_url():
    # Reset cache
    _version_cache["data"] = None
    _version_cache["timestamp"] = 0

    with patch("listing_hub.core.version.get_local_commit_sha", return_value="11111112222222"):
        with patch("listing_hub.core.version.fetch_latest_github_info", return_value={
            "sha": "99999998888888",
            "short_sha": "9999999",
            "message": "fix: bug",
            "date": "2026-09-09T18:00:00Z",
            "author": "Ondra",
            "url": "https://github.com/onhala/listing-hub/commit/9999999",
            "rate_limited": False
        }):
            status = get_version_status(force=True)
            assert status["status"] == "success"
            assert status["update_available"] is True
            assert status["local"]["hash"] == "1111111"
            assert status["latest"]["hash"] == "9999999"
            assert "compare/1111111...9999999" in status["compare_url"]

def test_get_version_status_caching():
    # Reset cache
    _version_cache["data"] = None
    _version_cache["timestamp"] = 0

    with patch("listing_hub.core.version.get_local_commit_sha", return_value="aaaaaaa"):
        with patch("listing_hub.core.version.fetch_latest_github_info", return_value={
            "sha": "aaaaaaa",
            "short_sha": "aaaaaaa",
            "message": "clean",
            "date": "",
            "author": "",
            "url": "",
            "rate_limited": False
        }) as mock_fetch:
            res1 = get_version_status(force=True)
            assert res1["update_available"] is False
            assert mock_fetch.call_count == 1

            # Second call without force should hit cache
            res2 = get_version_status(force=False)
            assert res2["cached"] is True
            assert mock_fetch.call_count == 1

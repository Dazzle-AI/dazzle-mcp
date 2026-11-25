"""Unit tests for the stdio MCP proxy: token forwarding, refresh, device flow, login state."""

from __future__ import annotations

import stat
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dazzle_photo_intelligence import proxy


@pytest.fixture(autouse=True)
def reset_storage(monkeypatch):
    state: dict[str, str] = {}

    def _get(field: str) -> str | None:
        return state.get(field)

    def _set(field: str, value: str) -> None:
        state[field] = value

    def _delete(field: str) -> None:
        state.pop(field, None)

    def _clear_all() -> None:
        state.clear()

    monkeypatch.setattr(proxy.storage, "get", _get)
    monkeypatch.setattr(proxy.storage, "set_", _set)
    monkeypatch.setattr(proxy.storage, "delete", _delete)
    monkeypatch.setattr(proxy.storage, "clear_all", _clear_all)
    return state


@pytest.fixture(autouse=True)
def isolated_cache_dir(monkeypatch, tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(proxy, "_cache_dir", lambda: cache)
    return cache


def _fresh_state(state: dict[str, str]) -> None:
    state["access_token"] = "access-current"
    state["refresh_token"] = "refresh-current"
    state["expires_at"] = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    state["client_id"] = "dazzle-photo-intelligence-skill"
    state["host"] = "https://api.example.com"


def _stale_state(state: dict[str, str]) -> None:
    state["access_token"] = "access-old"
    state["refresh_token"] = "refresh-old"
    state["expires_at"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    state["client_id"] = "dazzle-photo-intelligence-skill"
    state["host"] = "https://api.example.com"


# --- _forward ---


@pytest.mark.asyncio
async def test_forward_attaches_bearer_token(reset_storage):
    _fresh_state(reset_storage)

    mock_client = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
    response.raise_for_status = MagicMock()
    mock_client.post = AsyncMock(return_value=response)

    result = await proxy._forward(mock_client, "https://api.example.com", "client-x", "tools/list", None)

    assert result == {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
    args, kwargs = mock_client.post.call_args
    assert args[0] == "https://api.example.com/mcp"
    assert kwargs["headers"]["Authorization"] == "Bearer access-current"


@pytest.mark.asyncio
async def test_forward_refreshes_on_401(reset_storage):
    _fresh_state(reset_storage)

    mock_client = MagicMock()
    unauthorized = MagicMock()
    unauthorized.status_code = 401
    success = MagicMock()
    success.status_code = 200
    success.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": {}}
    success.raise_for_status = MagicMock()
    mock_client.post = AsyncMock(side_effect=[unauthorized, success])

    with patch("dazzle_photo_intelligence.proxy._refresh_access_token", new=AsyncMock(return_value="access-rotated")):
        result = await proxy._forward(mock_client, "https://api.example.com", "client-x", "tools/list", None)

    assert result == {"jsonrpc": "2.0", "id": 1, "result": {}}
    assert mock_client.post.await_count == 2


@pytest.mark.asyncio
async def test_forward_clears_tokens_when_refresh_fails(reset_storage):
    _fresh_state(reset_storage)

    mock_client = MagicMock()
    unauthorized = MagicMock()
    unauthorized.status_code = 401
    mock_client.post = AsyncMock(return_value=unauthorized)

    with patch("dazzle_photo_intelligence.proxy._refresh_access_token", new=AsyncMock(return_value=None)):
        with pytest.raises(RuntimeError, match="not_signed_in"):
            await proxy._forward(mock_client, "https://api.example.com", "client-x", "tools/list", None)

    assert reset_storage == {}


@pytest.mark.asyncio
async def test_forward_clears_tokens_when_second_401_after_refresh(reset_storage):
    _fresh_state(reset_storage)

    mock_client = MagicMock()
    unauthorized = MagicMock()
    unauthorized.status_code = 401
    mock_client.post = AsyncMock(return_value=unauthorized)

    with patch("dazzle_photo_intelligence.proxy._refresh_access_token", new=AsyncMock(return_value="access-rotated")):
        with pytest.raises(RuntimeError, match="not_signed_in"):
            await proxy._forward(mock_client, "https://api.example.com", "client-x", "tools/list", None)

    assert reset_storage == {}


# --- _ensure_access_token / _refresh_access_token ---


@pytest.mark.asyncio
async def test_ensure_access_token_refreshes_when_stale(reset_storage):
    _stale_state(reset_storage)
    mock_client = MagicMock()

    with patch(
        "dazzle_photo_intelligence.proxy._refresh_access_token", new=AsyncMock(return_value="access-rotated")
    ) as mock_refresh:
        token = await proxy._ensure_access_token(mock_client, "https://api.example.com", "client-x")

    assert token == "access-rotated"
    mock_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_access_token_skips_refresh_when_lock_holder_already_rotated(reset_storage):
    _stale_state(reset_storage)
    mock_client = MagicMock()

    def _swap_in_fresh_during_lock(*_a, **_kw):
        reset_storage["access_token"] = "access-just-rotated"
        reset_storage["expires_at"] = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        return None

    with (
        patch("dazzle_photo_intelligence.proxy._refresh_lock") as mock_lock,
        patch("dazzle_photo_intelligence.proxy._refresh_access_token", new=AsyncMock()) as mock_refresh,
    ):
        mock_lock.return_value.__enter__ = MagicMock(side_effect=_swap_in_fresh_during_lock)
        mock_lock.return_value.__exit__ = MagicMock(return_value=False)

        token = await proxy._ensure_access_token(mock_client, "https://api.example.com", "client-x")

    assert token == "access-just-rotated"
    mock_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_access_token_persists_new_tokens(reset_storage):
    _stale_state(reset_storage)

    mock_client = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "access_token": "access-new",
        "refresh_token": "refresh-new",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "query",
    }
    mock_client.post = AsyncMock(return_value=response)

    token = await proxy._refresh_access_token(mock_client, "https://api.example.com", "client-x")

    assert token == "access-new"
    assert reset_storage["access_token"] == "access-new"
    assert reset_storage["refresh_token"] == "refresh-new"


@pytest.mark.asyncio
async def test_refresh_access_token_returns_none_on_failure(reset_storage):
    _stale_state(reset_storage)

    mock_client = MagicMock()
    response = MagicMock()
    response.status_code = 400
    mock_client.post = AsyncMock(return_value=response)

    token = await proxy._refresh_access_token(mock_client, "https://api.example.com", "client-x")

    assert token is None


@pytest.mark.asyncio
async def test_refresh_access_token_returns_none_when_no_refresh_token(reset_storage):
    mock_client = MagicMock()

    token = await proxy._refresh_access_token(mock_client, "https://api.example.com", "client-x")

    assert token is None


@pytest.mark.asyncio
async def test_refresh_access_token_returns_peer_token_when_we_lose_race(reset_storage):
    """Refresh tokens are one-time-use. If a peer process rotated tokens during our network
    call, our /oauth2/token POST returns invalid_grant — but the peer's fresh access token
    is already in storage. Return that instead of None so callers don't _clear_tokens()."""
    _stale_state(reset_storage)

    invalid = MagicMock()
    invalid.status_code = 400
    invalid.json.return_value = {"error": "invalid_grant"}

    async def _peer_rotates_during_post(*_a, **_kw):
        reset_storage["access_token"] = "access-from-peer"
        reset_storage["refresh_token"] = "refresh-from-peer"
        reset_storage["expires_at"] = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        return invalid

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=_peer_rotates_during_post)

    token = await proxy._refresh_access_token(mock_client, "https://api.example.com", "client-x")

    assert token == "access-from-peer"


@pytest.mark.asyncio
async def test_refresh_access_token_uses_peer_token_when_both_succeed_concurrently(reset_storage):
    """If our refresh succeeds but a peer also stored fresh tokens between our network call
    and our store, defer to the peer's tokens rather than overwriting them."""
    _stale_state(reset_storage)

    success = MagicMock()
    success.status_code = 200
    success.json.return_value = {
        "access_token": "access-ours",
        "refresh_token": "refresh-ours",
        "expires_in": 3600,
    }

    async def _peer_rotates_during_post(*_a, **_kw):
        reset_storage["access_token"] = "access-from-peer"
        reset_storage["refresh_token"] = "refresh-from-peer"
        reset_storage["expires_at"] = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        return success

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=_peer_rotates_during_post)

    token = await proxy._refresh_access_token(mock_client, "https://api.example.com", "client-x")

    assert token == "access-from-peer"
    assert reset_storage["access_token"] == "access-from-peer"
    assert reset_storage["refresh_token"] == "refresh-from-peer"


# --- pending.json cache ---


def test_pending_round_trip(isolated_cache_dir: Path):
    assert proxy._load_pending() is None
    payload = {
        "device_code": "dev-abc",
        "user_code": "ABCD-EFGH",
        "expires_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        "interval": 5,
    }
    proxy._write_pending(payload)
    assert proxy._load_pending() == payload
    proxy._delete_pending()
    assert proxy._load_pending() is None


def test_is_pending_fresh_true_for_future_expiry():
    pending = {"expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()}
    assert proxy._is_pending_fresh(pending) is True


def test_is_pending_fresh_false_for_past_expiry():
    pending = {"expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()}
    assert proxy._is_pending_fresh(pending) is False


def test_is_pending_fresh_false_when_missing_field():
    assert proxy._is_pending_fresh({}) is False


# --- _ensure_login ---


def _device_authorization_response() -> dict:
    return {
        "device_code": "device-abc",
        "user_code": "ABCD-EFGH",
        "verification_uri": "https://app.example.com/device",
        "verification_uri_complete": "https://app.example.com/device?user_code=ABCD-EFGH",
        "expires_in": 900,
        "interval": 5,
    }


@pytest.mark.asyncio
async def test_ensure_login_returns_authenticated_when_refresh_token_present(reset_storage):
    _fresh_state(reset_storage)
    coord = proxy._LoginCoordinator()
    mock_client = MagicMock()

    result = await proxy._ensure_login(coord, mock_client, "https://api.example.com", "client-x", "query")

    assert result == {"status": "authenticated"}


@pytest.mark.asyncio
async def test_ensure_login_starts_fresh_flow_when_no_pending(reset_storage):
    coord = proxy._LoginCoordinator()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = _device_authorization_response()
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=response)

    result = await proxy._ensure_login(coord, mock_client, "https://api.example.com", "client-x", "query")

    assert result["status"] == "pending"
    assert result["pending"]["user_code"] == "ABCD-EFGH"
    persisted = proxy._load_pending()
    assert persisted is not None
    assert persisted["device_code"] == "device-abc"
    assert "owner_pid" not in persisted
    assert "last_heartbeat" not in persisted


@pytest.mark.asyncio
async def test_ensure_login_returns_existing_pending_without_starting_new_flow(reset_storage):
    coord = proxy._LoginCoordinator()
    pending = {
        "device_code": "device-existing",
        "user_code": "WXYZ-1234",
        "verification_uri": "https://app.example.com/device",
        "verification_uri_complete": "https://app.example.com/device?user_code=WXYZ-1234",
        "expires_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        "interval": 5,
    }
    proxy._write_pending(pending)
    pending_resp = MagicMock()
    pending_resp.status_code = 400
    pending_resp.json.return_value = {"error": "authorization_pending"}
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=pending_resp)

    result = await proxy._ensure_login(coord, mock_client, "https://api.example.com", "client-x", "query")

    assert result["status"] == "pending"
    assert result["pending"]["user_code"] == "WXYZ-1234"
    # Single /oauth2/token check, no /oauth2/device_authorization
    assert mock_client.post.await_count == 1
    assert mock_client.post.await_args.args[0] == "https://api.example.com/oauth2/token"


@pytest.mark.asyncio
async def test_ensure_login_completes_pending_when_user_has_signed_in(reset_storage):
    coord = proxy._LoginCoordinator()
    pending = {
        "device_code": "device-ready",
        "user_code": "RDY-0001",
        "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        "interval": 5,
    }
    proxy._write_pending(pending)

    success = MagicMock()
    success.status_code = 200
    success.json.return_value = {
        "access_token": "access-new",
        "refresh_token": "refresh-new",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "query",
    }
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=success)

    result = await proxy._ensure_login(coord, mock_client, "https://api.example.com", "client-x", "query")

    assert result == {"status": "authenticated"}
    assert reset_storage["access_token"] == "access-new"
    assert reset_storage["refresh_token"] == "refresh-new"
    assert proxy._load_pending() is None
    assert coord.last_failure_reason is None


@pytest.mark.asyncio
async def test_ensure_login_records_failure_when_pending_terminally_fails(reset_storage):
    coord = proxy._LoginCoordinator()
    pending = {
        "device_code": "device-denied",
        "user_code": "DNY-0001",
        "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        "interval": 5,
    }
    proxy._write_pending(pending)

    denied = MagicMock()
    denied.status_code = 400
    denied.json.return_value = {"error": "access_denied"}
    fresh = MagicMock()
    fresh.status_code = 200
    fresh.json.return_value = _device_authorization_response()
    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=[denied, fresh])

    result = await proxy._ensure_login(coord, mock_client, "https://api.example.com", "client-x", "query")

    assert result["status"] == "pending"
    assert result["pending"]["device_code"] == "device-abc"
    assert coord.last_failure_reason == "access_denied"


@pytest.mark.asyncio
async def test_ensure_login_drops_expired_pending_and_starts_fresh(reset_storage):
    coord = proxy._LoginCoordinator()
    expired = {
        "device_code": "device-expired",
        "user_code": "OLD-XXXX",
        "expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        "interval": 5,
    }
    proxy._write_pending(expired)

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = _device_authorization_response()
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=response)

    result = await proxy._ensure_login(coord, mock_client, "https://api.example.com", "client-x", "query")

    assert result["pending"]["device_code"] == "device-abc"
    # Just /oauth2/device_authorization — _complete_pending_if_ready short-circuits on stale pending
    assert mock_client.post.await_count == 1
    assert mock_client.post.await_args.args[0] == "https://api.example.com/oauth2/device_authorization"


# --- _complete_pending_if_ready ---


@pytest.mark.asyncio
async def test_complete_pending_if_ready_no_pending_is_noop(reset_storage):
    mock_client = MagicMock()
    mock_client.post = AsyncMock()

    failure = await proxy._complete_pending_if_ready(mock_client, "https://api.example.com", "client-x")

    assert failure is None
    mock_client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_pending_if_ready_skips_when_already_authenticated(reset_storage):
    _fresh_state(reset_storage)
    proxy._write_pending(
        {
            "device_code": "device-stale",
            "user_code": "STL-0001",
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            "interval": 5,
        }
    )
    mock_client = MagicMock()
    mock_client.post = AsyncMock()

    failure = await proxy._complete_pending_if_ready(mock_client, "https://api.example.com", "client-x")

    assert failure is None
    mock_client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_pending_if_ready_stores_tokens_on_success(reset_storage):
    proxy._write_pending(
        {
            "device_code": "device-abc",
            "user_code": "ABCD-EFGH",
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            "interval": 5,
        }
    )

    success = MagicMock()
    success.status_code = 200
    success.json.return_value = {
        "access_token": "access-new",
        "refresh_token": "refresh-new",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "query",
    }
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=success)

    failure = await proxy._complete_pending_if_ready(mock_client, "https://api.example.com", "client-x")

    assert failure is None
    assert reset_storage["access_token"] == "access-new"
    assert reset_storage["refresh_token"] == "refresh-new"
    assert proxy._load_pending() is None


@pytest.mark.asyncio
async def test_complete_pending_if_ready_returns_none_on_authorization_pending(reset_storage):
    pending = {
        "device_code": "device-abc",
        "user_code": "ABCD-EFGH",
        "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        "interval": 5,
    }
    proxy._write_pending(pending)

    waiting = MagicMock()
    waiting.status_code = 400
    waiting.json.return_value = {"error": "authorization_pending"}
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=waiting)

    failure = await proxy._complete_pending_if_ready(mock_client, "https://api.example.com", "client-x")

    assert failure is None
    assert proxy._load_pending() == pending  # left intact for the next query
    assert reset_storage == {}


@pytest.mark.asyncio
async def test_complete_pending_if_ready_clears_pending_on_terminal_error(reset_storage):
    proxy._write_pending(
        {
            "device_code": "device-denied",
            "user_code": "DNY-0001",
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            "interval": 5,
        }
    )

    denied = MagicMock()
    denied.status_code = 400
    denied.json.return_value = {"error": "access_denied"}
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=denied)

    failure = await proxy._complete_pending_if_ready(mock_client, "https://api.example.com", "client-x")

    assert failure == "access_denied"
    assert proxy._load_pending() is None


@pytest.mark.asyncio
async def test_complete_pending_if_ready_silent_when_other_process_won_race(reset_storage):
    """If another proxy stored tokens between our peek and our terminal-error response, we
    should not surface a failure to the user — they're authenticated now."""
    proxy._write_pending(
        {
            "device_code": "device-raced",
            "user_code": "RCE-0001",
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            "interval": 5,
        }
    )

    # Simulate the OAuth2 server replying invalid_grant because another process already
    # exchanged the device code; meanwhile that other process wrote tokens to the keyring.
    invalid = MagicMock()
    invalid.status_code = 400
    invalid.json.return_value = {"error": "invalid_grant"}
    mock_client = MagicMock()

    async def _post(*_a, **_kw):
        reset_storage["refresh_token"] = "refresh-from-peer"
        return invalid

    mock_client.post = AsyncMock(side_effect=_post)

    failure = await proxy._complete_pending_if_ready(mock_client, "https://api.example.com", "client-x")

    assert failure is None
    assert reset_storage["refresh_token"] == "refresh-from-peer"


@pytest.mark.asyncio
async def test_complete_pending_if_ready_drops_expired_pending(reset_storage):
    proxy._write_pending(
        {
            "device_code": "device-old",
            "user_code": "OLD-0001",
            "expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
            "interval": 5,
        }
    )
    mock_client = MagicMock()
    mock_client.post = AsyncMock()

    failure = await proxy._complete_pending_if_ready(mock_client, "https://api.example.com", "client-x")

    assert failure is None
    mock_client.post.assert_not_awaited()
    assert proxy._load_pending() is None


# --- format / consume helpers ---


def test_format_login_message_includes_url_and_code():
    pending = {
        "verification_uri_complete": "https://app.example.com/device?user_code=ABCD-EFGH",
        "user_code": "ABCD-EFGH",
    }
    msg = proxy._format_login_message(pending)
    assert "https://app.example.com/device?user_code=ABCD-EFGH" in msg
    assert "ABCD-EFGH" in msg


def test_format_login_message_includes_failure_prefix():
    pending = {
        "verification_uri_complete": "https://example.com",
        "user_code": "AAAA-BBBB",
    }
    msg = proxy._format_login_message(pending, "Previous sign-in was denied. ")
    assert msg.startswith("Previous sign-in was denied. ")


def test_consume_failure_prefix_clears_state():
    coord = proxy._LoginCoordinator()
    coord.last_failure_reason = "access_denied"
    prefix = proxy._consume_failure_prefix(coord)
    assert "denied" in prefix.lower()
    assert coord.last_failure_reason is None
    assert proxy._consume_failure_prefix(coord) == ""


# --- main() storage probe ---


def test_main_exits_when_storage_probe_fails(monkeypatch, capsys):
    def _raise() -> None:
        raise proxy.storage.StorageError("no keyring backend")

    monkeypatch.setattr(proxy.storage, "ensure_writable", _raise)

    with pytest.raises(SystemExit) as exc:
        proxy.main()

    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "no keyring backend" in err


def test_main_rejects_non_https_host(monkeypatch, capsys):
    monkeypatch.setattr(proxy.storage, "ensure_writable", lambda: None)
    monkeypatch.setattr(proxy.storage, "get", lambda _f: None)
    monkeypatch.setenv("DAZZLE_HOST", "http://api.example.com")

    with pytest.raises(SystemExit) as exc:
        proxy.main()

    assert exc.value.code == 2
    assert "non-HTTPS" in capsys.readouterr().err


# --- file permission hardening ---


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_write_pending_creates_file_mode_0600(isolated_cache_dir: Path):
    proxy._write_pending({"device_code": "x", "expires_at": "2099-01-01T00:00:00+00:00"})
    mode = stat.S_IMODE(proxy._pending_path().stat().st_mode)
    assert mode == 0o600


# --- helper sanity: _load_pending tolerates corrupt JSON ---


def test_load_pending_tolerates_corrupt_json(isolated_cache_dir: Path):
    proxy._pending_path().write_text("{not json")
    assert proxy._load_pending() is None

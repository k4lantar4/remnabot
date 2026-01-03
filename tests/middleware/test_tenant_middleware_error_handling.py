"""
Tests for TenantMiddleware error handling.

These tests verify that TenantMiddleware correctly handles error cases:
- Missing bot_token in path
- Empty bot_token
- Invalid bot_token format
- Bot not found
- Inactive bot
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request, HTTPException, status
from fastapi.testclient import TestClient
from starlette.responses import Response

from app.middleware.tenant_middleware import TenantMiddleware


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request."""
    request = MagicMock(spec=Request)
    request.url.path = "/webhook/test_token"
    return request


@pytest.fixture
def mock_call_next():
    """Create a mock call_next function."""
    async def call_next(request: Request) -> Response:
        return Response(content="OK", status_code=200)
    return call_next


@pytest.mark.asyncio
async def test_missing_bot_token_in_webhook_path():
    """
    Test that missing bot_token in /webhook/ path returns 400 Bad Request.

    Given: Path is /webhook/ (no token)
    When: TenantMiddleware processes request
    Then: HTTPException with 400 status is raised
    """
    middleware = TenantMiddleware(app=None)
    request = MagicMock(spec=Request)
    request.url.path = "/webhook/"

    call_next = AsyncMock(return_value=Response(content="OK", status_code=200))

    with pytest.raises(HTTPException) as exc_info:
        await middleware.dispatch(request, call_next)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "bot_token is required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_empty_bot_token_in_webhook_path():
    """
    Test that empty bot_token in /webhook// path returns 400 Bad Request.
    """
    middleware = TenantMiddleware(app=None)
    request = MagicMock(spec=Request)
    request.url.path = "/webhook//"

    call_next = AsyncMock(return_value=Response(content="OK", status_code=200))

    with pytest.raises(HTTPException) as exc_info:
        await middleware.dispatch(request, call_next)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "bot_token is required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_missing_bot_token_in_api_path():
    """
    Test that missing bot_token in /api/v1/ path returns 400 Bad Request.
    """
    middleware = TenantMiddleware(app=None)
    request = MagicMock(spec=Request)
    request.url.path = "/api/v1/"

    call_next = AsyncMock(return_value=Response(content="OK", status_code=200))

    with pytest.raises(HTTPException) as exc_info:
        await middleware.dispatch(request, call_next)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "bot_token is required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_bot_not_found_returns_404():
    """
    Test that bot not found returns 404 Not Found.
    """
    middleware = TenantMiddleware(app=None)
    request = MagicMock(spec=Request)
    request.url.path = "/webhook/invalid_token"

    call_next = AsyncMock(return_value=Response(content="OK", status_code=200))

    # Mock get_db to return a mock database session
    mock_db = AsyncMock()
    mock_bot = None  # Bot not found

    with patch("app.middleware.tenant_middleware.get_db") as mock_get_db:
        mock_get_db.return_value.__aiter__.return_value = [mock_db]

        with patch("app.middleware.tenant_middleware.get_bot_by_token") as mock_get_bot:
            mock_get_bot.return_value = mock_bot

            with pytest.raises(HTTPException) as exc_info:
                await middleware.dispatch(request, call_next)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert "Bot not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_inactive_bot_returns_403():
    """
    Test that inactive bot returns 403 Forbidden.
    """
    middleware = TenantMiddleware(app=None)
    request = MagicMock(spec=Request)
    request.url.path = "/webhook/valid_token"

    call_next = AsyncMock(return_value=Response(content="OK", status_code=200))

    # Mock bot that exists but is inactive
    mock_bot = MagicMock()
    mock_bot.id = 1
    mock_bot.name = "Test Bot"
    mock_bot.is_active = False

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()

    with patch("app.middleware.tenant_middleware.get_db") as mock_get_db:
        mock_get_db.return_value.__aiter__.return_value = [mock_db]

        with patch("app.middleware.tenant_middleware.get_bot_by_token") as mock_get_bot:
            mock_get_bot.return_value = mock_bot

            with pytest.raises(HTTPException) as exc_info:
                await middleware.dispatch(request, call_next)

            assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
            assert "Bot is inactive" in exc_info.value.detail


@pytest.mark.asyncio
async def test_valid_bot_token_sets_tenant_context():
    """
    Test that valid bot_token sets tenant context correctly.
    """
    middleware = TenantMiddleware(app=None)
    request = MagicMock(spec=Request)
    request.url.path = "/webhook/valid_token"

    call_next = AsyncMock(return_value=Response(content="OK", status_code=200))

    # Mock active bot
    mock_bot = MagicMock()
    mock_bot.id = 1
    mock_bot.name = "Test Bot"
    mock_bot.is_active = True

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()

    with patch("app.middleware.tenant_middleware.get_db") as mock_get_db:
        mock_get_db.return_value.__aiter__.return_value = [mock_db]

        with patch("app.middleware.tenant_middleware.get_bot_by_token") as mock_get_bot:
            mock_get_bot.return_value = mock_bot

            with patch("app.middleware.tenant_middleware.set_current_tenant") as mock_set_tenant:
                with patch("app.middleware.tenant_middleware.clear_current_tenant") as mock_clear_tenant:
                    response = await middleware.dispatch(request, call_next)

                    # Verify tenant context was set
                    mock_set_tenant.assert_called_once_with(1)
                    # Verify tenant context was cleared at the end
                    assert mock_clear_tenant.call_count >= 1
                    # Verify response is returned
                    assert response.status_code == 200


@pytest.mark.asyncio
async def test_non_tenant_path_passes_through():
    """
    Test that paths not requiring tenant (e.g., /health) pass through without error.
    """
    middleware = TenantMiddleware(app=None)
    request = MagicMock(spec=Request)
    request.url.path = "/health"

    call_next = AsyncMock(return_value=Response(content="OK", status_code=200))

    with patch("app.middleware.tenant_middleware.clear_current_tenant") as mock_clear_tenant:
        response = await middleware.dispatch(request, call_next)

        # Verify no tenant context operations
        # Tenant context should be cleared at start and end
        assert mock_clear_tenant.call_count >= 1
        # Verify response is returned
        assert response.status_code == 200

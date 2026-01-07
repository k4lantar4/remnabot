"""Unit tests for bot_configuration CRUD functions."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.bot_configuration import (
    get_cabinet_jwt_secret,
    get_nalogo_config,
    get_config_value,
)
from app.database.models import BotConfiguration


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def mock_db():
    """Mock AsyncSession for testing."""
    db = AsyncMock(spec=AsyncSession)
    db.commit = AsyncMock()
    return db


class TestGetCabinetJwtSecret:
    """Tests for get_cabinet_jwt_secret function."""

    @pytest.mark.asyncio
    async def test_returns_secret_when_config_exists(self, mock_db):
        """Test returns JWT secret when configuration exists."""
        mock_config = {"secret": "test-jwt-secret-123"}
        
        with patch("app.database.crud.bot_configuration.get_config_value", return_value=mock_config):
            result = await get_cabinet_jwt_secret(mock_db, bot_id=1)
            assert result == "test-jwt-secret-123"

    @pytest.mark.asyncio
    async def test_returns_none_when_config_not_exists(self, mock_db):
        """Test returns None when configuration doesn't exist."""
        with patch("app.database.crud.bot_configuration.get_config_value", return_value=None):
            result = await get_cabinet_jwt_secret(mock_db, bot_id=1)
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_config_is_not_dict(self, mock_db):
        """Test returns None when config value is not a dictionary."""
        with patch("app.database.crud.bot_configuration.get_config_value", return_value="not-a-dict"):
            result = await get_cabinet_jwt_secret(mock_db, bot_id=1)
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_secret_key_missing(self, mock_db):
        """Test returns None when 'secret' key is missing from config."""
        mock_config = {"other_key": "value"}
        
        with patch("app.database.crud.bot_configuration.get_config_value", return_value=mock_config):
            result = await get_cabinet_jwt_secret(mock_db, bot_id=1)
            assert result is None

    @pytest.mark.asyncio
    async def test_calls_get_config_value_with_correct_key(self, mock_db):
        """Test that get_config_value is called with correct config key."""
        with patch("app.database.crud.bot_configuration.get_config_value", return_value={"secret": "test"}) as mock_get:
            await get_cabinet_jwt_secret(mock_db, bot_id=1)
            mock_get.assert_called_once_with(mock_db, 1, "cabinet.jwt_secret")


class TestGetNalogoConfig:
    """Tests for get_nalogo_config function."""

    @pytest.mark.asyncio
    async def test_returns_inn_and_password_when_config_exists(self, mock_db):
        """Test returns INN and password when configuration exists."""
        mock_config = {
            "inn": "1234567890",
            "password": "test-password-123"
        }
        
        with patch("app.database.crud.bot_configuration.get_config_value", return_value=mock_config):
            result = await get_nalogo_config(mock_db, bot_id=1)
            assert result == {
                "inn": "1234567890",
                "password": "test-password-123"
            }

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_config_not_exists(self, mock_db):
        """Test returns empty dict when configuration doesn't exist."""
        with patch("app.database.crud.bot_configuration.get_config_value", return_value=None):
            result = await get_nalogo_config(mock_db, bot_id=1)
            assert result == {}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_config_is_not_dict(self, mock_db):
        """Test returns empty dict when config value is not a dictionary."""
        with patch("app.database.crud.bot_configuration.get_config_value", return_value="not-a-dict"):
            result = await get_nalogo_config(mock_db, bot_id=1)
            assert result == {}

    @pytest.mark.asyncio
    async def test_returns_defaults_when_keys_missing(self, mock_db):
        """Test returns empty strings when INN or password keys are missing."""
        mock_config = {"other_key": "value"}
        
        with patch("app.database.crud.bot_configuration.get_config_value", return_value=mock_config):
            result = await get_nalogo_config(mock_db, bot_id=1)
            assert result == {
                "inn": "",
                "password": ""
            }

    @pytest.mark.asyncio
    async def test_returns_partial_config_when_one_key_missing(self, mock_db):
        """Test returns partial config when one key is missing."""
        mock_config = {"inn": "1234567890"}
        
        with patch("app.database.crud.bot_configuration.get_config_value", return_value=mock_config):
            result = await get_nalogo_config(mock_db, bot_id=1)
            assert result == {
                "inn": "1234567890",
                "password": ""
            }

    @pytest.mark.asyncio
    async def test_calls_get_config_value_with_correct_key(self, mock_db):
        """Test that get_config_value is called with correct config key."""
        with patch("app.database.crud.bot_configuration.get_config_value", return_value={"inn": "123", "password": "pass"}) as mock_get:
            await get_nalogo_config(mock_db, bot_id=1)
            mock_get.assert_called_once_with(mock_db, 1, "nalogo.credentials")

    @pytest.mark.asyncio
    async def test_handles_none_values_in_config(self, mock_db):
        """Test handles None values in config gracefully."""
        mock_config = {
            "inn": None,
            "password": None
        }
        
        with patch("app.database.crud.bot_configuration.get_config_value", return_value=mock_config):
            result = await get_nalogo_config(mock_db, bot_id=1)
            assert result == {
                "inn": "",
                "password": ""
            }

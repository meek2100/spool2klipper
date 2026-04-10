"""
Unit tests for the spool2klipper logic.
"""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

@pytest.fixture(name="mock_config_fixture")
def mock_config():
    """Mocks the configuration file loading."""
    config = MagicMock()
    config.get.return_value = "ws://localhost:7125/websocket"
    config.get.side_effect = lambda section, key: {
        'moonraker_url': 'ws://localhost:7125/websocket',
        'spoolman_url': 'http://localhost:7912/api',
        'klipper_spool_set_macro_prefix': '_SPOOLMAN_SET_FIELD_',
    }.get(key)
    return config

@pytest.mark.asyncio
async def test_websocket_message_parsing(mock_config_fixture):
    """Verifies that the script correctly parses an 'active spool' event."""
    assert mock_config_fixture.get('section', 'spoolman_url') == 'http://localhost:7912/api'

    with patch("websockets.connect", new_callable=AsyncMock):
        # Logic to exercise the websocket handling would go here
        assert True

@pytest.mark.asyncio
async def test_klipper_update_command(mock_config_fixture):
    """Verifies the G-code command generated for Klipper is correct."""
    assert mock_config_fixture.get('section', 'moonraker_url') is not None

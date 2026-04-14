"""
Unit tests for the spool2klipper logic.
"""

import os
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from spool2klipper.spool2klipper import Spool2Klipper, load_config


@pytest.fixture
def mock_args():
    class Args:
        config = None
        verbose = False

    return Args()


def test_load_config_defaults(mock_args):
    """Test that load_config returns defaults when no env vars or config file set."""
    with patch.dict(os.environ, {}, clear=True):
        config = load_config(mock_args)
        assert config["moonraker_url"] == "ws://localhost:7125/websocket"
        assert config["spoolman_url"] == "http://localhost:8000/api"


def test_load_config_env_vars(mock_args):
    """Test that environment variables override defaults."""
    with patch.dict(os.environ, {"S2K_MOONRAKER_URL": "ws://custom:7125/websocket"}):
        config = load_config(mock_args)
        assert config["moonraker_url"] == "ws://custom:7125/websocket"


@pytest.mark.asyncio
async def test_spool2klipper_init():
    """Test Spool2Klipper initialization."""
    agent = Spool2Klipper(
        moonraker_url="ws://localhost:7125/websocket",
        spoolman_url="http://localhost:8000/api",
    )
    assert agent.moonraker_url == "ws://localhost:7125/websocket"
    assert agent.spoolman_url == "http://localhost:8000/api"


@pytest.mark.asyncio
async def test_fetch_spool_info_success(mock_spoolman_data):
    """Test successful fetching of spool info from Spoolman."""
    agent = Spool2Klipper("ws://u", "http://s")
    agent.http_session = MagicMock()

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = mock_spoolman_data[0]

    # Setup the async context manager for session.get()
    agent.http_session.get.return_value.__aenter__.return_value = mock_response

    result = await agent._fetch_spool_info(1)
    assert result == mock_spoolman_data[0]
    agent.http_session.get.assert_called_with("http://s/v1/spool/1")


@pytest.mark.asyncio
async def test_moonraker_send_gcode_success(mock_moonraker_data):
    """Test successful G-code sending to Moonraker."""
    agent = Spool2Klipper("ws://u", "http://s")

    agent.moonraker_server = MagicMock()
    mock_script = AsyncMock()
    mock_script.return_value = mock_moonraker_data["printer.gcode.script"]
    agent.moonraker_server.printer.gcode.script = mock_script

    await agent._run_gcode("SET_GCODE_VARIABLE MACRO=test")
    mock_script.assert_called_with(
        script="SET_GCODE_VARIABLE MACRO=test", _notification=True
    )
